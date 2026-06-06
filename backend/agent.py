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

import re

translate_keyword_prompt = PromptTemplate(
    input_variables=["keyword"],
    template="""Translate the following search keyword into a highly relevant English academic term for querying research papers on ArXiv or Semantic Scholar.
If the keyword is already in English, return it as is.
Return ONLY the English keyword without any explanation, markdown, or quotes.

Keyword: {keyword}"""
)
translate_keyword_chain = translate_keyword_prompt | llm | parser

def translate_keyword_to_english(keyword: str) -> str:
    if not keyword or not keyword.strip():
        return ""
    # 영문/숫자/기본 기호만 포함된 경우 바로 반환
    if re.match(r'^[\x00-\x7F]+$', keyword):
        return keyword.strip()
    try:
        translated = translate_keyword_chain.invoke({"keyword": keyword})
        return translated.strip()
    except Exception as e:
        print(f"Keyword translation error: {e}")
        return keyword.strip()


# 다중 라운드 검색어(Search Plan) 생성 프롬프트
generate_plan_prompt = PromptTemplate(
    input_variables=["keywords", "recent_history"],
    template="""You are an expert academic research assistant.
The user is interested in finding recent, impactful research papers based on the following keywords:
{keywords}

[User's Long-term Memory (Recently saved papers)]
{recent_history}

Your task is to generate a progressive 3-round search strategy to find the best papers on ArXiv or Semantic Scholar.
IMPORTANT: The user has already read the papers listed in the Long-term Memory. DO NOT generate search terms that will just find the exact same papers or identical methodologies. Instead, find novel approaches, opposing methodologies (contrasting approaches), or advanced follow-ups that push the boundary further. If the memory is empty, just proceed with normal expansions.

- Round 1 (Core): Specific academic terms based exactly on the user's keywords, but aiming for fresh papers not in the memory. (max 3 terms)
- Round 2 (Trend/Pain point): Search terms focusing on the latest trends, bottlenecks, or pain points related to the keywords (e.g., if keywords are RAG, terms could be "hallucination mitigation in RAG"). (max 4 terms)
- Round 3 (Broad/Application): Broader methodologies, applications, or combinations with other fields. (max 4 terms)

Return ONLY a valid JSON object matching the exact structure below, without any markdown formatting, backticks, or comments.
{{
    "round_1": ["term1", "term2"],
    "round_2": ["term3", "term4"],
    "round_3": ["term5", "term6"]
}}
"""
)
generate_search_plan_chain = generate_plan_prompt | llm | parser

