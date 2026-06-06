import os
import sys
from pathlib import Path

# 경로 설정
WORKSPACE_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = WORKSPACE_ROOT / "backend"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent_runner import run_paper_agent
import json

def test_pipeline():
    print("[테스트 시작] 맞춤형 논문 에이전트 파이프라인 통합 테스트")
    keywords = ["RAG", "LLM Hallucination"]
    sources = ["arxiv"]
    user_email = "test@test.com" # 더미 사용자 이메일
    
    print(f"\n목표 설정: 키워드={keywords}, 목표 논문 수=1, 사용자={user_email}")
    
    print("\n에이전트가 탐색 계획을 세우고 논문을 수집 및 분석 중입니다. (약 30초~1분 소요될 수 있습니다...)")
    
    try:
        result = run_paper_agent(
            keywords=keywords,
            sources=sources,
            collect_count=1,
            user_email=user_email,
            language="ko",
            summary_length="abstract" # 테스트 속도를 위해 abstract 모드로 진행
        )
        
        print("\n" + "="*50)
        print("[테스트 완료]")
        
        papers = result.get('papers', [])
        print(f"수집된 논문 수: {len(papers)}")
        
        if papers:
            paper = papers[0]
            print(f"\n[최종 논문 정보]")
            print(f"- 제목: {paper.get('title')}")
            print(f"- 출처: {paper.get('source')}")
            print(f"- 에이전트 선정 이유(Insight): {paper.get('_agent_insight')}")
            print(f"\n[최종 생성된 요약본 (Agent Briefing 포함)]:\n{paper.get('abstract_ko')}")
        else:
            print("수집된 논문이 없습니다. (Critic 필터링에서 모두 탈락했거나 검색 결과가 없음)")
        
        print("\n[에이전트의 내부 사고 흐름 (Steps)]")
        for step in result.get('steps', []):
            name = step.get('name')
            detail = step.get('detail', {})
            print(f" -> {name}")
            if name == "plan_created":
                print(f"    (검색 전략: {detail.get('rounds')})")
            elif name == "evaluated_with_critic":
                print(f"    (Critic 평가 결과: Relevant {detail.get('relevant_count')}건, Rejected {detail.get('rejected_count')}건)")
                
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    test_pipeline()
