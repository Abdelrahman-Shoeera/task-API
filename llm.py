"""LLM integration for the /categorize endpoint."""

import os
from enum import Enum
from pydantic import BaseModel, Field,ValidationError
from pathlib import Path
from openai import OpenAI,APITimeoutError,APIConnectionError
from dotenv import load_dotenv
from fastapi import HTTPException
import json
from datetime import datetime, timezone
import time

load_dotenv()

PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"categorize-{PROMPT_VERSION}.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text()

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL"),
    api_key=os.environ.get("LLM_API_KEY"),
    timeout=30,
    max_retries=2,
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

def _call_model(messages: list[dict]) -> tuple[str, dict]:
    """Call the LLM. Returns (raw_text, metadata).

    metadata contains: model, input_tokens, output_tokens, duration_ms.
    """
    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            messages=messages,
            temperature=0.2,
        )
    except (APITimeoutError, APIConnectionError):
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_call(
            prompt_version=PROMPT_VERSION,
            model=os.environ["LLM_MODEL"],
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
            repaired=False,
            outcome="timeout",
        )
        raise HTTPException(
            status_code=504,
            detail="LLM provider could not be reached (timeout or connection error)",
        )

    duration_ms = int((time.perf_counter() - start) * 1000)
    raw = response.choices[0].message.content
    metadata = {
        "model": response.model,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "duration_ms": duration_ms,
    }
    print(f"[LLM raw] {raw}")
    return raw, metadata



def _log_quarantine(title: str,raw: str,first_error: str,repair_raw: str,second_error: str) -> None:
    """Append a failure record to logs/quarantine.jsonl.

    Called when both the initial model attempt and the repair retry fail
    to produce schema-valid output. The file is JSON Lines format —
    one complete JSON object per line, appendable, greppable.

    Also prints a short summary to stdout for immediate visibility during dev.
    """

    log_path = Path(__file__).parent / "logs" / "quarantine.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)


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


def _log_call(
    prompt_version: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    repaired: bool,
    outcome: str,
) -> None:
    """Append a structured call record to logs/calls.jsonl.

    Called after every completed model call cycle (successful or failed).
    JSON Lines format — one complete JSON object per line.

    outcome: "success" | "quarantined" | "timeout" | "kill_switch" | "stub"
    """
    log_path = Path(__file__).parent / "logs" / "calls.jsonl"
    log_path.parent.mkdir(exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "repaired": repaired,
        "outcome": outcome,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")



def categorize(title: str) -> CategorizeResponse:
    """... existing docstring ..."""

    # Kill switch
    if os.environ.get("LLM_ENABLED", "true").lower() == "false":
        _log_call(
            prompt_version=PROMPT_VERSION,
            model="(none)",
            input_tokens=0,
            output_tokens=0,
            duration_ms=0,
            repaired=False,
            outcome="kill_switch",
        )
        return CategorizeResponse(
            category=Category.other,
            priority=Priority.normal,
            estimated_minutes=30,
            confidence=0.0,
            reason="categorization service disabled",
        )

    # Stub mode
    if os.environ.get("LLM_STUB") == "1":
        _log_call(
            prompt_version=PROMPT_VERSION,
            model="(stub)",
            input_tokens=0,
            output_tokens=0,
            duration_ms=0,
            repaired=False,
            outcome="stub",
        )
        return _stub_response(title)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": title},
    ]

    raw , meta = _call_model(messages)

    first_error = None
    try:
        json_text = _extract_json(raw)
        parsed = json.loads(json_text)
        result = CategorizeResponse(**parsed)
        _log_call(
            prompt_version=PROMPT_VERSION,
            model=meta["model"],
            input_tokens=meta["input_tokens"],
            output_tokens=meta["output_tokens"],
            duration_ms=meta["duration_ms"],
            repaired=False,
            outcome="success",
        )
        return result
    except (LLMExtractionError, json.JSONDecodeError, ValidationError) as e:
        first_error = e

    # Repair retry
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

    repair_raw , repair_meta = _call_model(repair_messages)

    try:
        repair_json = _extract_json(repair_raw)
        repair_parsed = json.loads(repair_json)
        result = CategorizeResponse(**repair_parsed)
        _log_call(
            prompt_version=PROMPT_VERSION,
            model=repair_meta["model"],
            input_tokens=meta["input_tokens"] + repair_meta["input_tokens"],
            output_tokens=meta["output_tokens"] + repair_meta["output_tokens"],
            duration_ms=meta["duration_ms"] + repair_meta["duration_ms"],
            repaired=True,
            outcome="success",
        )
        return result
    except (LLMExtractionError, json.JSONDecodeError, ValidationError) as e:
        second_error = e
        _log_call(
            prompt_version=PROMPT_VERSION,
            model=repair_meta["model"],
            input_tokens=meta["input_tokens"] + repair_meta["input_tokens"],
            output_tokens=meta["output_tokens"] + repair_meta["output_tokens"],
            duration_ms=meta["duration_ms"] + repair_meta["duration_ms"],
            repaired=True,
            outcome="quarantined",
        )
        _log_quarantine(title, raw, str(first_error), repair_raw, str(second_error))
        raise HTTPException(
            status_code=422,
            detail=(
                "Model output failed validation twice. "
                "Original error: " + str(first_error)[:200]
            ),
        )