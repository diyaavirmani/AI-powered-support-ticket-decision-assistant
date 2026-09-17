"""Unit tests for grounded structured-decision validation."""

from collections.abc import Sequence

import pytest

from src.decision import DecisionValidationError, TicketDecisionWorkflow, build_retrieval_query
from src.retrieval import RetrievedChunk
from src.schemas import TicketRequest


RETRIEVED = [
    RetrievedChunk(
        chunk_id="damaged_goods.md:0:test",
        source_filename="damaged_goods.md",
        text="# Damaged Goods\n1. Request photos.",
        similarity=0.9,
    )
]


class StaticRetriever:
    def __init__(self, chunks: Sequence[RetrievedChunk] = RETRIEVED) -> None:
        self.chunks = list(chunks)
        self.queries: list[str] = []

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        self.queries.append(query)
        return self.chunks


class SequenceGenerator:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def generate(self, prompt: str, _response_schema: dict) -> object:
        self.prompts.append(prompt)
        return self.responses.pop(0)


def ticket_request() -> TicketRequest:
    return TicketRequest(
        message="The screen arrived cracked.",
        order_value_inr="1999.00",
        days_since_delivery=2,
        product_type="non_food",
        opened_status="opened",
        order_status="delivered",
    )


def valid_decision(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "action": "REQUEST_PHOTOS",
        "confidence": 0.8,
        "reason": "The damage policy requires photos before resolution.",
        "sources": ["damaged_goods.md"],
        "inferred_issue_type": "damaged",
    }
    result.update(overrides)
    return result


def test_workflow_uses_structured_facts_and_policy_only_sources() -> None:
    retriever = StaticRetriever()
    generator = SequenceGenerator([valid_decision()])
    workflow = TicketDecisionWorkflow(retriever, generator)

    decision = workflow.decide(ticket_request())

    assert decision.action.value == "REQUEST_PHOTOS"
    assert '"days_since_delivery":2' in retriever.queries[0]
    assert '"product_type":"non_food"' in retriever.queries[0]
    assert "TICKET FACTS (UNTRUSTED)" in generator.prompts[0]
    assert "Historical resolved tickets are not evidence" in generator.prompts[0]
    assert "damaged_goods.md" in generator.prompts[0]


@pytest.mark.parametrize(
    "response",
    [
        valid_decision(action="NOT_A_REAL_ACTION"),
        valid_decision(confidence=1.1),
        valid_decision(sources=["invented.md"]),
        "not a JSON object",
    ],
)
def test_invalid_decisions_are_rejected_after_one_repair_attempt(response: object) -> None:
    generator = SequenceGenerator([response, response])
    workflow = TicketDecisionWorkflow(StaticRetriever(), generator)

    with pytest.raises(DecisionValidationError):
        workflow.decide(ticket_request())

    assert len(generator.prompts) == 2
    assert "previous result was invalid" in generator.prompts[1]


def test_build_retrieval_query_preserves_null_facts() -> None:
    ticket = TicketRequest(message="Where is my order?", order_status="dispatched")

    query = build_retrieval_query(ticket)

    assert '"days_since_delivery":null' in query
    assert '"order_status":"dispatched"' in query
