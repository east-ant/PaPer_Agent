import io
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime

import feedparser
import numpy as np
import pypdfium2 as pdfium
from rapidocr_onnxruntime import RapidOCR

from config import settings

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = BASE_DIR / "collected_papers.json"
OUTPUT_DIR = BASE_DIR / "translated_outputs"
REQUIRED_SOURCES = ["arXiv", "Crossref", "Semantic Scholar", "CORE"]
OCR_RENDER_SCALE = 1.5


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    if isinstance(value, tuple):
        return [item for item in value if item not in (None, "")]
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    return [value]


def _merge_categories(*groups):
    merged = []
    for group in groups:
        for item in _as_list(group):
            text = _normalize_category_name(item)
            if text and text not in merged:
                merged.append(text)
    return merged


def _normalize_category_name(value):
    if isinstance(value, dict):
        value = value.get("name") or value.get("field") or value.get("label") or value.get("topic")
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("&", " and ")
    text = re.sub(r"[^0-9a-z가-힣]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _json_sql_literal(value):
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("'", "''")


def _category_text_list(values):
    out = []
    for item in _as_list(values):
        if isinstance(item, dict):
            name = item.get("name") or item.get("field") or item.get("label") or item.get("topic")
            if name:
                out.append(str(name).strip())
        else:
            out.append(str(item).strip())
    return [v for v in out if v]


def _extract_ocr_keywords(text: str, top_n: int = 20):
    tokens = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text or "")
    stopwords = {
        "the", "and", "for", "that", "with", "from", "this", "were", "have", "has",
        "into", "their", "they", "than", "also", "these", "using", "used", "which",
        "such", "over", "between", "where", "about", "through", "while", "within",
        "paper", "review", "introduction", "figure", "table", "journal", "doi", "https",
    }
    freq = {}
    for token in tokens:
        word = token.lower()
        if word in stopwords or len(word) < 4:
            continue
        freq[word] = freq.get(word, 0) + 1

    ranked = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:top_n]
    return [word for word, _ in ranked]


def _title_to_text(title):
    if isinstance(title, list):
        return " ".join([str(part) for part in title if part])
    return str(title or "")


def sanitize_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "untitled")[:max_len]


def normalize_title(title):
    if not title:
        return ""
    return " ".join(_title_to_text(title).lower().strip().split())


def _parse_published_value(value):
    if value is None:
        return datetime.min
    if isinstance(value, int):
        return datetime(value, 1, 1)
    text = str(value).strip()
    if not text:
        return datetime.min

    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        try:
            year, month, day = map(int, iso_match.groups())
            return datetime(year, month, day)
        except Exception:
            return datetime.min

    ym_match = re.match(r"^(\d{4})-(\d{2})", text)
    if ym_match:
        try:
            year, month = map(int, ym_match.groups())
            return datetime(year, month, 1)
        except Exception:
            return datetime.min

    year_match = re.match(r"^(\d{4})", text)
    if year_match:
        try:
            return datetime(int(year_match.group(1)), 1, 1)
        except Exception:
            return datetime.min

    digits = re.search(r"\d{4}", text)
    if digits:
        try:
            return datetime(int(digits.group(0)), 1, 1)
        except Exception:
            return datetime.min

    return datetime.min


def sort_papers_by_recency(papers):
    return sorted(
        papers,
        key=lambda paper: (
            _parse_published_value(paper.get("published") or paper.get("year") or paper.get("publishedDate")),
            normalize_title(paper.get("title")),
        ),
        reverse=True,
    )


def normalize_author(author):
    if isinstance(author, dict):
        return str(author.get("name", "")).strip()
    if isinstance(author, str):
        return author.strip()
    return ""


def remove_duplicates(papers):
    seen = set()
    result = []
    for paper in papers:
        title = normalize_title(paper.get("title"))
        if title and title not in seen:
            seen.add(title)
            result.append(paper)
    return result


def request_bytes(url: str, timeout: int = 40, retries: int = 3) -> tuple[bytes, str]:
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), response.headers.get("Content-Type", "")
        except Exception as error:
            last_error = error
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def arxiv_abs_to_pdf(url: str) -> str:
    match = re.match(r"^https?://arxiv\.org/abs/([^?#]+)", url)
    if match:
        return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    return url


