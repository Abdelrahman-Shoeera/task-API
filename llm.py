"""LLM integration for the /categorize endpoint.

Stage 1: schemas and stub mode. No real LLM calls yet.
Stage 2+ will add: prompt loading, real LLM client, parse/validate/repair.
"""

import os
from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path
from openai import OpenAI

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"categorize-{PROMPT_VERSION}.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text()

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL"),
    api_key=os.environ.get("LLM_API_KEY"),
)


# --- Enums for closed-list fields (see JOB-CARD.md) ---

class Category(str, Enum):
    work = "work"
    personal = "personal"
    errand = "errand"
    admin = "admin"
    other = "other"


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


# --- Input schema ---

class CategorizeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


# --- Output schema ---

class CategorizeResponse(BaseModel):
    category: Category
    priority: Priority
    estimated_minutes: int = Field(ge=1, le=480)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=120)


# --- Stub mode ---

def _stub_response(title: str) -> CategorizeResponse:
    """Return a hardcoded valid response without calling any model.

    Enabled via env var LLM_STUB=1. Used during development so we don't
    burn our daily OpenRouter quota on iteration.
    """
    return CategorizeResponse(
        category=Category.other,
        priority=Priority.normal,
        estimated_minutes=30,
        confidence=0.5,
        reason="stub response - LLM not called",
    )


def categorize(title: str) -> CategorizeResponse:
    """Categorize a task title. Returns a validated response.

    Uses stub mode (LLM_STUB=1) or real LLM call.
    """
    if os.environ.get("LLM_STUB") == "1":
        return _stub_response(title)

    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": title},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content
    print(f"[LLM raw] {raw}")

    # Temporary debug: print raw model output for Stage 2/3 iteration.
    # Will be replaced by structured logging later.
    import json
    parsed = json.loads(raw)
    return CategorizeResponse(**parsed)
