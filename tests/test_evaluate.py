"""Tests for the evaluation runner.

Uses fake API clients — no live server, Gemini, or network.
"""

import json
import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.evaluate import (
    CaseResult,
    build_ticket_payload,
    evaluate_cases,
    load_test_cases,
    main,
    print_report,
    setup_evaluation_account,
)
from src.api_client import ApiClient, ApiError, AuthenticationError


SAMPLE_CASES_PATH = Path(__file__).resolve().parents[1] / "sample_test_cases.json"


# ------------------------------------------------------------------
# Test-case loading
# ------------------------------------------------------------------

class TestLoadCases:
    def test_all_five_supplied_cases_parse(self):
        cases = load_test_cases(SAMPLE_CASES_PATH)
        assert len(cases) == 5
        for case in cases:
            assert "case_id" in case
            assert "expected_action" in case
            assert "message" in case

    def test_malformed_file_fails_clearly(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        with pytest.raises(SystemExit, match="Cannot read"):
            load_test_cases(bad)

    def test_missing_file_fails_clearly(self, tmp_path):
        missing = tmp_path / "missing.json"
        with pytest.raises(SystemExit, match="not found"):
            load_test_cases(missing)

    def test_empty_array_fails(self, tmp_path):
        empty = tmp_path / "empty.json"
        empty.write_text("[]", encoding="utf-8")
        with pytest.raises(SystemExit, match="nonempty"):
            load_test_cases(empty)

    def test_missing_required_fields_fails(self, tmp_path):
        incomplete = tmp_path / "incomplete.json"
        incomplete.write_text(json.dumps([{"case_id": "X"}]), encoding="utf-8")
        with pytest.raises(SystemExit, match="expected_action"):
            load_test_cases(incomplete)


# ------------------------------------------------------------------
# Payload construction
# ------------------------------------------------------------------

class TestBuildPayload:
    def test_case_id_excluded(self):
        case = {"case_id": "S01", "message": "help", "expected_action": "X"}
        payload = build_ticket_payload(case)
        assert "case_id" not in payload
        assert "expected_action" not in payload

    def test_null_values_preserved(self):
        case = {
            "case_id": "S01",
            "message": "help",
            "expected_action": "X",
            "days_since_delivery": None,
            "days_since_dispatch": None,
        }
        payload = build_ticket_payload(case)
        assert payload["days_since_delivery"] is None
        assert payload["days_since_dispatch"] is None

    def test_issue_type_not_added(self):
        case = {"case_id": "S01", "message": "help", "expected_action": "X"}
        payload = build_ticket_payload(case)
        assert "issue_type" not in payload

    def test_structured_fields_included(self):
        case = {
            "case_id": "S01",
            "message": "broken",
            "expected_action": "X",
            "order_value_inr": 3500,
            "product_type": "non_food",
        }
        payload = build_ticket_payload(case)
        assert payload["order_value_inr"] == 3500
        assert payload["product_type"] == "non_food"


# ------------------------------------------------------------------
# Evaluation logic
# ------------------------------------------------------------------

def _make_fake_client(responses: list[dict | ApiError]) -> ApiClient:
    """Build a fake ApiClient that returns predetermined responses."""
    client = MagicMock(spec=ApiClient)
    side_effects = []
    for r in responses:
        if isinstance(r, Exception):
            side_effects.append(r)
        else:
            side_effects.append(r)
    client.create_ticket.side_effect = side_effects
    return client


class TestEvaluateCases:
    def test_correct_and_incorrect_counts(self):
        client = _make_fake_client([
            {"decision": {"action": "REQUEST_PHOTOS"}},
            {"decision": {"action": "WRONG_ACTION"}},
            {"decision": {"action": "OPEN_SHIPPING_INVESTIGATION"}},
        ])
        cases = [
            {"case_id": "A", "message": "a", "expected_action": "REQUEST_PHOTOS"},
            {"case_id": "B", "message": "b", "expected_action": "APPROVE_RETURN"},
            {"case_id": "C", "message": "c", "expected_action": "OPEN_SHIPPING_INVESTIGATION"},
        ]
        results = evaluate_cases(client, "tok", cases)
        assert len(results) == 3
        assert results[0].passed is True
        assert results[1].passed is False
        assert results[2].passed is True

    def test_one_failure_does_not_stop_later_cases(self):
        client = _make_fake_client([
            ApiError("unavailable", status_code=503),
            {"decision": {"action": "APPROVE_RETURN"}},
        ])
        cases = [
            {"case_id": "A", "message": "a", "expected_action": "X"},
            {"case_id": "B", "message": "b", "expected_action": "APPROVE_RETURN"},
        ]
        results = evaluate_cases(client, "tok", cases)
        assert len(results) == 2
        assert results[0].passed is False
        assert results[0].error is not None
        assert results[1].passed is True

    def test_auth_error_recorded_as_failure(self):
        client = _make_fake_client([
            AuthenticationError("expired", status_code=401),
        ])
        cases = [{"case_id": "A", "message": "a", "expected_action": "X"}]
        results = evaluate_cases(client, "tok", cases)
        assert results[0].passed is False
        assert results[0].error == "authentication_error"


# ------------------------------------------------------------------
# Report formatting
# ------------------------------------------------------------------

class TestPrintReport:
    def test_accuracy_formatting(self, capsys):
        results = [
            CaseResult("A", "X", "X", None, True),
            CaseResult("B", "Y", "Z", None, False),
            CaseResult("C", "W", "W", None, True),
            CaseResult("D", "V", None, "api_error_503", False),
        ]
        print_report(results)
        output = capsys.readouterr().out
        assert "4 test cases" in output
        assert "Correct: 2" in output
        assert "Incorrect: 2" in output
        assert "Accuracy: 50%" in output

    def test_error_case_display(self, capsys):
        results = [CaseResult("X", "ACT", None, "api_error_503", False)]
        print_report(results)
        output = capsys.readouterr().out
        assert "ERROR" in output
        assert "FAIL" in output

    def test_all_correct(self, capsys):
        results = [CaseResult("A", "X", "X", None, True)]
        print_report(results)
        output = capsys.readouterr().out
        assert "Accuracy: 100%" in output


# ------------------------------------------------------------------
# Setup failure
# ------------------------------------------------------------------

class TestSetupAccount:
    def test_registration_failure_exits(self):
        client = MagicMock(spec=ApiClient)
        client.register.side_effect = ApiError("server error", status_code=500)
        with pytest.raises(SystemExit, match="setup failed"):
            setup_evaluation_account(client)

    def test_login_failure_exits(self):
        client = MagicMock(spec=ApiClient)
        client.register.return_value = {"id": 1}
        client.login.side_effect = ApiError("auth failed", status_code=401)
        with pytest.raises(SystemExit, match="setup failed"):
            setup_evaluation_account(client)

    def test_duplicate_registration_proceeds(self):
        client = MagicMock(spec=ApiClient)
        client.register.side_effect = ApiError("exists", status_code=409)
        client.login.return_value = "tok123"
        token = setup_evaluation_account(client)
        assert token == "tok123"


# ------------------------------------------------------------------
# Security
# ------------------------------------------------------------------

class TestSecurityInRunner:
    def test_passwords_and_tokens_not_printed(self, capsys):
        results = [CaseResult("A", "X", "X", None, True)]
        print_report(results)
        output = capsys.readouterr().out
        assert "Bearer" not in output
        assert "password" not in output.lower() or "password" in "my-super-secret-pw" not in output
