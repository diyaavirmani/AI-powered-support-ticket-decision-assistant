"""Deterministic policy guardrail firewall unit tests."""

from decimal import Decimal

from src.guardrails import enforce_policy_guardrails
from src.schemas import (
    Action,
    DecisionDraft,
    IssueType,
    OpenedStatus,
    OrderStatus,
    ProductType,
    TicketRequest,
)


def make_decision(action: Action, issue: IssueType, sources: list[str]) -> DecisionDraft:
    return DecisionDraft(
        action=action,
        confidence=0.9,
        reason="Initial LLM recommendation based on policy.",
        sources=sources,
        inferred_issue_type=issue,
    )


def test_damaged_goods_above_2000_triggers_photo_guardrail():
    ticket = TicketRequest(
        message="Broken product on delivery",
        order_value_inr=Decimal("3500.00"),
        days_since_delivery=2,
    )
    decision = make_decision(
        Action.APPROVE_REFUND_OR_REPLACEMENT, IssueType.DAMAGED, ["damaged_goods.md"]
    )

    guarded, interventions = enforce_policy_guardrails(ticket, decision)

    assert guarded.action == Action.REQUEST_PHOTOS
    assert guarded.guardrail_triggered is True
    assert any("2,000" in i for i in interventions)
    assert "[Guardrail Applied:" in guarded.reason


def test_damaged_goods_outside_7_days_triggers_rejection_guardrail():
    ticket = TicketRequest(
        message="Damaged package",
        order_value_inr=Decimal("1500.00"),
        days_since_delivery=10,
    )
    decision = make_decision(
        Action.APPROVE_REFUND_OR_REPLACEMENT, IssueType.DAMAGED, ["damaged_goods.md"]
    )

    guarded, interventions = enforce_policy_guardrails(ticket, decision)

    assert guarded.action == Action.REJECT_OUTSIDE_WINDOW
    assert guarded.guardrail_triggered is True


def test_food_return_triggers_ineligibility_guardrail():
    ticket = TicketRequest(
        message="Want to return snacks",
        product_type=ProductType.FOOD,
        opened_status=OpenedStatus.UNOPENED,
        days_since_delivery=3,
    )
    decision = make_decision(Action.APPROVE_RETURN, IssueType.RETURN, ["returns.md"])

    guarded, interventions = enforce_policy_guardrails(ticket, decision)

    assert guarded.action == Action.REJECT_FOOD_RETURN
    assert guarded.guardrail_triggered is True


def test_opened_non_food_return_triggers_opened_item_rejection():
    ticket = TicketRequest(
        message="Changed my mind but opened it",
        product_type=ProductType.NON_FOOD,
        opened_status=OpenedStatus.OPENED,
        days_since_delivery=5,
    )
    decision = make_decision(Action.APPROVE_RETURN, IssueType.RETURN, ["returns.md"])

    guarded, interventions = enforce_policy_guardrails(ticket, decision)

    assert guarded.action == Action.REJECT_OPENED_ITEM
    assert guarded.guardrail_triggered is True


def test_defective_above_3000_requires_defect_evidence():
    ticket = TicketRequest(
        message="Expensive device defective",
        order_value_inr=Decimal("4999.00"),
        days_since_delivery=6,
    )
    decision = make_decision(
        Action.APPROVE_REPLACEMENT, IssueType.DEFECTIVE, ["defective_products.md"]
    )

    guarded, interventions = enforce_policy_guardrails(ticket, decision)

    assert guarded.action == Action.REQUEST_DEFECT_EVIDENCE
    assert guarded.guardrail_triggered is True


def test_cancellation_after_dispatch_is_blocked_by_guardrail():
    ticket = TicketRequest(
        message="Please cancel",
        order_status=OrderStatus.DISPATCHED,
        days_since_dispatch=2,
    )
    decision = make_decision(
        Action.CANCEL_AND_REFUND, IssueType.CANCELLATION, ["cancellations.md"]
    )

    guarded, interventions = enforce_policy_guardrails(ticket, decision)

    assert guarded.action == Action.CANNOT_CANCEL_AFTER_DISPATCH
    assert guarded.guardrail_triggered is True


def test_compliant_decision_passes_unmodified():
    ticket = TicketRequest(
        message="Damaged package under 2k",
        order_value_inr=Decimal("1200.00"),
        days_since_delivery=2,
    )
    decision = make_decision(
        Action.APPROVE_REFUND_OR_REPLACEMENT, IssueType.DAMAGED, ["damaged_goods.md"]
    )

    guarded, interventions = enforce_policy_guardrails(ticket, decision)

    assert guarded.action == Action.APPROVE_REFUND_OR_REPLACEMENT
    assert guarded.guardrail_triggered is False
    assert len(interventions) == 0