def find_pdf_links_in_html(base_url: str, html_bytes: bytes) -> list[str]:
    text = html_bytes.decode("utf-8", errors="ignore")
    candidates = []

    meta_links = re.findall(
        r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']',
        text,
        flags=re.IGNORECASE,
    )
    candidates.extend(meta_links)

    href_links = re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', text, flags=re.IGNORECASE)
    candidates.extend(href_links)

    output = []
    for candidate in candidates:
        candidate = candidate.replace("&amp;", "&")
        full_url = urllib.parse.urljoin(base_url, candidate)
        if full_url not in output:
            output.append(full_url)
    return output


def resolve_pdf_url(link: str) -> str:
    link = (link or "").replace("&amp;", "&")
    candidate = arxiv_abs_to_pdf(link)

    for test_url in [candidate, link]:
        if not test_url:
            continue
        data, content_type = request_bytes(test_url)
        if "pdf" in content_type.lower() or data[:5] == b"%PDF-":
            return test_url

        if "html" in content_type.lower() or data.startswith(b"<"):
            for pdf_url in find_pdf_links_in_html(test_url, data):
                pdf_data, pdf_type = request_bytes(pdf_url)
                if "pdf" in pdf_type.lower() or pdf_data[:5] == b"%PDF-":
                    return pdf_url

    raise ValueError("No direct PDF found")


def extract_pdf_text_ocr(pdf_url: str, ocr_engine: RapidOCR, max_pages: int | None = None) -> str:
    data, content_type = request_bytes(pdf_url)
    if "pdf" not in content_type.lower() and data[:5] != b"%PDF-":
        raise ValueError("Response is not PDF")

    document = pdfium.PdfDocument(io.BytesIO(data))
    chunks = []
    page_count = len(document) if max_pages is None else min(len(document), max_pages)
    for page_index in range(page_count):
        page = document[page_index]
        image = page.render(scale=OCR_RENDER_SCALE).to_pil()
        if image.mode != "RGB":
            image = image.convert("RGB")
        image_array = np.array(image)

        ocr_result, _ = ocr_engine(image_array)
        if not ocr_result:
            continue
        lines = [item[1] for item in ocr_result if len(item) > 1 and item[1]]
        if lines:
            chunks.append("\n".join(lines).strip())

    text = "\n\n".join(chunk for chunk in chunks if chunk).strip()
    if not text:
        raise ValueError("OCR text is empty")
    return text


def crossref_pdf_from_doi(doi_url: str) -> str:
    if "doi.org/" not in doi_url:
        raise ValueError("Not a DOI link")

    doi = doi_url.split("doi.org/", 1)[1]
    api = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    data, _ = request_bytes(api)
    obj = json.loads(data.decode("utf-8", errors="ignore"))
    message = obj.get("message", {})

    for item in message.get("link", []) or []:
        url = item.get("URL") or item.get("url")
        content_type = (item.get("content-type") or "").lower()
        if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
            return url

    return resolve_pdf_url(doi_url)


def semantic_pdf_from_link(link: str) -> str:
    match = re.search(r"/paper/([0-9a-f]{40})", link)
    if not match:
        raise ValueError("Cannot parse Semantic Scholar paper id")

    paper_id = match.group(1)
    api = (
        "https://api.semanticscholar.org/graph/v1/paper/"
        + paper_id
        + "?fields=title,url,openAccessPdf,externalIds"
    )
    data, _ = request_bytes(api)
    obj = json.loads(data.decode("utf-8", errors="ignore"))

    open_pdf = obj.get("openAccessPdf") or {}
    open_pdf_url = open_pdf.get("url")
    if open_pdf_url:
        return open_pdf_url

    external_ids = obj.get("externalIds") or {}
    arxiv_id = external_ids.get("ArXiv")
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    raise ValueError("No open access PDF in Semantic Scholar metadata")


