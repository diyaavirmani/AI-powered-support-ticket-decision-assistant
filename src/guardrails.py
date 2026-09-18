"""Deterministic policy guardrails (The Anti-Hallucination Firewall).

Neuro-symbolic validation layer: enforces strict numerical thresholds,
timing windows, and category exclusions deterministically before decisions
touch persistence.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from src.schemas import (
    Action,
    DecisionDraft,
    IssueType,
    OpenedStatus,
    OrderStatus,
    ProductType,
    TicketRequest,
)


def enforce_policy_guardrails(
    ticket: TicketRequest,
    decision: DecisionDraft,
) -> tuple[DecisionDraft, list[str]]:
    """Verify and correct LLM decisions against deterministic policy axioms.

    Returns:
        A tuple of (validated_or_corrected_decision, list_of_interventions).
    """
    interventions: list[str] = []
    action = decision.action
    reason = decision.reason
    inferred_type = decision.inferred_issue_type
    sources = list(decision.sources)
    confidence = decision.confidence

    # ------------------------------------------------------------------
    # 1. Damaged Goods Policy Rules
    # ------------------------------------------------------------------
    if inferred_type == IssueType.DAMAGED or "damaged_goods.md" in sources:
        # Rule: Damage > 7 days after delivery is ineligible
        if ticket.days_since_delivery is not None and ticket.days_since_delivery > 7:
            if action not in (Action.REJECT_OUTSIDE_WINDOW, Action.NEEDS_MORE_INFORMATION):
                interventions.append(
                    f"Damaged item reported {ticket.days_since_delivery} days after delivery (limit: 7 days)."
                )
                action = Action.REJECT_OUTSIDE_WINDOW
                if "damaged_goods.md" not in sources:
                    sources.append("damaged_goods.md")

        # Rule: Damage <= 7 days and value > 2,000 requires photos
        elif ticket.order_value_inr is not None and ticket.order_value_inr > Decimal("2000"):
            if action == Action.APPROVE_REFUND_OR_REPLACEMENT:
                interventions.append(
                    f"Order value ₹{ticket.order_value_inr} exceeds ₹2,000 threshold for automatic approval; photos required."
                )
                action = Action.REQUEST_PHOTOS
                if "damaged_goods.md" not in sources:
                    sources.append("damaged_goods.md")

    # ------------------------------------------------------------------
    # 2. Returns Policy Rules
    # ------------------------------------------------------------------
    if inferred_type == IssueType.RETURN or "returns.md" in sources:
        # Rule: Food products are never eligible for change-of-mind return
        if ticket.product_type == ProductType.FOOD:
            if action in (Action.APPROVE_RETURN, Action.REJECT_OPENED_ITEM):
                interventions.append("Food products are ineligible for change-of-mind returns.")
                action = Action.REJECT_FOOD_RETURN
                if "returns.md" not in sources:
                    sources.append("returns.md")

        # Rule: Opened non-food products cannot be returned
        elif ticket.opened_status == OpenedStatus.OPENED and ticket.product_type == ProductType.NON_FOOD:
            if action == Action.APPROVE_RETURN:
                interventions.append("Opened non-food items cannot be returned.")
                action = Action.REJECT_OPENED_ITEM
                if "returns.md" not in sources:
                    sources.append("returns.md")

        # Rule: Returns beyond 14 calendar days are rejected
        elif ticket.days_since_delivery is not None and ticket.days_since_delivery > 14:
            if action == Action.APPROVE_RETURN:
                interventions.append(
                    f"Return requested {ticket.days_since_delivery} days after delivery (limit: 14 days)."
                )
                action = Action.REJECT_OUTSIDE_WINDOW
                if "returns.md" not in sources:
                    sources.append("returns.md")

    # ------------------------------------------------------------------
    # 3. Defective Products Policy Rules
    # ------------------------------------------------------------------
    if inferred_type == IssueType.DEFECTIVE or "defective_products.md" in sources:
        # Rule: Defects > 14 days after delivery are ineligible
        if ticket.days_since_delivery is not None and ticket.days_since_delivery > 14:
            if action not in (Action.REJECT_OUTSIDE_WINDOW, Action.NEEDS_MORE_INFORMATION):
                interventions.append(
                    f"Defect reported {ticket.days_since_delivery} days after delivery (limit: 14 days)."
                )
                action = Action.REJECT_OUTSIDE_WINDOW
                if "defective_products.md" not in sources:
                    sources.append("defective_products.md")

        # Rule: Defective order value > ₹3,000 requires defect evidence
        elif ticket.order_value_inr is not None and ticket.order_value_inr > Decimal("3000"):
            if action == Action.APPROVE_REPLACEMENT:
                interventions.append(
                    f"Defective device valued at ₹{ticket.order_value_inr} (>₹3,000); defect evidence must be requested."
                )
                action = Action.REQUEST_DEFECT_EVIDENCE
                if "defective_products.md" not in sources:
                    sources.append("defective_products.md")

    # ------------------------------------------------------------------
    # 4. Cancellation Policy Rules
    # ------------------------------------------------------------------
    if inferred_type == IssueType.CANCELLATION or "cancellations.md" in sources:
        # Rule: Once dispatched, orders cannot be cancelled
        is_dispatched = (
            ticket.order_status == OrderStatus.DISPATCHED
            or (ticket.days_since_dispatch is not None and ticket.days_since_dispatch > 0)
        )
        if is_dispatched and action == Action.CANCEL_AND_REFUND:
            interventions.append("Order has already been dispatched and cannot be cancelled.")
            action = Action.CANNOT_CANCEL_AFTER_DISPATCH
            if "cancellations.md" not in sources:
                sources.append("cancellations.md")

    # Deduplicate sources while preserving order
    deduped_sources: list[str] = []
    for s in sources:
        if s not in deduped_sources:
            deduped_sources.append(s)

    if interventions:
        intervention_note = "; ".join(interventions)
        reason = f"[Guardrail Applied: {intervention_note}] {reason}"[:1500]

    updated_decision = DecisionDraft(
        action=action,
        confidence=confidence,
        reason=reason,
        sources=deduped_sources,
        inferred_issue_type=inferred_type,
        retrieval_latency_ms=decision.retrieval_latency_ms,
        llm_latency_ms=decision.llm_latency_ms,
        guardrail_triggered=bool(interventions),
    )
    return updated_decision, interventions
