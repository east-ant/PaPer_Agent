import os
from dotenv import load_dotenv
from openai import OpenAI
from config import settings

load_dotenv()

client = OpenAI(api_key=settings.openai_api_key)

# 1. 초록 한글 번역
def translate_abstract(abstract: str) -> str:
    if not abstract:
        return ""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "학술 논문 초록을 자연스러운 한국어로 번역해줘. 번역문만 출력해."},
            {"role": "user", "content": abstract}
        ]
    )
    return response.choices[0].message.content

# 2. 논문 분석 요약
def analyze_paper(title: str, abstract: str, keyword: str) -> str:
    if not abstract:
        abstract = title
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """너는 학술 논문 분석 에이전트야.
관련 있으면 아래 형식으로 답해줘.

[주제] 논문 핵심 주제 한 줄
- 핵심 요약: 논문 핵심 내용 2~3줄
- 시사점: 이 연구의 의의 1줄

관련 없으면 '관련없음' 만 출력해줘."""
            },
            {
                "role": "user",
                "content": f"키워드: {keyword}\n제목: {title}\n초록: {abstract}"
            }
        ]
    )
    return response.choices[0].message.content

def is_relevant(result: str) -> bool:
    return "관련없음" not in result