# 검색 실패 시 복구(Self-Correction) 프롬프트
fallback_prompt = PromptTemplate(
    input_variables=["failed_terms", "reason", "recent_history"],
    template="""You are an academic search agent trying to find research papers.
You recently searched for the following terms but failed to find enough relevant papers.
Failed terms: {failed_terms}
Reason for failure: {reason}

[User's Long-term Memory (Recently saved papers)]
{recent_history}

Suggest 3 new, alternative search queries that are related but take a slightly broader or different perspective to improve the chances of finding relevant academic papers. Make sure they don't overlap with the methodologies already seen in the user's Long-term Memory.
Return ONLY a valid JSON array of strings, without any markdown formatting or comments.
[
    "new term 1",
    "new term 2",
    "new term 3"
]
"""
)
generate_fallback_chain = fallback_prompt | llm | parser
# abstract mode: abstract-only academic summary.
translate_prompt = PromptTemplate(
    input_variables=["abstract", "user_keywords", "agent_insight"],
    template="""다음 논문 초록을 번역하고 요약하라.

[내부 참고 자료 - 절대 출력에 포함하지 마라]
- 사용자 관심사: {user_keywords}
- 에이전트의 선정 이유 (한국어로 자연스럽게 풀어 쓰되, 이 원문 텍스트를 그대로 복사하지 마라): {agent_insight}

요구사항:
- 출력은 반드시 아래 두 섹션만 사용하라.
- [내부 참고 자료] 섹션의 텍스트는 단 한 글자도 출력에 그대로 복사하지 마라.

[에이전트 브리핑]
사용자님을 부르며 대화체로 2~3줄 작성하라.
위의 [내부 참고 자료]를 참고하여, 이 논문이 사용자의 관심사와 어떻게 연결되는지, 어떤 점에서 가치가 있는지 한국어로 자연스럽게 설명하라.
절대로 'Agent Insight:', 'agent_insight', '내부 참고 자료' 등의 문구나 영어 원문을 출력에 포함시키지 마라.

[요약]
정확히 2~3줄로 작성하라.
연구 문제, 방법론, 핵심 결과, 이론적 기여 중 초록에서 확인 가능한 내용을 우선 포함하라.
전공자도 내용이 손상되지 않되, 비전공자도 흐름을 따라갈 수 있는 수준으로 작성하라.
학술 개념어가 처음 등장할 때는 괄호 안에 한 줄 이내로 뜻을 병기하라. 단, 인명·모델명 등 고유명사는 풀이하지 않는다.
"좋다", "유용하다" 같은 모호한 표현은 피하라.
초록에 없는 내용은 추측하지 마라.

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

# 에이전트 전용 비판적 필터링 체인 (Critic & Filtering)
critic_prompt = PromptTemplate(
    input_variables=["keyword", "title", "abstract"],
    template="""You are a strict, critical academic research agent.
Your task is to evaluate if a research paper is genuinely relevant to the user's intended research field and keyword.
Users often search for terms in IT/AI fields, but search results might return papers from completely unrelated fields (like agriculture, medicine, biology) that just happen to use the same acronym or word.

Evaluate the paper strictly based on the following criteria:
1. Is the academic context (field of study) relevant to the user's keyword? (e.g., if keyword is "Apple", reject agriculture papers. If "RAG", reject unrelated chemistry biology papers).
2. Is it a dataset paper or a simple review/survey without novel methodology? (If yes, reject if the user wants novel research).

Instructions:
- If the paper is NOT genuinely relevant to the core context of the user's keyword, return ONLY the word `IRRELEVANT`.
- If the paper is relevant and high-quality, return `RELEVANT` on the first line, and on the second line provide a concise 1-sentence "Agent Insight" explaining why this paper is valuable for the user.

[Keyword]
{keyword}

[Paper Title]
{title}

[Paper Abstract]
{abstract}"""
)
critic_chain = critic_prompt | llm | parser


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
    input_variables=["abstract", "body", "extracted", "user_keywords", "agent_insight"],
    template="""다음 논문을 요약하고 비판적으로 분석하라.
초록은 배경 참고용으로만 사용하고, 요약의 중심 근거는 PDF 본문에서 초록을 제외한 나머지 내용으로 삼아라.

[내부 참고 자료 - 절대 출력에 포함하지 마라]
- 사용자 관심사: {user_keywords}
- 에이전트의 선정 이유 (한국어로 자연스럽게 풀어 쓰되, 이 원문 텍스트를 그대로 복사하지 마라): {agent_insight}

출력 형식은 반드시 아래 세 섹션만 사용하라.
- [내부 참고 자료] 섹션의 텍스트는 단 한 글자도 출력에 그대로 복사하지 마라.

[에이전트 브리핑]
사용자님을 부르며 대화체로 2~3줄 작성하라.
위의 [내부 참고 자료]를 참고하여, 이 논문이 사용자의 관심사 측면에서 어떤 가치가 있는지 한국어로 자연스럽게 설명하라.
절대로 'Agent Insight:', 'agent_insight', '내부 참고 자료' 등의 문구나 영어 원문을 출력에 포함시키지 마라.

[요약]
4~5줄로 작성하라.
연구 문제 → 방법론 → 주요 정리 또는 핵심 결과 → 수치 검증 → 학문적 의의 순으로 서술하라.
수학적 모델과 핵심 개념이 논문에 등장하면 명확히 포함하라.
단순 설명이 아니라 논문의 이론적 기여를 강조하라.
전공자도 내용이 손상되지 않되, 비전공자도 흐름을 따라갈 수 있는 수준으로 작성하라.
학술 개념어가 처음 등장할 때는 괄호 안에 한 줄 이내로 뜻을 병기하라. 단, 인명·모델명 등 고유명사는 풀이하지 않는다.
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
    input_variables=["text", "extracted", "user_keywords", "agent_insight"],
    template="""다음 논문을 요약하고 비판적으로 분석하라.

[내부 참고 자료 - 절대 출력에 포함하지 마라]
- 사용자 관심사: {user_keywords}
- 에이전트의 선정 이유 (한국어로 자연스럽게 풀어 쓰되, 이 원문 텍스트를 그대로 복사하지 마라): {agent_insight}

출력 형식은 반드시 아래 세 섹션만 사용하라.
- [내부 참고 자료] 섹션의 텍스트는 단 한 글자도 출력에 그대로 복사하지 마라.

[에이전트 브리핑]
사용자님을 부르며 대화체로 2~3줄 작성하라.
위의 [내부 참고 자료]를 참고하여, 이 논문이 사용자의 관심사 측면에서 어떤 가치가 있는지 한국어로 자연스럽게 설명하라.
절대로 'Agent Insight:', 'agent_insight', '내부 참고 자료' 등의 문구나 영어 원문을 출력에 포함시키지 마라.

[요약]
5~7줄로 작성하라.
연구 문제 → 방법론 → 주요 정리 → 수치 검증 → 학문적 의의 순으로 서술하라.
수학적 모델과 핵심 개념을 명확히 포함하라.
단순 설명이 아니라 논문의 이론적 기여를 강조하라.
전공자도 내용이 손상되지 않되, 비전공자도 흐름을 따라갈 수 있는 수준으로 작성하라.
학술 개념어가 처음 등장할 때는 괄호 안에 한 줄 이내로 뜻을 병기하라. 단, 인명·모델명 등 고유명사는 풀이하지 않는다.
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


def translate_abstract(abstract: str, user_keywords: str = "", agent_insight: str = "") -> str:
    if not abstract:
        return ""
    return translate_chain.invoke({
        "abstract": abstract,
        "user_keywords": user_keywords,
        "agent_insight": agent_insight
    })


def summarize_body(abstract: str, body_text: str, user_keywords: str = "", agent_insight: str = "") -> str:
    extracted = extract_chain.invoke({"text": body_text[:5000]})
    return body_chain.invoke({
        "abstract": abstract,
        "body": body_text[:10000],
        "extracted": extracted,
        "user_keywords": user_keywords,
        "agent_insight": agent_insight
    })


def summarize_full(full_text: str, user_keywords: str = "", agent_insight: str = "") -> str:
    extracted = extract_chain.invoke({"text": full_text[:5000]})
    return full_chain.invoke({
        "text": full_text,
        "extracted": extracted,
        "user_keywords": user_keywords,
        "agent_insight": agent_insight
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