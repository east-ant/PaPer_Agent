import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from api_get import (
    arxiv_search,
    crossref_search,
    semantic_search,
    core_search,
    normalize_title,
    remove_duplicates,
    resolve_pdf_candidate,
    sort_papers_by_recency,
)
from config import settings

try:
    from agent import (
        read_paper_pdf, summarize_body, summarize_full, translate_abstract, 
        translate_keyword_to_english, generate_search_plan_chain, generate_fallback_chain,
        critic_chain
    )
except Exception:
    read_paper_pdf = None
    summarize_body = None
    summarize_full = None
    translate_abstract = None
    translate_keyword_to_english = lambda x: x
    generate_search_plan_chain = None
    generate_fallback_chain = None
    critic_chain = None


SOURCE_ALIASES = {
    "arxiv": "arxiv",
    "crossref": "crossref",
    "semantic": "semantic",
    "semantic scholar": "semantic",
    "core": "core",
}


@dataclass
class AgentGoal:
    user_email: str | None
    keywords: list[str]
    sources: list[str]
    collect_count: int = 5
    language: str = "ko"
    summary_length: str = "medium"


@dataclass
class AgentStep:
    name: str
    detail: dict = field(default_factory=dict)


class PaperAgentRunner:
    """
    Goal-driven paper collection loop.

    The old pipeline searched fixed keywords once. This runner adds a light
    agent layer: plan search terms, call tools, evaluate candidates, and retry
    with broader terms when the result set is weak.
    """

    def __init__(
        self,
        goal: AgentGoal,
        sent_keys: set[str] | None = None,
        max_rounds: int = 3,
    ):
        self.goal = goal
        self.sent_keys = sent_keys or set()
        self.max_rounds = max_rounds
        self.steps: list[AgentStep] = []

    def run(self) -> dict:
        self._record("goal_received", {
            "keywords": self.goal.keywords,
            "sources": self.goal.sources,
            "collect_count": self.goal.collect_count,
            "summary_mode": self._summary_mode(),
        })

        plan = self._build_search_plan()
        self._record("plan_created", plan)

        selected: list[dict] = []
        seen_titles: set[str] = set()

        for round_index in range(1, self.max_rounds + 1):
            round_terms = plan["rounds"][min(round_index - 1, len(plan["rounds"]) - 1)]
            
            max_retries = 1
            retry_count = 0
            
            while retry_count <= max_retries:
                fetch_limit = max(10, self.goal.collect_count * (round_index + 2))
                candidates = self._search_round(round_terms, fetch_limit)
                ranked = self._rank_candidates(candidates)

                added = 0
                for paper in ranked:
                    title_key = normalize_title(paper.get("title"))
                    if not title_key or title_key in seen_titles:
                        continue
                    if self._was_sent(paper):
                        continue

                    pdf_url = self._pdf_url(paper)
                    if not pdf_url:
                        self._record("candidate_skipped", {
                            "title": paper.get("title"),
                            "reason": "pdf_missing",
                            "query": paper.get("_agent_query"),
                        })
                        continue

                    # 비판적 사고 평가 (Critic Filtering)
                    is_relevant = self._evaluate_with_critic(paper)
                    if not is_relevant:
                        self._record("candidate_skipped", {
                            "title": paper.get("title"),
                            "reason": "critic_rejected",
                            "query": paper.get("_agent_query"),
                        })
                        continue

                    paper["_agent_pdf_url"] = pdf_url
                    selected.append(paper)
                    seen_titles.add(title_key)
                    added += 1
                    if len(selected) >= self.goal.collect_count:
                        break

                self._record("round_completed", {
                    "round": round_index,
                    "retry": retry_count,
                    "terms": round_terms,
                    "candidates": len(candidates),
                    "selected_total": len(selected),
                    "added": added,
                })

                if len(selected) >= self.goal.collect_count:
                    break
                    
                # Self-Correction: 만약 해당 라운드에서 하나도 건지지 못했고 LLM 체인이 있다면
                if added == 0 and generate_fallback_chain and retry_count < max_retries:
                    self._record("self_correction", {
                        "round": round_index,
                        "failed_terms": round_terms,
                        "reason": "No valid new papers found. Generating new queries..."
                    })
                    try:
                        fallback_json = generate_fallback_chain.invoke({
                            "failed_terms": ", ".join(round_terms),
                            "reason": "Found irrelevant papers, duplicates, or no PDFs. Need fresh, broader academic search terms.",
                            "recent_history": getattr(self, "recent_history", "")
                        })
                        import json
                        clean_json = fallback_json.strip()
                        if clean_json.startswith("```json"):
                            clean_json = clean_json[7:-3].strip()
                        elif clean_json.startswith("```"):
                            clean_json = clean_json[3:-3].strip()
                        new_terms = json.loads(clean_json)
                        if isinstance(new_terms, list) and new_terms:
                            round_terms = new_terms
                            retry_count += 1
                            continue
                    except Exception as e:
                        print(f"[PaperAgentRunner] Fallback generation error: {e}")
                
                break # 더 이상 재시도하지 않음
                
            if len(selected) >= self.goal.collect_count:
                break

        papers = selected[: self.goal.collect_count]
        self._enrich_summaries(papers)
        self._record("finalized", {"papers": len(papers)})

        return {
            "papers": papers,
            "steps": [step.__dict__ for step in self.steps],
        }

    def _fetch_user_memory(self) -> str:
        if not self.goal.user_email:
            return ""
        
        try:
            from database import get_connection
            import pymysql
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            memory_lines = []
            
            # 1) 최근 북마크 5개 (사용자가 저장한 논문 = 관심사)
            cursor.execute("""
                SELECT title, summary FROM bookmarks
                WHERE user_email = %s
                ORDER BY bookmarked_at DESC LIMIT 5
            """, (self.goal.user_email,))
            bookmarks = cursor.fetchall()
            if bookmarks:
                memory_lines.append("[Recently saved papers - User's interests]")
                for b in bookmarks:
                    title = b.get("title", "Unknown")
                    summary = str(b.get("summary") or "")[:150]
                    memory_lines.append(f"- {title}: {summary}...")
            
            # 2) 👍 피드백 논문 (유용하다고 평가한 논문)
            cursor.execute("""
                SELECT title FROM paper_feedback
                WHERE user_email = %s AND feedback = 'up'
                ORDER BY feedback_at DESC LIMIT 5
            """, (self.goal.user_email,))
            ups = cursor.fetchall()
            if ups:
                memory_lines.append("\n[Papers user found USEFUL (👍) - Find more like these]")
                for u in ups:
                    memory_lines.append(f"- {u.get('title', '')}")
            
            # 3) 👎 피드백 논문 (관련성 낮다고 평가한 논문)
            cursor.execute("""
                SELECT title FROM paper_feedback
                WHERE user_email = %s AND feedback = 'down'
                ORDER BY feedback_at DESC LIMIT 5
            """, (self.goal.user_email,))
            downs = cursor.fetchall()
            if downs:
                memory_lines.append("\n[Papers user found IRRELEVANT (👎) - Avoid similar papers]")
                for d in downs:
                    memory_lines.append(f"- {d.get('title', '')}")
            
            conn.close()
            return "\n".join(memory_lines) if memory_lines else ""
        except Exception as e:
            print(f"[PaperAgentRunner] Error fetching memory: {e}")
            return ""

    def _build_search_plan(self) -> dict:
        base_terms = []
        for kw in self.goal.keywords:
            if kw and kw.strip():
                # 한글 등 비영문 키워드가 섞여있다면 LLM을 통해 영문 학술 용어로 변환
                translated = translate_keyword_to_english(kw.strip())
                base_terms.append(translated)
        
        if not base_terms:
            base_terms = ["latest research"]

        # 사용자 메모리 로드
        recent_history = self._fetch_user_memory()
        self.recent_history = recent_history # Fallback에서 쓰기 위해 저장

        rounds = [base_terms[:3], [], []]
        if generate_search_plan_chain:
            try:
                plan_json_str = generate_search_plan_chain.invoke({
                    "keywords": ", ".join(base_terms),
                    "recent_history": recent_history
                })
                import json
                # 간단한 클렌징 (혹시 마크다운 블록이 있을 경우)
                clean_json = plan_json_str.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:-3].strip()
                elif clean_json.startswith("```"):
                    clean_json = clean_json[3:-3].strip()

                plan_data = json.loads(clean_json)
                r1 = plan_data.get("round_1", base_terms[:3])
                r2 = plan_data.get("round_2", [])
                r3 = plan_data.get("round_3", [])
                rounds = [r1, r2, r3]
            except Exception as e:
                print(f"[PaperAgentRunner] Error generating search plan: {e}")

        # Fallback to hardcoded expansion if LLM fails
        if not rounds[1]:
            expanded = []
            for term in base_terms[:3]:
                expanded.extend(self._expand_keyword(term))
            unique_terms = self._unique(base_terms + expanded)
            rounds = [
                base_terms[:3],
                unique_terms[:6],
                unique_terms[:10],
            ]

        return {
            "objective": "Find recent papers that match the user's research interests.",
            "sources": self._normalize_sources(self.goal.sources),
            "rounds": rounds,
        }

    def _expand_keyword(self, keyword: str) -> list[str]:
        cleaned = keyword.strip()
        variants = [cleaned]

        if " " in cleaned:
            variants.append(cleaned.replace(" ", " AND "))
            variants.append(cleaned.replace(" ", " OR "))

        lower = cleaned.lower()
        if "agent" in lower:
            variants.extend([
                "autonomous language agents",
                "tool using agents",
                "agentic workflow",
                "multi agent systems",
            ])
        if "rag" in lower or "retrieval" in lower:
            variants.extend([
                "retrieval augmented generation",
                "agentic rag",
                "retrieval based question answering",
            ])
        if "llm" in lower or "language model" in lower:
            variants.extend([
                "large language models",
                "llm reasoning",
                "llm evaluation",
            ])

        return self._unique(variants)


    def _search_round(self, terms: list[str], limit: int) -> list[dict]:
        sources = self._normalize_sources(self.goal.sources)
        results: list[dict] = []

        for term in terms:
            for source in sources:
                search_fn = self._source_function(source)
                if search_fn is None:
                    continue
                try:
                    source_results = search_fn(term, limit)
                    for paper in source_results:
                        paper["_agent_query"] = term
                    results.extend(source_results)
                except Exception as error:
                    self._record("tool_error", {
                        "source": source,
                        "query": term,
                        "error": str(error),
                    })

        deduped = remove_duplicates(results)
        return sort_papers_by_recency(deduped)

    def _source_function(self, source: str) -> Callable[[str, int], list[dict]] | None:
        if source == "arxiv":
            return arxiv_search
        # if source == "crossref":
        #     return crossref_search
        if source == "semantic":
            return lambda term, limit: semantic_search(
                term,
                settings.semantic_scholar_api_key,
                limit,
            )
        # if source == "core":
        #     return lambda term, limit: core_search(
        #         term,
        #         settings.core_api_key,
        #         limit,
        #     )
        return None

    def _rank_candidates(self, papers: list[dict]) -> list[dict]:
        scored = []
        for paper in papers:
            score, reasons = self._score_paper(paper)
            paper["_agent_score"] = score
            paper["_agent_reasons"] = reasons
            scored.append(paper)

        return sorted(
            scored,
            key=lambda item: (
                item.get("_agent_score", 0),
                self._published_year(item),
            ),
            reverse=True,
        )

    def _evaluate_with_critic(self, paper: dict) -> bool:
        if not critic_chain:
            return True # LLM 모듈이 없으면 통과 처리
        
        title = paper.get("title", "")
        abstract = paper.get("abstract") or paper.get("summary") or ""
        keywords = ", ".join(self.goal.keywords)
        
        try:
            result = critic_chain.invoke({
                "keyword": keywords,
                "title": title,
                "abstract": abstract
            }).strip()
            
            lines = result.split('\n')
            first_line = lines[0].strip().upper() if lines else ""
            
            if "IRRELEVANT" in first_line:
                return False
                
            if "RELEVANT" in first_line:
                if len(lines) > 1:
                    # 빈 줄 제외하고 가장 첫 번째 텍스트를 Insight로 저장
                    for line in lines[1:]:
                        if line.strip():
                            paper["_agent_insight"] = line.strip()
                            break
                return True
                
            return True # Fallback
        except Exception as e:
            print(f"[PaperAgentRunner] Critic evaluation error: {e}")
            return True

    def _score_paper(self, paper: dict) -> tuple[float, list[str]]:
        title = str(paper.get("title") or "")
        abstract = str(paper.get("abstract") or paper.get("summary") or "")
        categories = " ".join(str(x) for x in paper.get("categories") or [])
        text = f"{title} {abstract} {categories}".lower()
        reasons = []
        score = 0.0

        for keyword in self.goal.keywords:
            tokens = self._keyword_tokens(keyword)
            if not tokens:
                continue
            matched = sum(1 for token in tokens if token in text)
            if matched:
                score += 4.0 * matched / len(tokens)
                reasons.append(f"keyword:{keyword}")

        if abstract:
            score += 1.5
            reasons.append("has_abstract")

        year = self._published_year(paper)
        current_year = datetime.utcnow().year
        if year >= current_year - 1:
            score += 2.0
            reasons.append("recent")
        elif year >= current_year - 3:
            score += 1.0

        citations = paper.get("citationCount") or paper.get("citations") or 0
        try:
            citations = int(citations)
        except Exception:
            citations = 0
        if citations >= 100:
            score += 1.5
            reasons.append("high_citation")
        elif citations >= 10:
            score += 0.7

        if paper.get("link"):
            score += 0.3

        if self._known_pdf_url(paper):
            reasons.append("has_pdf")
        elif self._summary_mode() in {"body", "full"}:
            score -= 100.0
            reasons.append("pdf_missing")

        return score, reasons

    def _enrich_summaries(self, papers: list[dict]) -> None:
        if self.goal.language != "ko":
            return

        user_keywords = ", ".join(self.goal.keywords)

        for paper in papers:
            abstract = paper.get("abstract") or paper.get("summary") or ""
            agent_insight = paper.get("_agent_insight", "")
            
            if paper.get("abstract_ko"):
                continue
            try:
                summary_mode = self._summary_mode()
                if summary_mode == "body":
                    paper["abstract_ko"] = self._summarize_pdf_body(paper, abstract, user_keywords, agent_insight)
                elif summary_mode == "full":
                    paper["abstract_ko"] = self._summarize_pdf_full(paper, abstract, user_keywords, agent_insight)
                else:
                    paper["abstract_ko"] = self._summarize_abstract(abstract, user_keywords, agent_insight)
            except Exception as error:
                self._record("summary_error", {
                    "title": paper.get("title"),
                    "error": str(error),
                })

    def _summarize_abstract(self, abstract: str, user_keywords: str = "", agent_insight: str = "") -> str:
        if not abstract or translate_abstract is None:
            return abstract or ""
        return translate_abstract(abstract, user_keywords, agent_insight)

    def _summarize_pdf_body(self, paper: dict, abstract: str, user_keywords: str = "", agent_insight: str = "") -> str:
        if read_paper_pdf is None or summarize_body is None:
            return self._summarize_abstract(abstract, user_keywords, agent_insight)

        pdf_url = self._pdf_url(paper)
        if not pdf_url:
            self._record("pdf_missing", {"title": paper.get("title"), "mode": "body"})
            return self._summarize_abstract(abstract, user_keywords, agent_insight)

        body_text = read_paper_pdf(pdf_url, max_pages=5)
        if not body_text:
            self._record("pdf_read_empty", {"title": paper.get("title"), "mode": "body"})
            return self._summarize_abstract(abstract, user_keywords, agent_insight)

        paper["_agent_pdf_url"] = pdf_url
        paper["_agent_summary_mode"] = "body"
        return summarize_body(abstract, body_text, user_keywords, agent_insight)

    def _summarize_pdf_full(self, paper: dict, abstract: str, user_keywords: str = "", agent_insight: str = "") -> str:
        if read_paper_pdf is None or summarize_full is None:
            return self._summarize_abstract(abstract, user_keywords, agent_insight)

        pdf_url = self._pdf_url(paper)
        if not pdf_url:
            self._record("pdf_missing", {"title": paper.get("title"), "mode": "full"})
            return self._summarize_abstract(abstract, user_keywords, agent_insight)

        full_text = read_paper_pdf(pdf_url)
        if not full_text:
            self._record("pdf_read_empty", {"title": paper.get("title"), "mode": "full"})
            return self._summarize_abstract(abstract, user_keywords, agent_insight)

        paper["_agent_pdf_url"] = pdf_url
        paper["_agent_summary_mode"] = "full"
        return summarize_full(full_text, user_keywords, agent_insight)

    def _summary_mode(self) -> str:
        mode = str(self.goal.summary_length or "abstract").strip().lower()
        if mode in {"short", "abstract"}:
            return "abstract"
        if mode in {"medium", "body"}:
            return "body"
        if mode == "full":
            return "full"
        return "abstract"

    def _known_pdf_url(self, paper: dict) -> str:
        open_pdf = paper.get("openAccessPdf") or {}
        if isinstance(open_pdf, dict) and open_pdf.get("url"):
            return open_pdf.get("url")

        source = str(paper.get("source") or "").lower()
        link = paper.get("link") or paper.get("url") or ""
        if source == "arxiv" and "arxiv.org/abs/" in link:
            return link.replace("/abs/", "/pdf/") + ("" if link.endswith(".pdf") else ".pdf")
        if source == "arxiv" and "arxiv.org/pdf/" in link:
            return link
        if source == "core" and link:
            return link
        return ""

    def _pdf_url(self, paper: dict) -> str:
        known = self._known_pdf_url(paper)
        if known:
            return known
        try:
            return resolve_pdf_candidate(paper)
        except Exception as error:
            self._record("pdf_resolve_error", {
                "title": paper.get("title"),
                "error": str(error),
            })
            return ""

    def _was_sent(self, paper: dict) -> bool:
        paper_id = str(paper.get("id") or paper.get("paperId") or "").strip()
        title = normalize_title(paper.get("title"))
        return (
            bool(paper_id and f"id:{paper_id}" in self.sent_keys)
            or bool(title and f"title:{title}" in self.sent_keys)
        )

    def _normalize_sources(self, sources: list[str]) -> list[str]:
        normalized = []
        for source in sources or []:
            key = SOURCE_ALIASES.get(str(source).strip().lower())
            if key and key not in normalized:
                normalized.append(key)
        return normalized or ["arxiv", "semantic"]

    def _keyword_tokens(self, keyword: str) -> list[str]:
        return [
            token
            for token in re.split(r"[^0-9a-zA-Z가-힣]+", keyword.lower())
            if len(token) >= 2
        ]

    def _published_year(self, paper: dict) -> int:
        value = paper.get("published") or paper.get("year") or paper.get("publishedDate")
        match = re.search(r"\d{4}", str(value or ""))
        return int(match.group(0)) if match else 0

    def _unique(self, items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            normalized = " ".join(str(item).strip().split())
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        return result

    def _record(self, name: str, detail: dict) -> None:
        try:
            json.dumps(detail, ensure_ascii=False)
        except Exception:
            detail = {"raw": str(detail)}
        self.steps.append(AgentStep(name=name, detail=detail))


def run_paper_agent(
    keywords: list[str],
    sources: list[str],
    collect_count: int,
    user_email: str | None = None,
    sent_keys: set[str] | None = None,
    language: str = "ko",
    summary_length: str = "medium",
) -> dict:
    goal = AgentGoal(
        user_email=user_email,
        keywords=keywords,
        sources=sources,
        collect_count=collect_count,
        language=language,
        summary_length=summary_length,
    )
    return PaperAgentRunner(goal=goal, sent_keys=sent_keys).run()
