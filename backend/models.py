from pydantic import BaseModel
from typing import Optional

class Paper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    summary: Optional[str] = None
    category: Optional[str] = None
    published: Optional[str] = None