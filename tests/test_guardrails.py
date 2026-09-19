"""Deterministic policy guardrail firewall unit tests."""

from decimal import Decimal

import pytest

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


def test_defective_item_citing_damage_policy_keeps_14_day_window():
    """Verify cross-fire immunity: defective items citing damaged policy keep 14-day window."""
    ticket = TicketRequest(
        message="Phone stopped working",
        order_value_inr=Decimal("2500"),
        days_since_delivery=10,
    )
    decision = make_decision(
        Action.APPROVE_REPLACEMENT,
        IssueType.DEFECTIVE,
        ["defective_products.md", "damaged_goods.md"],
    )
    guarded, _ = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == Action.APPROVE_REPLACEMENT
    assert guarded.guardrail_triggered is False


def test_damaged_goods_missing_delivery_date_fails_closed_to_needs_more_info():
    ticket = TicketRequest(
        message="Product arrived damaged but no date given",
        order_value_inr=Decimal("1500"),
        days_since_delivery=None,
    )
    decision = make_decision(
        Action.APPROVE_REFUND_OR_REPLACEMENT, IssueType.DAMAGED, ["damaged_goods.md"]
    )
    guarded, interventions = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == Action.NEEDS_MORE_INFORMATION
    assert guarded.guardrail_triggered is True


def test_defective_products_missing_delivery_date_fails_closed_to_needs_more_info():
    ticket = TicketRequest(
        message="Device defect reported but delivery date missing",
        order_value_inr=Decimal("2500"),
        days_since_delivery=None,
    )
    decision = make_decision(
        Action.APPROVE_REPLACEMENT, IssueType.DEFECTIVE, ["defective_products.md"]
    )
    guarded, interventions = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == Action.NEEDS_MORE_INFORMATION
    assert guarded.guardrail_triggered is True


def test_returns_missing_opened_status_fails_closed_to_needs_more_info():
    ticket = TicketRequest(
        message="Want to return item",
        product_type=ProductType.NON_FOOD,
        opened_status=None,
        days_since_delivery=5,
    )
    decision = make_decision(
        Action.APPROVE_RETURN, IssueType.RETURN, ["returns.md"]
    )
    guarded, interventions = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == Action.NEEDS_MORE_INFORMATION
    assert guarded.guardrail_triggered is True


def test_cancellation_unknown_status_fails_closed_to_needs_more_info():
    ticket = TicketRequest(
        message="Can I cancel this?",
        order_status=OrderStatus.UNKNOWN,
    )
    decision = make_decision(
        Action.CANCEL_AND_REFUND, IssueType.CANCELLATION, ["cancellations.md"]
    )
    guarded, interventions = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == Action.NEEDS_MORE_INFORMATION
    assert guarded.guardrail_triggered is True


@pytest.mark.parametrize(
    ("days", "expected_action", "triggered"),
    [
        (7, Action.APPROVE_REFUND_OR_REPLACEMENT, False),
        (8, Action.REJECT_OUTSIDE_WINDOW, True),
    ],
)
def test_damaged_goods_day_boundary(days: int, expected_action: Action, triggered: bool):
    ticket = TicketRequest(
        message="Damaged package",
        order_value_inr=Decimal("1500"),
        days_since_delivery=days,
    )
    decision = make_decision(
        Action.APPROVE_REFUND_OR_REPLACEMENT, IssueType.DAMAGED, ["damaged_goods.md"]
    )
    guarded, _ = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == expected_action
    assert guarded.guardrail_triggered is triggered


@pytest.mark.parametrize(
    ("days", "expected_action", "triggered"),
    [
        (14, Action.APPROVE_REPLACEMENT, False),
        (15, Action.REJECT_OUTSIDE_WINDOW, True),
    ],
)
def test_defective_day_boundary(days: int, expected_action: Action, triggered: bool):
    ticket = TicketRequest(
        message="Defective item",
        order_value_inr=Decimal("2500"),
        days_since_delivery=days,
    )
    decision = make_decision(
        Action.APPROVE_REPLACEMENT, IssueType.DEFECTIVE, ["defective_products.md"]
    )
    guarded, _ = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == expected_action
    assert guarded.guardrail_triggered is triggered


@pytest.mark.parametrize(
    ("value", "expected_action", "triggered"),
    [
        (Decimal("2000.00"), Action.APPROVE_REFUND_OR_REPLACEMENT, False),
        (Decimal("2000.01"), Action.REQUEST_PHOTOS, True),
    ],
)
def test_damaged_value_boundary(value: Decimal, expected_action: Action, triggered: bool):
    ticket = TicketRequest(
        message="Damaged item",
        order_value_inr=value,
        days_since_delivery=3,
    )
    decision = make_decision(
        Action.APPROVE_REFUND_OR_REPLACEMENT, IssueType.DAMAGED, ["damaged_goods.md"]
    )
    guarded, _ = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == expected_action
    assert guarded.guardrail_triggered is triggered


@pytest.mark.parametrize(
    ("value", "expected_action", "triggered"),
    [
        (Decimal("3000.00"), Action.APPROVE_REPLACEMENT, False),
        (Decimal("3000.01"), Action.REQUEST_DEFECT_EVIDENCE, True),
    ],
)
def test_defective_value_boundary(value: Decimal, expected_action: Action, triggered: bool):
    ticket = TicketRequest(
        message="Defective device",
        order_value_inr=value,
        days_since_delivery=5,
    )
    decision = make_decision(
        Action.APPROVE_REPLACEMENT, IssueType.DEFECTIVE, ["defective_products.md"]
    )
    guarded, _ = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == expected_action
    assert guarded.guardrail_triggered is triggered


def test_raw_action_is_preserved_when_guardrail_intervenes():
    ticket = TicketRequest(
        message="Damaged package",
        order_value_inr=Decimal("5000"),
        days_since_delivery=2,
    )
    decision = make_decision(
        Action.APPROVE_REFUND_OR_REPLACEMENT, IssueType.DAMAGED, ["damaged_goods.md"]
    )
    guarded, _ = enforce_policy_guardrails(ticket, decision)
    assert guarded.action == Action.REQUEST_PHOTOS
    assert guarded.raw_action == Action.APPROVE_REFUND_OR_REPLACEMENT
    assert guarded.raw_reason == "Initial LLM recommendation based on policy."
