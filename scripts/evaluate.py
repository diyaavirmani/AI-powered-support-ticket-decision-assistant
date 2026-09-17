"""Evaluate the AI decision API against the supplied test cases.

Submits every case through the authenticated HTTP API and compares
the returned action with the expected action.  Does not call Gemini,
the database, or any internal module directly.

Usage:
    python -m scripts.evaluate --help
    python -m scripts.evaluate                              # defaults
    python -m scripts.evaluate --api-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from src.api_client import ApiClient, ApiError, AuthenticationError


DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_CASES_PATH = Path(__file__).resolve().parents[1] / "sample_test_cases.json"
DEFAULT_TIMEOUT = 60


@dataclass
class CaseResult:
    case_id: str
    expected: str
    actual: str | None
    error: str | None
    passed: bool


def load_test_cases(path: Path) -> list[dict[str, Any]]:
    """Load and validate the JSON test case file."""
    if not path.is_file():
        raise SystemExit(f"Test case file not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
        cases = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read test cases: {exc}") from None

    if not isinstance(cases, list) or not cases:
        raise SystemExit("Test cases must be a nonempty JSON array.")

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            raise SystemExit(f"Test case {idx} is not an object.")
        if "case_id" not in case or "expected_action" not in case:
            raise SystemExit(f"Test case {idx} is missing case_id or expected_action.")
        if "message" not in case:
            raise SystemExit(f"Test case {idx} is missing a message.")
    return cases


def build_ticket_payload(case: dict[str, Any]) -> dict[str, Any]:
    """Extract only the fields that POST /tickets accepts.

    Excludes case_id, expected_action, and issue_type.
    """
    payload: dict[str, Any] = {"message": case["message"]}
    for field in [
        "order_value_inr",
        "days_since_delivery",
        "days_since_dispatch",
        "product_type",
        "opened_status",
        "order_status",
    ]:
        if field in case:
            payload[field] = case[field]
    return payload


def setup_evaluation_account(client: ApiClient) -> str:
    """Register and log in a unique evaluation user.  Returns a bearer token."""
    eval_email = f"eval-{uuid.uuid4().hex[:12]}@example.com"
    # Strong random password, never printed or persisted.
    password = secrets.token_urlsafe(32)

    try:
        client.register(eval_email, password)
    except ApiError as exc:
        # A UUID-based email should never collide in practice.
        raise SystemExit(f"Evaluation setup failed during registration: {exc}") from None

    try:
        token = client.login(eval_email, password)
    except ApiError as exc:
        raise SystemExit(f"Evaluation setup failed during login: {exc}") from None

    return token


def evaluate_cases(
    client: ApiClient,
    token: str,
    cases: list[dict[str, Any]],
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        case_id = case["case_id"]
        expected = case["expected_action"]
        payload = build_ticket_payload(case)
        try:
            response = client.create_ticket(
                token,
                message=payload["message"],
                order_value_inr=payload.get("order_value_inr"),
                days_since_delivery=payload.get("days_since_delivery"),
                days_since_dispatch=payload.get("days_since_dispatch"),
                product_type=payload.get("product_type"),
                opened_status=payload.get("opened_status"),
                order_status=payload.get("order_status"),
            )
            actual = response.get("decision", {}).get("action")
            passed = actual == expected
            results.append(CaseResult(
                case_id=case_id,
                expected=expected,
                actual=actual,
                error=None,
                passed=passed,
            ))
        except AuthenticationError:
            results.append(CaseResult(
                case_id=case_id,
                expected=expected,
                actual=None,
                error="authentication_error",
                passed=False,
            ))
        except ApiError as exc:
            label = f"api_error_{exc.status_code}" if exc.status_code else "api_error"
            results.append(CaseResult(
                case_id=case_id,
                expected=expected,
                actual=None,
                error=label,
                passed=False,
            ))
    return results


def print_report(results: list[CaseResult]) -> None:
    print()
    for r in results:
        actual_display = r.actual if r.actual else f"ERROR({r.error})"
        status = "PASS" if r.passed else "FAIL"
        print(f"  {r.case_id}: expected={r.expected}  actual={actual_display}  [{status}]")

    total = len(results)
    correct = sum(1 for r in results if r.passed)
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0.0

    print()
    print(f"{total} test cases")
    print(f"Correct: {correct}")
    print(f"Incorrect: {incorrect}")
    print(f"Accuracy: {accuracy:.0f}%")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the AI decision API against supplied test cases."
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Base URL of the running FastAPI server (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_PATH),
        help=f"Path to the JSON test cases file (default: {DEFAULT_CASES_PATH})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request read timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args(argv)

    cases = load_test_cases(Path(args.cases))
    print(f"Loaded {len(cases)} test cases from {args.cases}")

    client = ApiClient(
        base_url=args.api_url,
        timeout=httpx.Timeout(connect=5.0, read=float(args.timeout), write=5.0, pool=5.0),
    )

    token = setup_evaluation_account(client)
    print("Evaluation account ready.")

    print("Submitting test cases…")
    results = evaluate_cases(client, token, cases)
    print_report(results)

    has_failures = any(not r.passed for r in results)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
