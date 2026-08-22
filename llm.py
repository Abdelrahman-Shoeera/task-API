"""LLM integration for the /categorize endpoint.

Stage 1: schemas and stub mode. No real LLM calls yet.
Stage 2+ will add: prompt loading, real LLM client, parse/validate/repair.
"""

import os
from enum import Enum
from pydantic import BaseModel, Field


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

    Stage 1: only stub mode works. Real LLM call comes in Stage 2.
    """
    if os.environ.get("LLM_STUB") == "1":
        return _stub_response(title)

    # Stage 2 will replace this with a real LLM call
    raise NotImplementedError(
        "Real LLM call not yet implemented. Set LLM_STUB=1 to use stub mode."
    )
