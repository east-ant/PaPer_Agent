from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import init_db, save_paper, get_papers
from api_get import (
    arxiv_search, semantic_search, core_search, crossref_search,
    remove_duplicates, sort_papers_by_recency, resolve_pdf_candidate,
)
from agent import analyze_paper, is_relevant, translate_abstract, read_paper_pdf, summarize_body, summarize_full
from config import settings
from auth import router as auth_router, decode_jwt

app = FastAPI()
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    keyword: str
    limit: int = 10
    summaryMode: str = "abstract"


class PdfRequest(BaseModel):
    link: str
    source: str
    abstract: str = ""
    summaryMode: str = "abstract"


def get_email_from_token(authorization: Optional[str]) -> str:
    """Authorization: Bearer <token> 헤더에서 email 추출"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다.")
    token = authorization.split(" ", 1)[1]
    payload = decode_jwt(token)
    return payload["email"]


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {"message": "Paper Agent 서버 정상 동작"}


@app.post("/search")
def search(body: SearchRequest, authorization: Optional[str] = Header(None)):
    email = get_email_from_token(authorization)

    papers = []
    papers += arxiv_search(body.keyword, body.limit)
    papers += crossref_search(body.keyword, body.limit)
    papers += semantic_search(body.keyword, settings.semantic_scholar_api_key, body.limit)
    papers += core_search(body.keyword, settings.core_api_key, body.limit)

    papers = remove_duplicates(papers)
    papers = sort_papers_by_recency(papers)

    result = []
    for i, p in enumerate(papers[:body.limit]):
        authors = p.get("authors", [])
        journal = p.get("venue") or p.get("journal") or p.get("source") or ""
        if isinstance(journal, dict):
            journal = journal.get("name", "")

        abstract = p.get("summary") or p.get("abstract") or ""

        summary = ""
        if body.summaryMode == "abstract":
            summary = translate_abstract(abstract)

        elif body.summaryMode == "body":
            try:
                paper = {"link": p.get("link") or "", "source": p.get("source") or ""}
                pdf_url = resolve_pdf_candidate(paper)
                body_text = read_paper_pdf(pdf_url, max_pages=1)
                summary = summarize_body(abstract, body_text)
            except:
                summary = translate_abstract(abstract)

        elif body.summaryMode == "full":
            try:
                paper = {"link": p.get("link") or "", "source": p.get("source") or ""}
                pdf_url = resolve_pdf_candidate(paper)
                full_text = read_paper_pdf(pdf_url)
                summary = summarize_full(full_text)
            except:
                summary = translate_abstract(abstract)

        result.append({
            "id": p.get("paperId") or p.get("id") or str(i),
            "title": p.get("title") or "제목 없음",
            "authors": ", ".join(authors) if isinstance(authors, list) else str(authors),
            "year": str(p.get("published") or p.get("year") or "")[:4],
            "journal": journal,
            "citations": p.get("citationCount") or 0,
            "summary": summary,
            "link": p.get("link") or "",
        })
        save_paper(
            arxiv_id=p.get("paperId") or p.get("id") or str(i),
            title=p.get("title") or "제목 없음",
            abstract=abstract,
            summary=summary,
            user_email=email,
            category=str(p.get("categories", [""])[0]) if p.get("categories") else None,
        )

    return {"papers": result}


@app.post("/analyze")
def analyze(title: str, abstract: str, keyword: str, arxiv_id: str = "test-001"):
    result = analyze_paper(title, abstract, keyword)
    relevant = is_relevant(result)

    if relevant:
        saved = save_paper(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            summary=result,
            user_email="anonymous",
        )
        return {"relevant": True, "summary": result, "saved": saved}

    return {"relevant": False, "summary": "관련 없는 논문", "saved": False}


@app.post("/collect")
def collect(keyword: str, max_results: int = 10, authorization: Optional[str] = Header(None)):
    email = get_email_from_token(authorization)

    papers = []
    papers += arxiv_search(keyword, max_results)
    papers += crossref_search(keyword, max_results)
    papers += semantic_search(keyword, settings.semantic_scholar_api_key, max_results)
    papers += core_search(keyword, settings.core_api_key, max_results)

    papers = remove_duplicates(papers)
    papers = sort_papers_by_recency(papers)

    saved_count = 0
    relevant_count = 0

    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("summary", "") or paper.get("abstract", "")
        arxiv_id = paper.get("id", "") or paper.get("paperId", "") or title[:50]

        if not title or not abstract:
            continue

        result = analyze_paper(title, abstract, keyword)
        if is_relevant(result):
            relevant_count += 1
            saved = save_paper(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                summary=result,
                user_email=email,
                category=str(paper.get("categories", [""])[0]) if paper.get("categories") else None,
            )
            if saved:
                saved_count += 1

    return {
        "keyword": keyword,
        "total_collected": len(papers),
        "relevant_count": relevant_count,
        "saved_count": saved_count,
    }


@app.get("/papers")
def papers(authorization: Optional[str] = Header(None)):
    email = get_email_from_token(authorization)
    return get_papers(email)


@app.post("/paper/pdf")
def get_paper_pdf(body: PdfRequest):
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    try:
        paper = {"link": body.link, "source": body.source}

        if body.summaryMode == "abstract":
            summary = translate_abstract(body.abstract)
            return {"success": True, "summary": summary}

        pdf_url = resolve_pdf_candidate(paper)

        if body.summaryMode == "body":
            text = read_paper_pdf(pdf_url, max_pages=1)
            if not text:
                return {"success": False, "summary": ""}
            summary = summarize_body(body.abstract, text)
        else:
            text = read_paper_pdf(pdf_url)
            if not text:
                return {"success": False, "summary": ""}
            summary = summarize_full(text)

        return {"success": True, "summary": summary}
    except Exception as e:
        return {"success": False, "summary": str(e)}