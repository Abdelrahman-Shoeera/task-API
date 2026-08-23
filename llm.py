"""LLM integration for the /categorize endpoint."""

import os
from enum import Enum
from pydantic import BaseModel, Field,ValidationError
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import HTTPException
import json


load_dotenv()

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


class LLMExtractionError(Exception):
    """Raised when the model's response contains no extractable JSON object."""
    pass


def _extract_json(text: str) -> str:
    """Extract the JSON object substring from raw model output."""

    
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise LLMExtractionError(
            f"no JSON object found in model output: {text[:200]!r}"
        )

    return text[start:end + 1]

def _call_model(messages: list[dict]) -> str:
    """Call the LLM with a messages list, return the raw response text.

    Encapsulates the actual API call so the same code path is used for
    the main attempt and the repair retry.
    """
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=messages,
        temperature=0.2,
    )
    raw = response.choices[0].message.content
    # Temporary debug: print raw model output for Stage 2/3 iteration.
    # Will be replaced by structured logging in Stage 4.
    print(f"[LLM raw] {raw}")
    return raw

def categorize(title: str) -> CategorizeResponse:
    """Categorize a task title. Returns a validated response.

    Flow:
      1. Build system+user messages.
      2. Call the model.
      3. Try to extract JSON, parse, and validate.
      4. If step 3 fails, run one repair retry:
         send the model its own broken output + the error.
      5. If repair also fails, quarantine and raise HTTPException(422).
    """
    if os.environ.get("LLM_STUB") == "1":
        return _stub_response(title)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": title},
    ]

    raw = _call_model(messages)

    # First attempt: try to extract, parse, validate
    first_error = None
    try:
       json_text = _extract_json(raw)
       parsed = json.loads(json_text)
       return CategorizeResponse(**parsed)
    except (LLMExtractionError, json.JSONDecodeError, ValidationError) as e:
       first_error = e

    # Repair retry: send the model its own broken output + the error
    repair_messages = messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": (
                f"Your previous response was rejected for this reason:\n"
                f"{first_error}\n\n"
                f"Return ONLY corrected JSON matching the schema. "
                f"No explanation, no code fences."
            ),
        },
    ]

    repair_raw = _call_model(repair_messages)

    # Second attempt: try to extract, parse, validate the repair output
    try:
        repair_json = _extract_json(repair_raw)
        repair_parsed = json.loads(repair_json)
        return CategorizeResponse(**repair_parsed)
    except (LLMExtractionError, json.JSONDecodeError, ValidationError) as second_error:
        # Both attempts failed. Quarantine and raise.
        _log_quarantine(title, raw, str(first_error), repair_raw, str(second_error))
        raise HTTPException(
            status_code=422,
            detail=(
                "Model output failed validation twice. "
                "Original error: " + str(first_error)[:200]
            ),
        )

def _log_quarantine(title: str,raw: str,first_error: str,repair_raw: str,second_error: str) -> None:
    """Append a failure record to logs/quarantine.jsonl.

    Called when both the initial model attempt and the repair retry fail
    to produce schema-valid output. The file is JSON Lines format —
    one complete JSON object per line, appendable, greppable.

    Also prints a short summary to stdout for immediate visibility during dev.
    """

    log_path = Path(__file__).parent / "logs" / "quarantine.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "input_title": title,
        "first_attempt": {
            "raw": raw,
            "error": first_error,
        },
        "repair_attempt": {
            "raw": repair_raw,
            "error": second_error,
        },
    }

    with open(log_path, "a", encoding="utf-8") as f:
      json.dump(entry, f)
      f.write("\n")


    print(f"[QUARANTINE] logged to {log_path.name}: {title!r}")