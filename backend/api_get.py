import io
import json
import re
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone

import feedparser
import numpy as np
import pypdfium2 as pdfium
try:
    import pymysql
except ImportError:
    pymysql = None
from rapidocr_onnxruntime import RapidOCR
from dotenv import load_dotenv

# 스크립트를 직접 실행할 때 상위 폴더 모듈 import가 가능하도록 경로를 추가합니다.
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from config import settings

load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ==================== 엔드 포인트 설정 ====================
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = BASE_DIR / "collected_papers.json"
OUTPUT_DIR = BASE_DIR / "translated_outputs"
REQUIRED_SOURCES = ["arXiv", "Crossref", "Semantic Scholar", "CORE"]
OCR_RENDER_SCALE = 1.5
TOP_N_CUTOFF = 30
PDF_PROBE_TIMEOUT = 8
PDF_PROBE_RETRIES = 2
PDF_PROBE_BYTES = 8192
METADATA_TIMEOUT = 15
METADATA_RETRIES = 3
ARXIV_TIMEOUT = 30
ARXIV_RETRIES = 5
HISTORY_JSON = BASE_DIR / "processed_papers.json"


# ==================== 논문 데이터 정리  ====================

# 리스트 형태로 맞춰주는 함수
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



# 카테고리 값을 하나로 합치는 함수
def _merge_categories(*groups):
    merged = []
    for group in groups:
        for item in _as_list(group):
            text = _normalize_category_name(item)
            if text and text not in merged:
                merged.append(text)
    return merged



# 카테고리 이름을 정규화하는 함수
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



# 문자열을 SQL/JSON에 넣기 좋게 바꾸는 함수
def _json_sql_literal(value):
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("'", "''")



# 카테고리 이름을 텍스트 목록으로 바꾸는 함수
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



# 논문 초록 텍스트를 정리하는 함수
def _normalize_abstract_text(value):
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text



# OCR 결과에서 핵심 단어를 뽑는 함수
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



# 제목 값을 문자열로 바꾸는 함수
def _title_to_text(title):
    if isinstance(title, list):
        return " ".join([str(part) for part in title if part])
    return str(title or "")



# 파일명으로 쓰기 좋게 바꾸는 함수
def sanitize_filename(name: str, max_len: int = 120) -> str:
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "untitled")[:max_len]



# 제목 비교용 문자열로 정리하는 함수
def normalize_title(title):
    if not title:
        return ""
    return " ".join(_title_to_text(title).lower().strip().split())


# 검색어를 쉼표 기준으로 나누어 AND 조건으로 쓰기 좋게 정리하는 함수
def parse_search_terms(keyword_text: str) -> list[str]:
    terms = []
    for part in re.split(r"[,，]", keyword_text or ""):
        term = part.strip().lower()
        if term:
            terms.append(term)
    return terms


# 논문이 모든 검색어를 포함하는지 확인하는 함수
def paper_matches_terms(paper: dict, terms: list[str]) -> bool:
    if not terms:
        return True

    searchable_parts = [
        _title_to_text(paper.get("title")),
        _normalize_abstract_text(paper.get("abstract") or paper.get("summary")),
        " ".join(_as_list(paper.get("categories", []))),
        " ".join(_as_list(paper.get("subject", []))),
        " ".join(_as_list(paper.get("subjects", []))),
        " ".join(_as_list(paper.get("topics", []))),
        " ".join(_as_list(paper.get("authors", []))),
    ]
    searchable_text = " ".join(part for part in searchable_parts if part).lower()
    for term in terms:
        escaped = re.escape(term).replace(r"\ ", r"\s+")
        pattern = rf"(?<!\w){escaped}(?!\w)"
        if not re.search(pattern, searchable_text, flags=re.IGNORECASE):
            return False
    return True


# 이전에 성공적으로 저장한 논문을 기록에서 읽는 함수
def load_processed_history() -> set[str]:
    if not HISTORY_JSON.exists():
        return set()

    try:
        data = json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
    except Exception:
        return set()

    history = set()
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        paper_id = str(item.get("paper_id") or "").strip()
        title = normalize_title(item.get("title"))
        if paper_id:
            history.add(f"id:{paper_id}")
        if title:
            history.add(f"title:{title}")
    return history