def arxiv_search(query, max_results):
    url = "https://export.arxiv.org/api/query"
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    try:
        with urllib.request.urlopen(f"{url}?{params}") as response:
            feed = feedparser.parse(response.read())

        results = []
        for entry in feed.entries:
            categories = []
            for tag in entry.get("tags", []):
                if tag.get("term"):
                    categories.append(tag.get("term"))

            primary_category = None
            arxiv_primary = entry.get("arxiv_primary_category") or entry.get("arxiv:primary_category")
            if isinstance(arxiv_primary, dict):
                primary_category = arxiv_primary.get("term") or arxiv_primary.get("scheme")
            elif isinstance(arxiv_primary, str):
                primary_category = arxiv_primary

            categories = _merge_categories(categories, primary_category)

            results.append({
                "source": "arXiv",
                "id": entry.get("id"),
                "title": entry.get("title"),
                "summary": entry.get("summary"),
                "published": entry.get("published"),
                "authors": [a.name for a in entry.get("authors", [])],
                "link": entry.get("link"),
                "links": [link.get("href") for link in entry.get("links", []) if link.get("href")],
                "categories": categories,
                "primary_category": primary_category,
                "journal_ref": entry.get("arxiv_journal_ref") or entry.get("arxiv:journal_ref"),
                "comment": entry.get("arxiv_comment") or entry.get("arxiv:comment"),
                "doi": entry.get("arxiv_doi") or entry.get("arxiv:doi"),
            })
        return results
    except Exception as error:
        print(f"arXiv 호출 오류: {error}")
        return []


def crossref_search(query, max_results):
    url = "https://api.crossref.org/works"
    params = urllib.parse.urlencode({
        "query": query,
        "rows": max_results,
        "sort": "published",
        "order": "desc",
    })
    try:
        with urllib.request.urlopen(f"{url}?{params}") as response:
            data = json.loads(response.read())

        results = []
        for item in data.get("message", {}).get("items", []):
            subjects = _as_list(item.get("subject", []))
            container_titles = _as_list(item.get("container-title", []))
            categories = _merge_categories(subjects, container_titles, item.get("type"), item.get("publisher"))

            title_raw = item.get("title", [""])
            title = title_raw[0] if isinstance(title_raw, list) and len(title_raw) > 0 else title_raw
            results.append({
                "source": "Crossref",
                "title": title,
                "authors": [
                    f"{author.get('given', '')} {author.get('family', '')}".strip()
                    for author in item.get("author", [])
                ],
                "published": item.get("created", {}).get("date-time"),
                "link": item.get("URL"),
                "DOI": item.get("DOI"),
                "subject": subjects,
                "container_title": container_titles,
                "type": item.get("type"),
                "publisher": item.get("publisher"),
                "license": item.get("license", []),
                "categories": categories,
            })
        return results
    except Exception as error:
        print(f"Crossref 호출 오류: {error}")
        return []


def semantic_search(query, api_key, max_results):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = urllib.parse.urlencode({
        "query": query,
        "limit": max_results,
        "fields": "title,year,authors,url,fieldsOfStudy,s2FieldsOfStudy,venue,journal,publicationTypes,citationCount,influentialCitationCount,openAccessPdf,externalIds",
    })
    headers = {"x-api-key": api_key} if api_key and "your_" not in api_key else {}
    request = urllib.request.Request(f"{url}?{params}", headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read())

        results = []
        for item in data.get("data", []):
            fields_of_study = _as_list(item.get("fieldsOfStudy", []))
            s2_fields = _as_list(item.get("s2FieldsOfStudy", []))
            venue = item.get("venue")
            journal = item.get("journal") or {}
            categories = _merge_categories(
                fields_of_study,
                _category_text_list(s2_fields),
                venue,
                journal.get("name") if isinstance(journal, dict) else journal,
                item.get("publicationTypes", []),
            )

            results.append({
                "source": "Semantic Scholar",
                "title": item.get("title"),
                "authors": [author.get("name") for author in item.get("authors", [])],
                "published": str(item.get("year", "")),
                "link": item.get("url"),
                "paperId": item.get("paperId"),
                "fieldsOfStudy": fields_of_study,
                "s2FieldsOfStudy": s2_fields,
                "venue": venue,
                "journal": journal,
                "publicationTypes": item.get("publicationTypes", []),
                "citationCount": item.get("citationCount"),
                "influentialCitationCount": item.get("influentialCitationCount"),
                "openAccessPdf": item.get("openAccessPdf"),
                "externalIds": item.get("externalIds"),
                "categories": categories,
            })
        return results
    except Exception as error:
        print(f"Semantic Scholar 호출 실패: {error}")
        return []


