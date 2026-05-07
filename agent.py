import os
import io
import ssl
import urllib.request
from pypdf import PdfReader
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config import settings

load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key
)

parser = StrOutputParser()

# 초록 번역 체인
translate_prompt = PromptTemplate(
    input_variables=["abstract"],
    template="학술 논문 초록을 자연스러운 한국어로 번역해줘. 번역문만 출력해.\n\n{abstract}"
)
translate_chain = translate_prompt | llm | parser

# 논문 관련성 분석 체인
analyze_prompt = PromptTemplate(
    input_variables=["keyword", "title", "abstract"],
    template="""너는 학술 논문 분석 에이전트야.
관련 있으면 아래 형식으로 답해줘.

[주제] 논문 핵심 주제 한 줄
- 핵심 요약: 논문 핵심 내용 2~3줄
- 시사점: 이 연구의 의의 1줄

관련 없으면 '관련없음' 만 출력해줘.

키워드: {keyword}
제목: {title}
초록: {abstract}"""
)
analyze_chain = analyze_prompt | llm | parser

# body 모드 체인
body_prompt = PromptTemplate(
    input_variables=["abstract", "body"],
    template="""너는 학술 논문 분석 전문가야.
아래 논문의 초록과 본문 일부를 읽고 핵심 내용을 한국어로 요약해줘.

[초록]
{abstract}

[본문 일부]
{body}

요약 형식:
[주제] 논문 핵심 주제 한 줄
- 핵심 내용: 2~3줄
- 결론: 1줄"""
)
body_chain = body_prompt | llm | parser

# full 모드 체인
full_prompt = PromptTemplate(
    input_variables=["text"],
    template="""너는 학술 논문 분석 전문가야.
아래 논문 전체를 읽고 핵심 내용을 한국어로 상세하게 요약해줘.

[논문 전체]
{text}

요약 형식:
[주제] 논문 핵심 주제 한 줄
- 연구 목적: 1~2줄
- 방법론: 1~2줄
- 핵심 결과: 2~3줄
- 결론 및 시사점: 1~2줄"""
)
full_chain = full_prompt | llm | parser


def translate_abstract(abstract: str) -> str:
    if not abstract:
        return ""
    return translate_chain.invoke({"abstract": abstract})


def summarize_body(abstract: str, body_text: str) -> str:
    return body_chain.invoke({
        "abstract": abstract,
        "body": body_text[:2500]
    })


def summarize_full(full_text: str) -> str:
    return full_chain.invoke({"text": full_text})


def read_paper_pdf(pdf_url: str, max_pages: int = 45) -> str:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=30, context=ctx).read()
        reader = PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages[:max_pages]:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        print(f"PDF 읽기 실패: {e}")
        return ""


def analyze_paper(title: str, abstract: str, keyword: str) -> str:
    if not abstract:
        abstract = title
    return analyze_chain.invoke({
        "keyword": keyword,
        "title": title,
        "abstract": abstract
    })


def is_relevant(result: str) -> bool:
    return "관련없음" not in result