# 성공한 논문을 기록에 추가하는 함수
def append_processed_history(items: list[dict]) -> None:
    existing = []
    if HISTORY_JSON.exists():
        try:
            loaded = json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception:
            existing = []

    seen_keys = set()
    normalized_existing = []
    for item in existing:
        if not isinstance(item, dict):
            continue
        paper_id = str(item.get("paper_id") or "").strip()
        title = normalize_title(item.get("title"))
        key = f"id:{paper_id}" if paper_id else f"title:{title}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        normalized_existing.append(item)

    for item in items:
        paper_id = str(item.get("paper_id") or "").strip()
        title = normalize_title(item.get("title"))
        key = f"id:{paper_id}" if paper_id else f"title:{title}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        normalized_existing.append({
            "paper_id": paper_id,
            "title": item.get("title"),
            "source": item.get("source"),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        })

    HISTORY_JSON.write_text(json.dumps(normalized_existing, ensure_ascii=False, indent=2), encoding="utf-8")


# 이미 처리한 논문인지 확인하는 함수
def paper_seen_before(paper: dict, history: set[str]) -> bool:
    paper_id = str(paper.get("id") or paper.get("paperId") or "").strip()
    title = normalize_title(paper.get("title"))
    if paper_id and f"id:{paper_id}" in history:
        return True
    if title and f"title:{title}" in history:
        return True
    return False



# 발행일을 비교 가능한 값으로 바꾸는 함수
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



# 최신순으로 정렬하는 함수
def sort_papers_by_recency(papers):
    return sorted(
        papers,
        key=lambda paper: (
            _parse_published_value(paper.get("published") or paper.get("year") or paper.get("publishedDate")),
            normalize_title(paper.get("title")),
        ),
        reverse=True,
    )



# 저자 이름을 문자열로 정리하는 함수
def normalize_author(author):
    if isinstance(author, dict):
        return str(author.get("name", "")).strip()
    if isinstance(author, str):
        return author.strip()
    return ""



# 제목 기준으로 중복 제거하는 함수
def remove_duplicates(papers):
    seen = set()
    result = []
    for paper in papers:
        title = normalize_title(paper.get("title"))
        if title and title not in seen:
            seen.add(title)
            result.append(paper)
    return result


# DB 연결을 준비하는 함수
def _get_db_connection():
    # .env에서 DB 접속 정보를 읽어옵니다.
    if pymysql is None:
        print("pymysql 패키지가 없어 DB 저장을 건너뜁니다.")
        return None

    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    if not db_host or not db_user or not db_name:
        return None

    try:
        return pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            charset="utf8mb4",
        )
    except Exception as error:
        print(f"DB 연결 실패로 저장을 건너뜁니다: {error}")
        return None


# DB 테이블이 없으면 만드는 함수
def _init_db():
    conn = _get_db_connection()
    if conn is None:
        print("DB 설정이 없어 저장을 건너뜁니다.")
        return False

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            arxiv_id VARCHAR(100) UNIQUE,
            title VARCHAR(500),
            abstract TEXT,
            summary TEXT,
            category VARCHAR(100),
            published DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            authors TEXT,
            citations INT DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    return True


