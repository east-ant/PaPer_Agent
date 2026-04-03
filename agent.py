import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

llm = ChatAnthropic(
    model="claude-haiku-4-5",
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

prompt = PromptTemplate(
    input_variables=["title", "abstract", "keyword"],
    template="""
    너는 학술 논문 분석 에이전트야.
    
    사용자 관심 키워드: {keyword}
    논문 제목: {title}
    논문 내용: {abstract}
    
    1. 이 논문이 키워드와 관련 있는지 판단해줘. (관련있음/관련없음)
    2. 관련 있으면 아래 형식으로 요약해줘.
    
    [주제] 논문 핵심 주제 한 줄
    - 제목: 논문 제목
    - 핵심 요약: 논문 핵심 내용 2~3줄
    - 시사점: 이 연구의 의의 1줄
    
    관련 없으면 "관련없음" 만 출력해줘.
    """
)

chain = prompt | llm | StrOutputParser()

def analyze_paper(title: str, abstract: str, keyword: str) -> str:
    # Claude API 키 생기면 아래 주석 해제
    # result = chain.invoke({"title": title, "abstract": abstract, "keyword": keyword})
    # return result

    # 임시 테스트용 가짜 응답
    if keyword.lower() in title.lower() or keyword.lower() in abstract.lower():
        return f"""[주제] {title} 관련 연구
- 제목: {title}
- 핵심 요약: 키워드 '{keyword}'와 관련된 논문입니다.
- 시사점: 추후 Claude API 연동 시 자동 분석됩니다."""
    else:
        return "관련없음"

def is_relevant(result: str) -> bool:
    return "관련없음" not in result