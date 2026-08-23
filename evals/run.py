"""Run the categorize endpoint against evals/cases.json and print a score.

Prompts for Supabase email/password on start. Hits POST /categorize for
each case, compares actual category against expected_category, and
prints per-case results plus a final score.

Grading rule: category match is a pass. Everything else (priority,
estimated_minutes, confidence, reason) is not graded but is shown in
the per-case output so a human reader can spot weirdness.
"""

import json
import sys
from getpass import getpass
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


BASE_URL = "http://localhost:8000"
CASES_PATH = Path(__file__).parent / "cases.json"


def get_token(email: str, password: str) -> str:
    """Log in via /auth/login and return the access token."""
    req = Request(
        f"{BASE_URL}/auth/login",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as resp:
        body = json.loads(resp.read())
    return body["access_token"]


def categorize(title: str, token: str) -> dict:
    """Call POST /categorize with the given title, return parsed JSON."""
    req = Request(
        f"{BASE_URL}/categorize",
        data=json.dumps({"title": title}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        # Return the error body so the runner can report it
        return {"__error__": e.code, "body": e.read().decode("utf-8", errors="replace")}


def is_pass(actual_category: str, expected: str | list) -> bool:
    """Grade one case: pass if actual matches expected (string or list-any-of)."""
    if isinstance(expected, list):
        return actual_category in expected
    return actual_category == expected


def main():
    # Load cases
    with open(CASES_PATH) as f:
        cases = json.load(f)
    print(f"Loaded {len(cases)} cases from {CASES_PATH.name}\n")

    # Get credentials
    email = input("Supabase email: ").strip()
    password = getpass("Supabase password: ")

    # Log in
    try:
        token = get_token(email, password)
    except HTTPError as e:
        print(f"Login failed: HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}")
        sys.exit(1)
    print(f"Logged in, token length {len(token)}\n")

    # Run cases
    print(f"{'STATUS':6}  {'ID':32}  {'CATEGORY':10}  {'EXPECTED':30}  TITLE")
    print("-" * 120)

    passes = 0
    failures = []

    for case in cases:
        title = case["title"]
        expected = case["expected_category"]

        result = categorize(title, token)

        if "__error__" in result:
            status = "ERROR"
            actual_cat = "(error)"
            failures.append((case["id"], f"HTTP {result['__error__']}: {result['body'][:100]}"))
        else:
            actual_cat = result.get("category", "(missing)")
            if is_pass(actual_cat, expected):
                status = "PASS"
                passes += 1
            else:
                status = "FAIL"
                failures.append((case["id"], f"got {actual_cat!r}, expected {expected!r}"))

        expected_display = str(expected) if not isinstance(expected, list) else "|".join(expected)
        print(f"{status:6}  {case['id']:32}  {actual_cat:10}  {expected_display:30}  {title}")

    print("-" * 120)
    print(f"\nScore: {passes}/{len(cases)}\n")

    if failures:
        print("Failures:")
        for case_id, reason in failures:
            print(f"  {case_id}: {reason}")


if __name__ == "__main__":
    main()