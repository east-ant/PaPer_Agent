from fastapi import FastAPI
from database import init_db, save_paper, get_papers
from agent import analyze_paper, is_relevant

app = FastAPI()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"message": "Paper Agent 서버 정상 동작"}

@app.post("/analyze")
def analyze(title: str, abstract: str, keyword: str, arxiv_id: str = "test-001"):
    result = analyze_paper(title, abstract, keyword)
    relevant = is_relevant(result)

    if relevant:
        saved = save_paper(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            summary=result
        )
        return {
            "relevant": True,
            "summary": result,
            "saved": saved
        }

    return {
        "relevant": False,
        "summary": "관련 없는 논문",
        "saved": False
    }

@app.get("/papers")
def papers():
    return get_papers()