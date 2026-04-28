import random
import re
from models.schemas import TrendData

EVERGREEN_TOPICS = [
    "Building a data analytics portfolio from scratch",
    "5 AI tools saving analysts 10+ hours a week",
    "How to transition into a data career in 2025",
    "Why most dashboards fail to drive decisions",
    "Automating weekly reports with Python in 30 minutes",
    "The hidden skill every data analyst needs (it's not SQL)",
    "From spreadsheets to Tableau: a practical migration guide",
]

TARGET_KEYWORDS: dict[str, list[str]] = {
    "data_analytics": ["data", "analytics", "sql", "python", "bi", "dashboard", "tableau", "power bi", "dataset"],
    "ai_automation": ["ai", "llm", "automation", "machine learning", "generative", "gemini", "chatgpt", "openai", "model"],
    "career_growth": ["career", "job", "skill", "linkedin", "growth", "interview", "hire", "salary", "resume"],
    "startups": ["startup", "funding", "founder", "saas", "product", "venture", "seed", "vc", "scale"],
}

BANNED_KEYWORDS = ["politics", "religion", "war", "election", "scandal", "protest", "violence", "terror"]

CATEGORY_WEIGHTS: dict[str, float] = {
    "data_analytics": 1.0,
    "ai_automation": 1.0,
    "career_growth": 0.8,
    "startups": 0.7,
}


def _is_banned(topic: str) -> bool:
    lower = topic.lower()
    return any(kw in lower for kw in BANNED_KEYWORDS)


def _relevance_score(topic: str) -> float:
    lower = topic.lower()
    score = 0.0
    for category, keywords in TARGET_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            score += hits * CATEGORY_WEIGHTS[category]
    return score


def _score_trend(trend: TrendData) -> float:
    if _is_banned(trend.topic):
        return 0.0
    base = trend.score
    relevance = _relevance_score(trend.topic)
    return base + relevance * 0.5


def get_top_5_topics(trends: list[TrendData]) -> list[str]:
    scored = [(t, _score_trend(t)) for t in trends if not _is_banned(t.topic)]
    scored.sort(key=lambda x: x[1], reverse=True)

    seen: set[str] = set()
    results: list[str] = []
    for trend, score in scored:
        clean = trend.topic.strip()
        if clean.lower() not in seen and score > 0:
            seen.add(clean.lower())
            results.append(clean)
        if len(results) == 5:
            break

    # pad with evergreens if needed
    if len(results) < 5:
        pool = [t for t in EVERGREEN_TOPICS if t.lower() not in seen]
        random.shuffle(pool)
        for ev in pool:
            results.append(ev)
            if len(results) == 5:
                break

    return results[:5]
