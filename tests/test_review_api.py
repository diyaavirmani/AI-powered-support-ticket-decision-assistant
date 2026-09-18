"""Integration tests for Human-in-the-Loop review and override endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api import app, ticket_workflow_dependency
from src.schemas import DecisionDraft, TicketRequest


class FakeWorkflow:
    def __init__(self, decision: DecisionDraft | None = None) -> None:
        self.decision = decision or DecisionDraft(
            action="REQUEST_PHOTOS",
            confidence=0.85,
            reason="The damaged-goods policy requires photos.",
            sources=["damaged_goods.md"],
            inferred_issue_type="damaged",
        )

    def decide(self, request: TicketRequest) -> DecisionDraft:
        return self.decision


@pytest.fixture
def workflow_override() -> Generator[FakeWorkflow, None, None]:
    workflow = FakeWorkflow()
    app.dependency_overrides[ticket_workflow_dependency] = lambda: workflow
    yield workflow
    app.dependency_overrides.pop(ticket_workflow_dependency, None)


def register_and_token(client: TestClient, email: str) -> str:
    password = "correct horse battery staple"
    registered = client.post("/register", json={"email": email, "password": password})
    assert registered.status_code == 201
    logged_in = client.post("/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_agent_can_accept_ai_decision(client: TestClient, workflow_override: FakeWorkflow):
    alice = register_and_token(client, "alice@example.com")
    ticket_res = client.post(
        "/tickets",
        json={"message": "My item arrived damaged"},
        headers=auth_headers(alice),
    )
    assert ticket_res.status_code == 201
    ticket_id = ticket_res.json()["id"]

    review_res = client.post(
        f"/tickets/{ticket_id}/review",
        json={"accept": True, "reason": "Verified by senior agent"},
        headers=auth_headers(alice),
    )
    assert review_res.status_code == 200
    decision = review_res.json()["decision"]
    assert decision["human_override_action"] == "REQUEST_PHOTOS"
    assert decision["human_override_reason"] == "Verified by senior agent"
    assert decision["reviewed_at"] is not None


def test_agent_can_override_ai_decision(client: TestClient, workflow_override: FakeWorkflow):
    alice = register_and_token(client, "alice@example.com")
    ticket_res = client.post(
        "/tickets",
        json={"message": "My item arrived damaged"},
        headers=auth_headers(alice),
    )
    ticket_id = ticket_res.json()["id"]

    override_res = client.post(
        f"/tickets/{ticket_id}/review",
        json={
            "accept": False,
            "action": "APPROVE_REFUND_OR_REPLACEMENT",
            "reason": "VIP exception approved by supervisor",
        },
        headers=auth_headers(alice),
    )
    assert override_res.status_code == 200
    decision = override_res.json()["decision"]
    assert decision["human_override_action"] == "APPROVE_REFUND_OR_REPLACEMENT"
    assert decision["human_override_reason"] == "VIP exception approved by supervisor"


def test_override_missing_reason_fails_validation(
    client: TestClient, workflow_override: FakeWorkflow
):
    alice = register_and_token(client, "alice@example.com")
    ticket_res = client.post(
        "/tickets",
        json={"message": "My item arrived damaged"},
        headers=auth_headers(alice),
    )
    ticket_id = ticket_res.json()["id"]

    res = client.post(
        f"/tickets/{ticket_id}/review",
        json={"accept": False, "action": "APPROVE_RETURN"},
        headers=auth_headers(alice),
    )
    assert res.status_code == 422


def test_review_enforces_tenancy_isolation(
    client: TestClient, workflow_override: FakeWorkflow
):
    alice = register_and_token(client, "alice@example.com")
    bob = register_and_token(client, "bob@example.com")

    ticket_res = client.post(
        "/tickets",
        json={"message": "Bob's ticket"},
        headers=auth_headers(bob),
    )
    bob_ticket_id = ticket_res.json()["id"]

    # Alice tries to review Bob's ticket
    res = client.post(
        f"/tickets/{bob_ticket_id}/review",
        json={"accept": True},
        headers=auth_headers(alice),
    )
    assert res.status_code == 404
