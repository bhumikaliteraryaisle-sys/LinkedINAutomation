from pydantic import BaseModel
from typing import Optional


class TrendData(BaseModel):
    topic: str
    source: str  # "google" | "rss" | "evergreen"
    score: float = 0.0
    context: Optional[str] = None
