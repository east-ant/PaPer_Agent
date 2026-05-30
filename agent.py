import io
import ssl
import urllib.request

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pypdf import PdfReader

from config import settings

load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
)

parser = StrOutputParser()


# abstract mode: abstract-only academic summary.
translate_prompt = PromptTemplate(
    input_variables=["abstract"],
    template="""다음 논문 초록을 요약하라.

요구사항:
- 출력은 반드시 [요약] 섹션만 사용하라.
- [요약]은 정확히 2줄로 작성하라.
- 연구 문제, 방법론, 핵심 결과, 이론적 기여 중 초록에서 확인 가능한 내용을 우선 포함하라.
- 전공자도 내용이 손상되지 않되, 비전공자도 흐름을 따라갈 수 있는 수준으로 작성하라.
- 학술 개념어가 처음 등장할 때는 괄호 안에 한 줄 이내로 뜻을 병기하라. 단, 인명·모델명 등 고유명사는 풀이하지 않는다. 같은 개념이 재등장할 때는 풀이 없이 용어만 사용하라.
- "좋다", "유용하다" 같은 모호한 표현은 피하라.
- 초록에 없는 내용은 추측하지 마라.

[초록]
{abstract}""",
)
translate_chain = translate_prompt | llm | parser


# relevance analysis chain.
analyze_prompt = PromptTemplate(
    input_variables=["keyword", "title", "abstract"],
    template="""너는 학술 논문 분석 에이전트다.
아래 논문이 사용자의 키워드와 관련 있는지 판단하라.

출력 형식:
- 관련 있으면 첫 줄에 RELEVANT를 출력하고, 다음 줄부터 아래 형식으로 한국어로 작성하라.
  [주제] 논문의 핵심 주제 한 줄
  - 핵심 요약: 논문 핵심 내용 2~3줄
  - 시사점: 연구자에게 의미 있는 이론적 또는 방법론적 기여 1줄
- 관련 없으면 IRRELEVANT만 출력하라.

[키워드]
{keyword}

[제목]
{title}

[초록]
{abstract}""",
)
analyze_chain = analyze_prompt | llm | parser


# step 1: extract structured information before review-style summarization.
extract_prompt = PromptTemplate(
    input_variables=["text"],
    template="""아래 논문 텍스트에서 다음 항목을 각각 한두 줄로 추출하라.
항목 외 다른 텍스트는 출력하지 마라.
논문에 명시되지 않은 내용은 추측하지 말고 "확인 불가"라고 적어라.

연구문제: 이 논문이 해결하려는 핵심 문제
방법론: 사용한 주요 방법, 모델, 정리, 실험 또는 분석 절차
핵심개념: PDE, chemotaxis, Lyapunov function 등 중요한 전문 개념
주요정리/결과: 논문의 핵심 이론 결과 또는 실험 결과
수치검증: 수치 실험이나 검증이 있다면 그 역할
학문적의의: 이론적 또는 방법론적 기여
한계: 차원 제한성, 가정의 일반성, 확장 가능성 측면의 한계
후속연구: 구체적인 확장 방향

[논문 텍스트]
{text}""",
)
extract_chain = extract_prompt | llm | parser


# body mode: body-centered review, excluding the abstract as the main source.
body_prompt = PromptTemplate(
    input_variables=["abstract", "body", "extracted"],
    template="""다음 논문을 요약하고 비판적으로 분석하라.
초록은 배경 참고용으로만 사용하고, 요약의 중심 근거는 PDF 본문에서 초록을 제외한 나머지 내용으로 삼아라.

출력 형식은 반드시 아래 두 섹션만 사용하라.

[요약]
4~5줄로 작성하라.
연구 문제 → 방법론 → 주요 정리 또는 핵심 결과 → 수치 검증 → 학문적 의의 순으로 서술하라.
수학적 모델과 핵심 개념이 논문에 등장하면 명확히 포함하라.
단순 설명이 아니라 논문의 이론적 기여를 강조하라.
전공자도 내용이 손상되지 않되, 비전공자도 흐름을 따라갈 수 있는 수준으로 작성하라.
학술 개념어가 처음 등장할 때는 괄호 안에 한 줄 이내로 뜻을 병기하라. 단, 인명·모델명 등 고유명사는 풀이하지 않는다. 같은 개념이 재등장할 때는 풀이 없이 용어만 사용하라.
"좋다", "유용하다" 같은 모호한 표현은 피하라.

[비판적 분석]
2~3줄로 작성하라.
모델의 차원 제한성, 가정의 일반성, 확장 가능성을 논하라.
후속 연구 방향을 구체적으로 제시하라.
논문에 없는 내용을 단정하지 말고, 텍스트에서 확인 가능한 범위 안에서 분석하라.

[추출 정보]
{extracted}

[초록 - 참고용]
{abstract}

[PDF 본문]
{body}""",
)
body_chain = body_prompt | llm | parser


# full mode: full-paper academic review.
full_prompt = PromptTemplate(
    input_variables=["text", "extracted"],
    template="""다음 논문을 요약하고 비판적으로 분석하라.

출력 형식은 반드시 아래 두 섹션만 사용하라.

[요약]
5~7줄로 작성하라.
연구 문제 → 방법론 → 주요 정리 → 수치 검증 → 학문적 의의 순으로 서술하라.
수학적 모델과 핵심 개념을 명확히 포함하라.
단순 설명이 아니라 논문의 이론적 기여를 강조하라.
전공자도 내용이 손상되지 않되, 비전공자도 흐름을 따라갈 수 있는 수준으로 작성하라.
학술 개념어가 처음 등장할 때는 괄호 안에 한 줄 이내로 뜻을 병기하라. 단, 인명·모델명 등 고유명사는 풀이하지 않는다. 같은 개념이 재등장할 때는 풀이 없이 용어만 사용하라.
"좋다", "유용하다" 같은 모호한 표현은 피하라.

[비판적 분석]
2~3줄로 작성하라.
모델의 차원 제한성, 가정의 일반성, 확장 가능성을 논하라.
후속 연구 방향을 구체적으로 제시하라.
논문에 없는 내용을 단정하지 말고, 텍스트에서 확인 가능한 범위 안에서 분석하라.

[추출 정보]
{extracted}

[논문 전체]
{text}""",
)
full_chain = full_prompt | llm | parser


def translate_abstract(abstract: str) -> str:
    if not abstract:
        return ""
    return translate_chain.invoke({"abstract": abstract})


def summarize_body(abstract: str, body_text: str) -> str:
    extracted = extract_chain.invoke({"text": body_text[:5000]})
    return body_chain.invoke({
        "abstract": abstract,
        "body": body_text[:10000],
        "extracted": extracted,
    })


def summarize_full(full_text: str) -> str:
    extracted = extract_chain.invoke({"text": full_text[:5000]})
    return full_chain.invoke({
        "text": full_text,
        "extracted": extracted,
    })


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
        "abstract": abstract,
    })


def is_relevant(result: str) -> bool:
    return result.strip().upper().startswith("RELEVANT")