# DB에 선택된 논문을 저장하는 함수
def _save_paper_to_db(paper: dict, extracted_text: str):
    conn = _get_db_connection()
    if conn is None:
        return False

    cursor = conn.cursor()
    paper_id = paper.get("id") or paper.get("paperId") or sanitize_filename(_title_to_text(paper.get("title")) or "untitled")
    category_list = paper.get("categories") or paper.get("fieldsOfStudy") or paper.get("subject") or paper.get("subjects") or []
    category = category_list[0] if isinstance(category_list, list) and category_list else None
    published_value = _parse_published_value(paper.get("published") or paper.get("year") or paper.get("publishedDate"))
    if published_value == datetime.min:
        published_value = None

    try:
        authors_val = paper.get("authors")
        if isinstance(authors_val, list):
            authors_str = ", ".join(authors_val[:3])
        else:
            authors_str = str(authors_val or "")
        citations_val = paper.get("citationCount") or paper.get("citations") or 0

        cursor.execute("""
            INSERT IGNORE INTO papers (arxiv_id, title, abstract, summary, category, published, authors, citations)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(paper_id),
            _title_to_text(paper.get("title"))[:500],
            _normalize_abstract_text(paper.get("abstract") or paper.get("summary")),
            extracted_text[:5000],
            str(category)[:100] if category else None,
            published_value,
            authors_str,
            citations_val
        ))
        conn.commit()
        return True
    except Exception as error:
        print(f"DB 저장 실패: {error}")
        return False
    finally:
        conn.close()


# 각 소스 API를 병렬로 호출하는 함수
def fetch_all_source_candidates(keyword: str, limit: int, semantic_key: str, core_key: str) -> list[dict]:
    combined = []
    with ThreadPoolExecutor(max_workers=len(REQUIRED_SOURCES)) as executor:
        future_map = {
            executor.submit(fetch_source_candidates, source, keyword, limit, semantic_key, core_key): source
            for source in REQUIRED_SOURCES
        }
        ordered_results = {source: [] for source in REQUIRED_SOURCES}
        for future in as_completed(future_map):
            source = future_map[future]
            try:
                ordered_results[source] = future.result() or []
            except Exception as error:
                print(f"{source} 병렬 호출 실패: {error}")

    # 결과를 임시로 한 리스트에 모으는 함수
    for source in REQUIRED_SOURCES:
        combined.extend(ordered_results.get(source, []))
    return combined


# PDF 링크를 먼저 확인해서 OCR 가능한 후보만 남기는 함수
def resolve_pdf_candidate(paper: dict) -> str:
    source = paper.get("source", "")
    link = (paper.get("link") or "").replace("&amp;", "&")
    doi = paper.get("doi") or paper.get("DOI")

    if source == "arXiv":
        return resolve_pdf_url(link)
    if source == "Crossref":
        return crossref_pdf_from_doi(link if "doi.org/" in link else f"https://doi.org/{doi}" if doi else link)
    if source == "Semantic Scholar":
        open_pdf = paper.get("openAccessPdf") or {}
        open_pdf_url = open_pdf.get("url")
        if open_pdf_url:
            return open_pdf_url

        external_ids = paper.get("externalIds") or {}
        arxiv_id = external_ids.get("ArXiv")
        doi_id = external_ids.get("DOI") or external_ids.get("doi") or paper.get("doi") or paper.get("DOI")
        if arxiv_id:
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        if doi_id:
            try:
                return crossref_pdf_from_doi(f"https://doi.org/{doi_id}")
            except Exception:
                pass

        if link:
            try:
                return resolve_pdf_url(link)
            except Exception:
                pass

        paper_id = paper.get("paperId")
        if paper_id:
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
            doi_id = external_ids.get("DOI") or external_ids.get("doi")
            if arxiv_id:
                return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            if doi_id:
                try:
                    return crossref_pdf_from_doi(f"https://doi.org/{doi_id}")
                except Exception:
                    pass

            api_link = obj.get("url") or link
            if api_link:
                try:
                    return resolve_pdf_url(api_link)
                except Exception:
                    pass

        return semantic_pdf_fallback(paper)
    if source == "CORE":
        if doi and not link:
            link = f"https://doi.org/{doi}"
        return resolve_pdf_url(link)

    raise ValueError("Unsupported source")


# ==================== 논문 파일 요청 및 PDF 해석 ====================

# HTTP 응답 바이트를 가져오는 함수
def request_bytes(
    url: str,
    timeout: int = 40,
    retries: int = 3,
    max_bytes: int | None = None,
) -> tuple[bytes, str]:
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read() if max_bytes is None else response.read(max_bytes)
                return data, response.headers.get("Content-Type", "")
        except Exception as error:
            last_error = error
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_error



# arXiv abs 링크를 PDF 링크로 바꾸는 함수
def arxiv_abs_to_pdf(url: str) -> str:
    match = re.match(r"^https?://arxiv\.org/abs/([^?#]+)", url)
    if match:
        return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    return url



# HTML 안에서 PDF 링크를 찾는 함수
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



# 실제 PDF URL을 찾아내는 함수
def resolve_pdf_url(link: str) -> str:
    link = (link or "").replace("&amp;", "&")
    candidate = arxiv_abs_to_pdf(link)

    for test_url in [candidate, link]:
        if not test_url:
            continue
        data, content_type = request_bytes(
            test_url,
            timeout=PDF_PROBE_TIMEOUT,
            retries=PDF_PROBE_RETRIES,
            max_bytes=PDF_PROBE_BYTES,
        )
        if "pdf" in content_type.lower() or data[:5] == b"%PDF-":
            return test_url

        if "html" in content_type.lower() or data.startswith(b"<"):
            for pdf_url in find_pdf_links_in_html(test_url, data):
                pdf_data, pdf_type = request_bytes(
                    pdf_url,
                    timeout=PDF_PROBE_TIMEOUT,
                    retries=PDF_PROBE_RETRIES,
                    max_bytes=PDF_PROBE_BYTES,
                )
                if "pdf" in pdf_type.lower() or pdf_data[:5] == b"%PDF-":
                    return pdf_url

    raise ValueError("No direct PDF found")



# PDF를 OCR로 읽어서 텍스트로 바꾸는 함수
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



# Crossref DOI에서 PDF 링크를 찾는 함수
def crossref_pdf_from_doi(doi_url: str) -> str:
    if "doi.org/" not in doi_url:
        raise ValueError("Not a DOI link")

    doi = doi_url.split("doi.org/", 1)[1]
    api = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    data, _ = request_bytes(api, timeout=METADATA_TIMEOUT, retries=METADATA_RETRIES, max_bytes=16384)
    obj = json.loads(data.decode("utf-8", errors="ignore"))
    message = obj.get("message", {})

    for item in message.get("link", []) or []:
        url = item.get("URL") or item.get("url")
        content_type = (item.get("content-type") or "").lower()
        if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
            return url

    return resolve_pdf_url(doi_url)



# Semantic Scholar 링크에서 PDF 링크를 찾는 함수
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
    data, _ = request_bytes(api, timeout=METADATA_TIMEOUT, retries=METADATA_RETRIES, max_bytes=16384)
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


# Semantic Scholar 후보에서 PDF를 더 넓게 찾아보는 함수
def semantic_pdf_fallback(paper: dict) -> str:
    external_ids = paper.get("externalIds") or {}
    doi = external_ids.get("DOI") or external_ids.get("doi") or paper.get("doi") or paper.get("DOI")
    arxiv_id = external_ids.get("ArXiv") or external_ids.get("arXiv")
    link = (paper.get("link") or paper.get("url") or "").replace("&amp;", "&")

    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    if doi:
        try:
            return crossref_pdf_from_doi(f"https://doi.org/{doi}")
        except Exception:
            pass

    if link:
        try:
            return resolve_pdf_url(link)
        except Exception:
            pass

    raise ValueError("No open access PDF in Semantic Scholar metadata")


# ==================== 논문 API 호출 ====================

# arXiv 논문 검색 함수
def arxiv_search(query, max_results):
    url = "https://export.arxiv.org/api/query"
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    request = urllib.request.Request(
        f"{url}?{params}",
        headers={"User-Agent": "Mozilla/5.0 (compatible; PaperCollector/1.0)"},
    )

    try:
        for attempt in range(ARXIV_RETRIES):
            try:
                with urllib.request.urlopen(request, timeout=ARXIV_TIMEOUT) as response:
                    feed = feedparser.parse(response.read())
                break
            except urllib.error.HTTPError as error:
                if error.code in (429, 503) and attempt < ARXIV_RETRIES - 1:
                    time.sleep(5.0 * (attempt + 1))
                    continue
                raise

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
                "abstract": _normalize_abstract_text(entry.get("summary")),
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



# Crossref 논문 검색 함수
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
                "abstract": _normalize_abstract_text(item.get("abstract")),
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



# Semantic Scholar 논문 검색 함수
def semantic_search(query, api_key, max_results):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = urllib.parse.urlencode({
        "query": query,
        "limit": max_results,
        "fields": "title,abstract,year,publicationDate,authors,url,fieldsOfStudy,s2FieldsOfStudy,venue,journal,publicationTypes,citationCount,influentialCitationCount,openAccessPdf,externalIds",
    })
    headers = {"x-api-key": api_key} if api_key and "your_" not in api_key else {}
    request = urllib.request.Request(f"{url}?{params}", headers=headers)
    
    data = None
    try:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = json.loads(response.read())
                break
            except urllib.error.HTTPError as error:
                if error.code in (429, 503) and attempt < 2:
                    import time
                    time.sleep(3.0 * (attempt + 1))
                    continue
                raise
        
        if not data:
            return []

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
                "published": item.get("publicationDate") or item.get("year") or "",
                "link": item.get("url"),
                "paperId": item.get("paperId"),
                "abstract": _normalize_abstract_text(item.get("abstract")),
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



# CORE 논문 검색 함수
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
                "abstract": _normalize_abstract_text(item.get("abstract") or item.get("description")),
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


# ==================== 논문 후보 정리 ====================

# 소스별로 논문을 묶는 함수
def group_by_source(papers: list[dict]) -> dict[str, list[dict]]:
    grouped = {source: [] for source in REQUIRED_SOURCES}
    for paper in papers:
        source = paper.get("source")
        if source in grouped:
            grouped[source].append(paper)
    for source in grouped:
        grouped[source] = sort_papers_by_recency(grouped[source])
    return grouped



# 소스별 후보를 가져오는 함수
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


# 쉼표로 받은 키워드를 API 검색용 문자열로 정리하는 함수
def build_api_query_text(keyword_text: str) -> str:
    terms = parse_search_terms(keyword_text)
    return " ".join(terms) if terms else keyword_text.strip()


# ==================== 논문 컬럼 정리 ====================

# 논문 텍스트를 소스별로 뽑는 함수
def source_text(paper: dict, ocr_engine: RapidOCR, pdf_url: str | None = None) -> tuple[str, str]:
    source = paper.get("source", "")
    link = (paper.get("link") or "").replace("&amp;", "&")

    if source == "arXiv":
        pdf_url = pdf_url or resolve_pdf_url(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    if source == "Crossref":
        pdf_url = pdf_url or crossref_pdf_from_doi(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    if source == "Semantic Scholar":
        pdf_url = pdf_url or semantic_pdf_from_link(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    if source == "CORE":
        pdf_url = pdf_url or resolve_pdf_url(link)
        return extract_pdf_text_ocr(pdf_url, ocr_engine), pdf_url

    raise ValueError("Unsupported source")



# OCR 저장용 컬럼을 만드는 함수
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
        "abstract": paper.get("abstract") or paper.get("summary"),
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



# OCR 결과를 파일로 저장하는 함수
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


# ==================== 실행 흐름 ====================

# 전체 수집을 실행하는 함수
def main() -> None:
    keyword = input("검색 키워드 입력: ").strip()
    if not keyword:
        print("키워드를 입력해 주세요.")
        return

    search_terms = parse_search_terms(keyword)
    api_query_text = build_api_query_text(keyword)

    max_results_input = input("각 소스별 수집할 논문 개수 입력 (기본값 5): ").strip()
    try:
        max_results = int(max_results_input) if max_results_input else 5
    except ValueError:
        max_results = 5
        print(f"잘못된 입력, 기본값 {max_results}를 사용합니다.")

    semantic_key = settings.semantic_scholar_api_key
    core_key = settings.core_api_key
    print(f"\n키워드: '{keyword}', 각 소스별 개수: {max_results}")
    if len(search_terms) > 1:
        print(f"AND 검색어: {', '.join(search_terms)}")
    print("-" * 60)
    print("API에서 링크 후보를 가져와 바로 OCR 시도합니다.")
    print(f"OCR 설정: 전체 페이지, 렌더 스케일 {OCR_RENDER_SCALE}")

    print("\n" + "=" * 60)
    print("OCR 추출 시작...")
    print("=" * 60)

    # 7. DB 저장을 위한 테이블 준비
    _init_db()

    ocr_engine = RapidOCR()
    successful_records = []
    saved_db_count = 0
    processed_history = load_processed_history()

    success = 0

    # 1. API 병렬 호출: AND 후보가 부족하면 중복 없이 더 넓게 재수집합니다
    fetch_limit = max(TOP_N_CUTOFF, max_results * 5)
    fetch_limit_max = max(fetch_limit, 200)
    fetch_step = max(10, max_results * 5)
    raw_candidates = []
    seen_titles = set()

    round_index = 0
    while True:
        round_index += 1
        round_batch = fetch_all_source_candidates(api_query_text, fetch_limit, semantic_key, core_key)

        added_count = 0
        for paper in round_batch:
            if paper_seen_before(paper, processed_history):
                continue
            title_key = normalize_title(paper.get("title"))
            if not title_key or title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            raw_candidates.append(paper)
            added_count += 1

        and_count = len(remove_duplicates([paper for paper in raw_candidates if paper_matches_terms(paper, search_terms)]))
        print(f"RAW 수집 {round_index}차: 요청 {fetch_limit}, 신규 {added_count}, 누적 {len(raw_candidates)}, AND 누적 {and_count}")

        if and_count >= max_results:
            break
        if fetch_limit >= fetch_limit_max:
            break
        if added_count == 0 and fetch_limit >= TOP_N_CUTOFF:
            break

        fetch_limit = min(fetch_limit + fetch_step, fetch_limit_max)

    print(f"RAW 후보 {len(raw_candidates)}개")

    source_groups = group_by_source(raw_candidates)
    for source in REQUIRED_SOURCES:
        print(f"[{source}] 후보 {len(source_groups.get(source, []))}개")

    # 1-1. AND 조건 필터: 모든 검색어를 만족하는 후보만 남깁니다
    candidates = [paper for paper in raw_candidates if paper_matches_terms(paper, search_terms)]
    print(f"AND 필터 후 후보 {len(candidates)}개")

    # 2. 결과 임시 통합: 중복을 제거한 뒤 리스트로 한 번에 모읍니다
    dedup_and_candidates = remove_duplicates(candidates)
    print(f"DEDUP 후 후보 {len(dedup_and_candidates)}개")

    # 2-1. 키워드 정확도를 위해 최종 후보는 AND 통과 논문으로만 유지합니다
    candidates = dedup_and_candidates
    if len(candidates) < max_results:
        print(f"AND 엄격 모드: 요청 {max_results}개 대비 AND 후보가 {len(candidates)}개입니다.")

    # 3. 상위 N개만 컷: 최신순 기준으로 먼저 넓게 정렬하고 상위 후보만 남깁니다
    candidates = sort_papers_by_recency(candidates)
    candidates = candidates[:TOP_N_CUTOFF]

    if not candidates:
        print("후보가 없어 종료합니다.")
        return

    # 4. PDF 여부 체크: OCR 가능한 PDF가 있는 논문만 남깁니다
    pdf_candidates = []
    last_error = ""
    for paper in candidates:
        try:
            pdf_url = resolve_pdf_candidate(paper)
            paper_with_pdf = dict(paper)
            paper_with_pdf["resolved_pdf_url"] = pdf_url
            pdf_candidates.append(paper_with_pdf)
        except Exception as error:
            last_error = str(error)
            print(f"  PDF 없음/해결 실패: {_title_to_text(paper.get('title'))} ({error})")

    if not pdf_candidates:
        print(f"  PDF 가능한 후보를 찾지 못했습니다: {last_error}")
        return

    print(f"PDF after 후보 {len(pdf_candidates)}개")

    # 5. 최신순 정렬: PDF가 확인된 후보를 다시 최신순으로 정리합니다
    pdf_candidates = sort_papers_by_recency(pdf_candidates)

    # 6. limit 만큼 선택: 실패한 논문이 있으면 다음 후보로 메꿔서 저장 수량을 맞춥니다
    selected_candidates = pdf_candidates

    print(f"  최종 OCR 대상 {len(selected_candidates)}개를 선택했습니다.")
    for paper in selected_candidates:
        if success >= max_results:
            break
        print(f"  제목: {_title_to_text(paper.get('title'))}")
        try:
            text, used_link = source_text(paper, ocr_engine, pdf_url=paper.get("resolved_pdf_url"))
            output_path, payload = save_ocr_json(paper, text, used_link)
            successful_records.append(payload)
            print(f"  저장: {output_path.name}")
            processed_history.add(f"title:{normalize_title(paper.get('title'))}")

            # 7. DB 저장: 최종 선택된 논문만 DB에 넣습니다
            if _save_paper_to_db(paper, text):
                saved_db_count += 1
                print("  DB 저장 완료")

            success += 1
        except Exception as error:
            last_error = str(error)
            print(f"  실패: {error}")
            print("  다음 최신 후보로 계속 시도합니다.")

    if success < max_results:
        print(f"  목표 {max_results}개 중 {success}개만 저장했습니다.")

    if success == 0:
        print(f"  저장 가능한 논문을 찾지 못했습니다: {last_error}")
    else:
        print(f"  {success}개 저장 완료")

    OUTPUT_JSON.write_text(
        json.dumps({"keyword": keyword, "count": len(successful_records), "papers": successful_records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    append_processed_history(successful_records)
    print(f"성공한 논문만 저장: '{OUTPUT_JSON}'")

    print(f"\n완료. 총 {success}개 논문 저장됨")
    print(f"DB 저장된 논문 수: {saved_db_count}")


if __name__ == "__main__":
    main()