def core_search(query, api_key, max_results):
    if not api_key or "your_" in api_key:
        print("CORE API 키가 설정되지 않아 건너뜁니다.")
        return []

    url = "https://api.core.ac.uk/v3/search/works"
    safe_query = "".join(character for character in query if character.isalnum() or character in " ")

    params = urllib.parse.urlencode({
        "q": safe_query,
        "limit": min(max_results, 10),
        "apiKey": api_key.strip(),
    })

    full_url = f"{url}?{params}"
    request = urllib.request.Request(full_url)
    request.add_header("User-Agent", "Mozilla/5.0")

    try:
        time.sleep(0.5)
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read())

        results = []
        for item in data.get("results", []):
            subjects = _as_list(item.get("subjects", []))
            topics = _as_list(item.get("topics", []))
            categories = _merge_categories(subjects, topics, item.get("publisher"), item.get("language"))
            results.append({
                "source": "CORE",
                "title": item.get("title"),
                "authors": [author.get("name") for author in item.get("authors", []) if author.get("name")],
                "published": item.get("publishedDate"),
                "link": item.get("downloadUrl") or item.get("doi"),
                "doi": item.get("doi"),
                "publisher": item.get("publisher"),
                "language": item.get("language"),
                "subjects": subjects,
                "topics": topics,
                "categories": categories,
            })
        return results
    except urllib.error.HTTPError as error:
        if error.code == 500:
            print("CORE API 서버 내부 오류(500) 발생")
        else:
            print(f"CORE API 호출 실패 (HTTP {error.code}): {error.reason}")
        return []
    except Exception as error:
        print(f"CORE API 기타 오류: {error}")
        return []


def group_by_source(papers: list[dict]) -> dict[str, list[dict]]:
    grouped = {source: [] for source in REQUIRED_SOURCES}
    for paper in papers:
        source = paper.get("source")
        if source in grouped:
            grouped[source].append(paper)
    for source in grouped:
        grouped[source] = sort_papers_by_recency(grouped[source])
    return grouped


def fetch_source_candidates(source: str, keyword: str, limit: int, semantic_key: str, core_key: str) -> list[dict]:
    if source == "arXiv":
        return arxiv_search(keyword, limit)
    if source == "Crossref":
        return crossref_search(keyword, limit)
    if source == "Semantic Scholar":
        return semantic_search(keyword, semantic_key, limit)
    if source == "CORE":
        return core_search(keyword, core_key, limit)
    return []


