import logging
import json
import google.generativeai as genai
from config.settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert LinkedIn content strategist specializing in:
- Data Analytics and Business Intelligence
- AI and Automation
- Career Growth and Professional Development
- Startups and Business Insights

Tone rules:
- Professional but conversational — write like a smart colleague, not a press release
- Insightful and slightly opinionated — take a clear stance, don't hedge everything
- No fluff, high clarity — every sentence must earn its place
- Avoid generic AI-sounding phrases like "In today's fast-paced world", "game-changer", "leverage synergies"
- Avoid controversial political, religious, or sensitive social topics

Post structure (always follow this):
1. Hook — a single strong opening line that stops the scroll
2. Insight — 2-3 sentences with a concrete observation, data point, or story
3. Takeaway — one actionable or thought-provoking point
4. CTA — a question or engagement trigger to invite comments

Constraints:
- Length: 120–200 words per post
- Use line breaks for readability (blank line between sections)
- End with 3–5 relevant hashtags on the last line
- Never number the sections or add labels like "Hook:" or "CTA:"
"""

_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT,
            generation_config={"max_output_tokens": 1200, "temperature": 0.8},
        )
    return _model


def _call(prompt: str) -> str:
    model = _get_model()
    response = model.generate_content(prompt)
    return response.text.strip()


def generate_posts(topic: str, context: str = "") -> list[str]:
    """Generate 3 distinct LinkedIn post variants for the given topic."""
    ctx_line = f"\nAdditional context: {context}" if context else ""
    prompt = f"""Topic: {topic}{ctx_line}

Write 3 LinkedIn posts. Different angles: data-driven, story-based, opinion-led.

---POST 1---
(post here)
---POST 2---
(post here)
---POST 3---
(post here)"""
    raw = _call(prompt)
    return _parse_posts(raw)


def amend_post(original_post: str, instructions: str) -> str:
    """Revise a single post based on natural language instructions."""
    prompt = f"""Here is a LinkedIn post:

{original_post}

User's amendment instructions: {instructions}

Rewrite the post applying these changes while keeping the overall structure intact. Return ONLY the revised post, no preamble.
"""
    return _call(prompt)


def more_posts(topic: str, direction: str = "") -> list[str]:
    """Generate 3 fresh post variants, optionally guided by a direction hint."""
    dir_line = f"\nDirection / style hint: {direction}" if direction else ""
    prompt = f"""Topic: {topic}{dir_line}

Write 3 fresh LinkedIn posts — unexpected angles, contrarian takes, vivid hooks.

---POST 1---
(post here)
---POST 2---
(post here)
---POST 3---
(post here)"""
    raw = _call(prompt)
    return _parse_posts(raw)


def _parse_posts(raw: str) -> list[str]:
    """Split the raw Gemini response into a list of 3 post strings."""
    import re
    parts = re.split(r"---POST \d+---", raw)
    posts = [p.strip() for p in parts if p.strip()]
    if len(posts) >= 3:
        return posts[:3]
    # fallback: return whatever we got, padded if necessary
    while len(posts) < 3:
        posts.append(posts[-1] if posts else raw)
    return posts
