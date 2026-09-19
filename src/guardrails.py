"""Deterministic policy guardrails (The Anti-Hallucination Firewall).

Neuro-symbolic validation layer: enforces strict numerical thresholds,
timing windows, and category exclusions deterministically before decisions
touch persistence.
"""

from __future__ import annotations

from decimal import Decimal
import logging
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

logger = logging.getLogger("support_assistant.guardrails")

# All actions that represent an approval/resolution in favor of refund or replacement
APPROVAL_ACTIONS: frozenset[Action] = frozenset({
    Action.APPROVE_REFUND_OR_REPLACEMENT,
    Action.APPROVE_REPLACEMENT,
    Action.OFFER_REPLACEMENT_OR_REFUND,
    Action.APPROVE_RETURN,
    Action.CANCEL_AND_REFUND,
    Action.REPLACE_CORRECT_ITEM,
})


def enforce_policy_guardrails(
    ticket: TicketRequest,
    decision: DecisionDraft,
) -> tuple[DecisionDraft, list[str]]:
    """Verify and correct LLM decisions against deterministic policy axioms.

    Returns:
        A tuple of (validated_or_corrected_decision, list_of_interventions).
    """
    interventions: list[str] = []
    raw_action = decision.action
    raw_reason = decision.reason
    action = decision.action
    reason = decision.reason
    inferred_type = decision.inferred_issue_type
    sources = list(decision.sources)
    confidence = decision.confidence

    # ------------------------------------------------------------------
    # 1. Damaged Goods Policy Rules
    # Gate strictly on inferred_type to eliminate cross-firing from citations
    # ------------------------------------------------------------------
    if inferred_type == IssueType.DAMAGED:
        # Rule 5: If delivery date or damage details missing, request more info
        if ticket.days_since_delivery is None:
            if action in APPROVAL_ACTIONS or action == Action.REJECT_OUTSIDE_WINDOW:
                interventions.append(
                    "Delivery date missing for damaged item; requesting more information per policy rule 5."
                )
                action = Action.NEEDS_MORE_INFORMATION
                if "damaged_goods.md" not in sources:
                    sources.append("damaged_goods.md")
        # Rule 1 & 4: Damage > 7 days after delivery is ineligible
        elif ticket.days_since_delivery > 7:
            if action != Action.REJECT_OUTSIDE_WINDOW:
                interventions.append(
                    f"Damaged item reported {ticket.days_since_delivery} days after delivery (limit: 7 days)."
                )
                action = Action.REJECT_OUTSIDE_WINDOW
                if "damaged_goods.md" not in sources:
                    sources.append("damaged_goods.md")
        # Rule 2 & 3: Damage <= 7 days and value > 2,000 requires photos
        elif ticket.order_value_inr is not None and ticket.order_value_inr > Decimal("2000"):
            if action in APPROVAL_ACTIONS and action != Action.REQUEST_PHOTOS:
                interventions.append(
                    f"Order value INR {ticket.order_value_inr} exceeds INR 2,000 threshold for automatic approval; photos required."
                )
                action = Action.REQUEST_PHOTOS
                if "damaged_goods.md" not in sources:
                    sources.append("damaged_goods.md")

    # ------------------------------------------------------------------
    # 2. Returns Policy Rules
    # ------------------------------------------------------------------
    elif inferred_type == IssueType.RETURN:
        # Rule 5: If product type, opened status, or delivery date missing
        if action in APPROVAL_ACTIONS:
            if ticket.product_type is None or ticket.product_type == ProductType.UNKNOWN:
                interventions.append(
                    "Product type unknown for return; requesting more information per policy rule 5."
                )
                action = Action.NEEDS_MORE_INFORMATION
                if "returns.md" not in sources:
                    sources.append("returns.md")
            elif ticket.days_since_delivery is None:
                interventions.append(
                    "Delivery date missing for return; requesting more information per policy rule 5."
                )
                action = Action.NEEDS_MORE_INFORMATION
                if "returns.md" not in sources:
                    sources.append("returns.md")
            elif (
                ticket.product_type == ProductType.NON_FOOD
                and (ticket.opened_status is None or ticket.opened_status == OpenedStatus.UNKNOWN)
            ):
                interventions.append(
                    "Opened/unopened status unknown for non-food return; requesting more information."
                )
                action = Action.NEEDS_MORE_INFORMATION
                if "returns.md" not in sources:
                    sources.append("returns.md")

        # Rule 3: Food products are never eligible for change-of-mind return
        if ticket.product_type == ProductType.FOOD and action in APPROVAL_ACTIONS:
            interventions.append("Food products are ineligible for change-of-mind returns.")
            action = Action.REJECT_FOOD_RETURN
            if "returns.md" not in sources:
                sources.append("returns.md")

        # Rule 2: Opened non-food products cannot be returned
        elif (
            ticket.opened_status == OpenedStatus.OPENED
            and ticket.product_type == ProductType.NON_FOOD
            and action in APPROVAL_ACTIONS
        ):
            interventions.append("Opened non-food items cannot be returned.")
            action = Action.REJECT_OPENED_ITEM
            if "returns.md" not in sources:
                sources.append("returns.md")

        # Rule 1: Returns beyond 14 calendar days are rejected
        elif ticket.days_since_delivery is not None and ticket.days_since_delivery > 14:
            if action in APPROVAL_ACTIONS or action != Action.REJECT_OUTSIDE_WINDOW:
                interventions.append(
                    f"Return requested {ticket.days_since_delivery} days after delivery (limit: 14 days)."
                )
                action = Action.REJECT_OUTSIDE_WINDOW
                if "returns.md" not in sources:
                    sources.append("returns.md")

    # ------------------------------------------------------------------
    # 3. Defective Products Policy Rules
    # ------------------------------------------------------------------
    elif inferred_type == IssueType.DEFECTIVE:
        # Rule 5: If delivery date missing, request more information
        if ticket.days_since_delivery is None:
            if action in APPROVAL_ACTIONS or action == Action.REJECT_OUTSIDE_WINDOW:
                interventions.append(
                    "Delivery date missing for defective product; requesting more information per policy rule 5."
                )
                action = Action.NEEDS_MORE_INFORMATION
                if "defective_products.md" not in sources:
                    sources.append("defective_products.md")
        # Rule 3: Defects > 14 days after delivery are ineligible
        elif ticket.days_since_delivery > 14:
            if action != Action.REJECT_OUTSIDE_WINDOW:
                interventions.append(
                    f"Defect reported {ticket.days_since_delivery} days after delivery (limit: 14 days)."
                )
                action = Action.REJECT_OUTSIDE_WINDOW
                if "defective_products.md" not in sources:
                    sources.append("defective_products.md")
        # Rule 2: Defective order value > INR 3,000 requires defect evidence
        elif ticket.order_value_inr is not None and ticket.order_value_inr > Decimal("3000"):
            if action in APPROVAL_ACTIONS and action != Action.REQUEST_DEFECT_EVIDENCE:
                interventions.append(
                    f"Defective device valued at INR {ticket.order_value_inr} (>INR 3,000); defect evidence must be requested."
                )
                action = Action.REQUEST_DEFECT_EVIDENCE
                if "defective_products.md" not in sources:
                    sources.append("defective_products.md")

    # ------------------------------------------------------------------
    # 4. Cancellation Policy Rules
    # ------------------------------------------------------------------
    elif inferred_type == IssueType.CANCELLATION:
        # Rule 4: If order dispatch status is unknown, request more information
        if ticket.order_status == OrderStatus.UNKNOWN or (
            ticket.order_status is None and ticket.days_since_dispatch is None
        ):
            if action in (Action.CANCEL_AND_REFUND, Action.CANNOT_CANCEL_AFTER_DISPATCH):
                interventions.append(
                    "Order dispatch status is unknown; requesting more information per policy rule 4."
                )
                action = Action.NEEDS_MORE_INFORMATION
                if "cancellations.md" not in sources:
                    sources.append("cancellations.md")
        else:
            # Rule 1 & 2: Once dispatched (or delivered), orders cannot be cancelled
            is_dispatched = (
                ticket.order_status in (OrderStatus.DISPATCHED, OrderStatus.DELIVERED)
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
        logger.info(
            "Guardrail intervened: raw_action=%s -> guarded_action=%s | notes: %s",
            raw_action,
            action,
            intervention_note,
        )

    updated_decision = DecisionDraft(
        action=action,
        raw_action=raw_action,
        raw_reason=raw_reason,
        confidence=confidence,
        reason=reason,
        sources=deduped_sources,
        inferred_issue_type=inferred_type,
        retrieval_latency_ms=decision.retrieval_latency_ms,
        llm_latency_ms=decision.llm_latency_ms,
        guardrail_triggered=bool(interventions),
    )
    return updated_decision, interventions
