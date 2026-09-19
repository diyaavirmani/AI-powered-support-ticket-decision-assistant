"""Authenticated ticket API integration tests using deterministic local fakes."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api import app, ticket_workflow_dependency
from src.decision import DecisionValidationError
from src.models import Decision, Ticket
from src.retrieval import ProviderServiceError
from src.schemas import DecisionDraft, TicketRequest


class FakeWorkflow:
    def __init__(self, decision: DecisionDraft | None = None, error: Exception | None = None) -> None:
        self.decision = decision or DecisionDraft(
            action="REQUEST_PHOTOS",
            confidence=0.82,
            reason="The damaged-goods policy requires photos.",
            sources=["damaged_goods.md"],
            inferred_issue_type="damaged",
        )
        self.error = error
        self.requests: list[TicketRequest] = []

    def decide(self, request: TicketRequest) -> DecisionDraft:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
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


def ticket_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "message": "My phone screen arrived cracked.",
        "order_value_inr": "1999.00",
        "days_since_delivery": 2,
        "days_since_dispatch": 5,
        "product_type": "non_food",
        "opened_status": "opened",
        "order_status": "delivered",
    }
    payload.update(overrides)
    return payload


def create_ticket(client: TestClient, token: str, **overrides: object):
    return client.post("/tickets", json=ticket_payload(**overrides), headers=auth_headers(token))


def test_authenticated_ticket_creation_persists_one_ticket_and_decision(
    client: TestClient, db_session: Session, workflow_override: FakeWorkflow
) -> None:
    token = register_and_token(client, "alice@example.com")

    response = create_ticket(client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["decision"]["action"] == "REQUEST_PHOTOS"
    assert body["decision"]["sources"] == ["damaged_goods.md"]
    assert "password_hash" not in response.text
    assert "prompt" not in response.text
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 1
    assert db_session.scalar(select(func.count()).select_from(Decision)) == 1
    assert workflow_override.requests[0].message == ticket_payload()["message"]
    assert workflow_override.requests[0].days_since_delivery == 2


def test_ticket_list_is_owner_scoped_and_newest_first(
    client: TestClient, workflow_override: FakeWorkflow
) -> None:
    alice = register_and_token(client, "alice@example.com")
    bob = register_and_token(client, "bob@example.com")
    first = create_ticket(client, alice, message="First damaged item")
    second = create_ticket(client, alice, message="Second damaged item")
    create_ticket(client, bob, message="Bob's damaged item")

    response = client.get("/tickets", headers=auth_headers(alice))

    assert response.status_code == 200
    assert [ticket["id"] for ticket in response.json()] == [second.json()["id"], first.json()["id"]]
    assert all(ticket["message"] != "Bob's damaged item" for ticket in response.json())


def test_ticket_detail_is_owner_scoped_and_hides_other_users_ticket(
    client: TestClient, workflow_override: FakeWorkflow
) -> None:
    alice = register_and_token(client, "alice@example.com")
    bob = register_and_token(client, "bob@example.com")
    bob_ticket = create_ticket(client, bob)

    own = create_ticket(client, alice)
    assert client.get(f"/tickets/{own.json()['id']}", headers=auth_headers(alice)).status_code == 200
    hidden = client.get(f"/tickets/{bob_ticket.json()['id']}", headers=auth_headers(alice))
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Ticket not found"}


def test_ticket_validation_and_authentication_failures(client: TestClient) -> None:
    assert client.post("/tickets", json=ticket_payload()).status_code == 401
    assert client.post(
        "/tickets", json=ticket_payload(), headers={"Authorization": "Bearer invalid"}
    ).status_code == 401

    token = register_and_token(client, "alice@example.com")
    invalid = create_ticket(client, token, message=" ", issue_type="damaged_goods")
    assert invalid.status_code == 422
    assert any(error["loc"][-1] == "issue_type" for error in invalid.json()["detail"])


def test_null_ticket_fields_are_preserved_and_needs_more_information_is_stored(
    client: TestClient, workflow_override: FakeWorkflow
) -> None:
    workflow_override.decision = DecisionDraft(
        action="NEEDS_MORE_INFORMATION",
        confidence=0.4,
        reason="The delivery timing is missing.",
        sources=["shipping.md"],
        inferred_issue_type="shipping_delay",
    )
    token = register_and_token(client, "alice@example.com")

    response = create_ticket(
        client,
        token,
        order_value_inr=None,
        days_since_delivery=None,
        days_since_dispatch=None,
        product_type=None,
        opened_status=None,
        order_status="unknown",
    )

    assert response.status_code == 201
    assert response.json()["order_value_inr"] is None
    assert response.json()["days_since_delivery"] is None
    assert response.json()["decision"]["action"] == "NEEDS_MORE_INFORMATION"


@pytest.mark.parametrize(
    "error, expected_status",
    [
        (DecisionValidationError("bad action"), 502),
        (ProviderServiceError("embedding unavailable"), 503),
    ],
)
def test_upstream_failures_do_not_persist_or_expose_details(
    client: TestClient,
    db_session: Session,
    error: Exception,
    expected_status: int,
) -> None:
    workflow = FakeWorkflow(error=error)
    app.dependency_overrides[ticket_workflow_dependency] = lambda: workflow
    try:
        token = register_and_token(client, "alice@example.com")
        response = create_ticket(client, token)
    finally:
        app.dependency_overrides.pop(ticket_workflow_dependency, None)

    assert response.status_code == expected_status
    assert "embedding unavailable" not in response.text
    assert db_session.scalar(select(func.count()).select_from(Ticket)) == 0


def test_missing_production_gemini_configuration_is_a_clear_503(client: TestClient) -> None:
    token = register_and_token(client, "alice@example.com")

    response = create_ticket(client, token)

    assert response.status_code == 503
    assert response.json() == {"detail": "AI decision service is not configured"}


def test_raw_action_persisted_in_database(
    client: TestClient, db_session: Session
) -> None:
    from src.models import Decision
    workflow = FakeWorkflow(
        decision=DecisionDraft(
            action="REQUEST_PHOTOS",
            raw_action="APPROVE_REFUND_OR_REPLACEMENT",
            raw_reason="LLM draft approval",
            confidence=0.88,
            reason="Photos required by policy.",
            sources=["damaged_goods.md"],
            inferred_issue_type="damaged",
            guardrail_triggered=True,
        )
    )
    app.dependency_overrides[ticket_workflow_dependency] = lambda: workflow
    try:
        token = register_and_token(client, "alice@example.com")
        res = create_ticket(client, token)
    finally:
        app.dependency_overrides.pop(ticket_workflow_dependency, None)

    assert res.status_code == 201
    assert res.json()["decision"]["raw_action"] == "APPROVE_REFUND_OR_REPLACEMENT"
    decision_row = db_session.scalar(select(Decision))
    assert decision_row.raw_action == "APPROVE_REFUND_OR_REPLACEMENT"


def test_db_connection_is_not_held_during_llm_call(client: TestClient) -> None:
    from src.database import engine

    class InspectingWorkflow:
        def __init__(self):
            self.checked_out_during_call = None

        def decide(self, request: TicketRequest) -> DecisionDraft:
            self.checked_out_during_call = engine.pool.checkedout()
            return DecisionDraft(
                action="WAIT_AND_TRACK",
                confidence=0.9,
                reason="Standard delay.",
                sources=["shipping.md"],
                inferred_issue_type="shipping_delay",
            )

    inspecting_workflow = InspectingWorkflow()
    app.dependency_overrides[ticket_workflow_dependency] = lambda: inspecting_workflow
    try:
        token = register_and_token(client, "alice@example.com")
        res = create_ticket(client, token)
    finally:
        app.dependency_overrides.pop(ticket_workflow_dependency, None)

    assert res.status_code == 201
    assert inspecting_workflow.checked_out_during_call == 0