def source_text(paper: dict, ocr_engine: RapidOCR) -> tuple[str, str]:
    source = paper.get("source", "")
    link = (paper.get("link") or "").replace("&amp;", "&")

    if source == "arXiv":
        pdf_url = resolve_pdf_url(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    if source == "Crossref":
        pdf_url = crossref_pdf_from_doi(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    if source == "Semantic Scholar":
        pdf_url = semantic_pdf_from_link(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    if source == "CORE":
        pdf_url = resolve_pdf_url(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    raise ValueError("Unsupported source")


def build_ocr_payload(paper: dict, extracted_text: str, used_link: str) -> dict:
    ocr_keywords = _extract_ocr_keywords(extracted_text, top_n=20)
    categories = _merge_categories(
        paper.get("categories", []),
        paper.get("fieldsOfStudy", []),
        _category_text_list(paper.get("s2FieldsOfStudy", [])),
        paper.get("subject", []),
        paper.get("subjects", []),
        paper.get("topics", []),
        paper.get("publicationTypes", []),
        [f"ocr_{kw}" for kw in ocr_keywords],
    )

    return {
        "paper_id": paper.get("id") or paper.get("paperId") or sanitize_filename(_title_to_text(paper.get("title")) or "untitled"),
        "source": paper.get("source"),
        "title": paper.get("title"),
        "authors": paper.get("authors", []),
        "published": paper.get("published"),
        "link": paper.get("link"),
        "doi": paper.get("doi") or paper.get("DOI"),
        "summary": paper.get("summary"),
        "journal_ref": paper.get("journal_ref"),
        "comment": paper.get("comment"),
        "venue": paper.get("venue"),
        "journal": paper.get("journal"),
        "publisher": paper.get("publisher"),
        "language": paper.get("language"),
        "categories": categories,
        "ocr": {
            "text_file": None,
            "pdf_url": used_link,
            "text_length": len(extracted_text),
        },
    }


def save_ocr_json(paper: dict, extracted_text: str, used_link: str) -> tuple[Path, dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(_title_to_text(paper.get("title")) or "untitled")
    file_name = base_name + ".json"
    output_path = OUTPUT_DIR / file_name
    text_path = OUTPUT_DIR / (base_name + ".txt")

    payload = build_ocr_payload(paper, extracted_text, used_link)
    payload["ocr"]["text_file"] = text_path.name
    payload["ocr"]["text_preview"] = extracted_text[:800]

    for attempt in range(2):
        try:
            text_path.write_text(extracted_text, encoding="utf-8")
            with output_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            break
        except Exception:
            if attempt == 1:
                raise
            time.sleep(0.5)
    return output_path, payload


def main() -> None:
    keyword = input("검색 키워드 입력: ").strip()
    if not keyword:
        print("키워드를 입력해 주세요.")
        return

    max_results_input = input("각 API별 수집할 논문 개수 입력 (기본값 10): ").strip()
    try:
        max_results = int(max_results_input) if max_results_input else 10
    except ValueError:
        max_results = 10
        print(f"잘못된 입력, 기본값 {max_results}를 사용합니다.")

    semantic_key = settings.semantic_scholar_api_key
    core_key = settings.core_api_key
    print(f"\n키워드: '{keyword}', 개수: {max_results}")
    print("-" * 60)
    print("API에서 링크 후보를 가져와 바로 OCR 시도합니다.")
    print(f"OCR 설정: 전체 페이지, 렌더 스케일 {OCR_RENDER_SCALE}")

    print("\n" + "=" * 60)
    print("OCR 추출 시작...")
    print("=" * 60)

    ocr_engine = RapidOCR()
    successful_records = []

    success = 0
    for index, source in enumerate(REQUIRED_SOURCES, start=1):
        print(f"[{index}] {source} :: 최신 후보를 순차적으로 시도")
        done_for_source = False
        last_error = ""
        tried_titles = set()
        search_limit = max_results
        max_search_limit = max(max_results * 5, 30)

        while search_limit <= max_search_limit and not done_for_source:
            candidates = fetch_source_candidates(source, keyword, search_limit, semantic_key, core_key)
            candidates = sort_papers_by_recency(remove_duplicates(candidates))

            fresh_candidates = []
            for paper in candidates:
                title_key = normalize_title(paper.get("title"))
                if not title_key or title_key in tried_titles:
                    continue
                tried_titles.add(title_key)
                fresh_candidates.append(paper)

            if not fresh_candidates:
                print(f"  상위 {search_limit}건에 새 후보가 없어 더 넓게 검색합니다.")
                search_limit += max_results
                continue

            print(f"  상위 {search_limit}건 중 {len(fresh_candidates)}개 후보를 시도합니다.")
            for paper in fresh_candidates:
                print(f"  제목: {_title_to_text(paper.get('title'))}")
                try:
                    text, used_link = source_text(paper, ocr_engine)
                    output_path, payload = save_ocr_json(paper, text, used_link)
                    successful_records.append(payload)
                    print(f"  저장: {output_path.name}")
                    done_for_source = True
                    success += 1
                    break
                except Exception as error:
                    last_error = str(error)
                    print(f"  실패: {error}")
                    print("  다음 최신 후보로 계속 시도합니다.")

            if not done_for_source:
                search_limit += max_results

        if not done_for_source:
            print(f"  저장 가능한 논문을 찾지 못했습니다: {last_error}")

    OUTPUT_JSON.write_text(
        json.dumps({"keyword": keyword, "count": len(successful_records), "papers": successful_records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"성공한 논문만 저장: '{OUTPUT_JSON}'")

    print(f"\n완료. {success}/{len(REQUIRED_SOURCES)} 소스 저장됨")


if __name__ == "__main__":
    main()
