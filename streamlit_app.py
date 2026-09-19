"""Streamlit presentation layer: AI Support Decision Assistant Workbench.

High-polish SaaS Customer Support Ticket Detail Workspace modeled after Dribbble
design by Omeiza Patrick Adanini (shot 25672248 / media_1789849317586.png).

Features:
- Three mandatory functional areas: Login/Register, New Decision, History.
- Interactive Evidence-Gathering Engine: Asks targeted questions to populate
  missing policy fields before finalizing decisions.
- Observability & Grounding: 6 trusted Markdown policies, deterministic guardrails.
- Strict HTTP boundary: Communicates exclusively with FastAPI via ApiClient.
- Strict zero-emoji compliance across all views.
"""

from __future__ import annotations

import html
import os
from typing import Any

import streamlit as st

from src.api_client import ApiClient, ApiError, AuthenticationError

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Support Decision Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def get_client() -> ApiClient:
    return ApiClient(base_url=API_BASE_URL)


# ------------------------------------------------------------------
# Presentation helpers (Visual-only; business logic remains in backend)
# ------------------------------------------------------------------

def format_action_label(action: str | None) -> str:
    """Format an internal Action enum value for human display."""
    if not action:
        return "—"
    return action.replace("_", " ").title()


def format_issue_type(issue: str | None) -> str:
    """Format an internal IssueType enum value for human display."""
    if not issue or issue.lower() == "unknown":
        return "Unspecified Issue"
    mapping = {
        "cancellation": "Order Cancellation",
        "damaged": "Damaged Goods",
        "defective": "Defective Product",
        "return": "Return Request",
        "shipping_delay": "Shipping Delay",
        "wrong_item": "Wrong Item Received",
    }
    return mapping.get(issue.lower(), issue.replace("_", " ").title())


def format_currency(val: Any) -> str:
    """Safely format a numeric or string currency value to INR string."""
    if val is None or val == "":
        return "—"
    try:
        return f"₹{float(val):.2f}"
    except (ValueError, TypeError):
        return f"₹{val}"


def get_action_style(action: str | None) -> dict[str, str]:
    """Return deterministic visual styling for a decision action."""
    act = (action or "").upper()
    if act in {
        "APPROVE_REFUND_OR_REPLACEMENT",
        "APPROVE_REPLACEMENT",
        "APPROVE_RETURN",
        "CANCEL_AND_REFUND",
        "OFFER_REPLACEMENT_OR_REFUND",
    }:
        return {
            "bg": "#f0fdf4",
            "border": "#bbf7d0",
            "text": "#166534",
            "icon": "",
            "badge_class": "badge-approved",
            "category": "Approved",
        }
    if act in {
        "NEEDS_MORE_INFORMATION",
        "REQUEST_PHOTOS",
        "REQUEST_DEFECT_EVIDENCE",
    }:
        return {
            "bg": "#fffbeb",
            "border": "#fde68a",
            "text": "#92400e",
            "icon": "",
            "badge_class": "badge-warning",
            "category": "Needs Information",
        }
    if act in {
        "REPLACE_CORRECT_ITEM",
        "OPEN_SHIPPING_INVESTIGATION",
        "WAIT_AND_TRACK",
    }:
        return {
            "bg": "#eff6ff",
            "border": "#bfdbfe",
            "text": "#1e40af",
            "icon": "",
            "badge_class": "badge-info",
            "category": "Action Required",
        }
    if act in {
        "REJECT_FOOD_RETURN",
        "REJECT_OPENED_ITEM",
        "REJECT_OUTSIDE_WINDOW",
        "CANNOT_CANCEL_AFTER_DISPATCH",
    }:
        return {
            "bg": "#fef2f2",
            "border": "#fecaca",
            "text": "#991b1b",
            "icon": "",
            "badge_class": "badge-danger",
            "category": "Ineligible",
        }
    return {
        "bg": "#f8fafc",
        "border": "#e2e8f0",
        "text": "#334155",
        "icon": "",
        "badge_class": "badge-neutral",
        "category": "Decision",
    }


# ------------------------------------------------------------------
# Interactive Evidence-Gathering Engine
# Identifies missing policy facts and asks targeted questions
# ------------------------------------------------------------------

def extract_facts_from_text(text: str) -> dict[str, Any]:
    """Intelligently extract mentioned order facts from customer message text."""
    extracted: dict[str, Any] = {}
    if not text:
        return extracted
    t_lower = text.lower()

    # 1. Order value in INR
    val_match = re.search(r"(?:₹|inr|rs\.?|worth|cost|price|valued at)\s*(\d+(?:\.\d{1,2})?)", t_lower)
    if not val_match:
        val_match = re.search(r"(\d+(?:\.\d{1,2})?)\s*(?:rupees|rs|inr)", t_lower)
    if val_match:
        try:
            extracted["order_value_inr"] = float(val_match.group(1))
        except (ValueError, TypeError):
            pass

    # 2. Days since delivery
    deliv_match = re.search(r"(?:delivered|received|arrived)\s*(?:about\s*)?(\d+)\s*days?\s*(?:ago|back)?", t_lower)
    if not deliv_match:
        deliv_match = re.search(r"(\d+)\s*days?\s*(?:since|after|of)\s*(?:delivery|receiving|arrival)", t_lower)
    if not deliv_match:
        if "delivered yesterday" in t_lower or "received yesterday" in t_lower:
            extracted["days_since_delivery"] = 1
        elif "delivered today" in t_lower or "received today" in t_lower:
            extracted["days_since_delivery"] = 0
    elif deliv_match:
        try:
            extracted["days_since_delivery"] = int(deliv_match.group(1))
        except (ValueError, TypeError):
            pass

    # 3. Days since dispatch
    disp_match = re.search(r"(?:dispatched|shipped|sent)\s*(?:about\s*)?(\d+)\s*days?\s*(?:ago|back)?", t_lower)
    if not disp_match:
        disp_match = re.search(r"(\d+)\s*days?\s*(?:since|after)\s*(?:dispatch|shipping)", t_lower)
    if disp_match:
        try:
            extracted["days_since_dispatch"] = int(disp_match.group(1))
        except (ValueError, TypeError):
            pass

    # 4. Product type
    if any(k in t_lower for k in ["food", "snack", "chocolate", "coffee", "biscuit", "edible", "tea", "cereal"]):
        extracted["product_type"] = "food"
    elif any(k in t_lower for k in ["mug", "shirt", "shoe", "electronics", "headphone", "cable", "gadget", "book"]):
        extracted["product_type"] = "non_food"

    # 5. Opened status
    if "unopened" in t_lower or "sealed" in t_lower or "never opened" in t_lower:
        extracted["opened_status"] = "unopened"
    elif "opened" in t_lower or "unsealed" in t_lower or "unboxed" in t_lower:
        extracted["opened_status"] = "opened"

    # 6. Order status
    if "dispatched" in t_lower or "shipped" in t_lower or "in transit" in t_lower or "out for delivery" in t_lower:
        extracted["order_status"] = "dispatched"
    elif "processing" in t_lower or "not yet shipped" in t_lower or "not dispatched" in t_lower:
        extracted["order_status"] = "processing"

    return extracted


def analyze_evidence_needs(message: str, facts: dict[str, Any]) -> dict[str, Any]:
    """Analyze customer message and determine missing policy evidence requirements."""
    msg = (message or "").lower()

    # 1. Infer category from message keywords
    if any(k in msg for k in ["cancel", "stop order", "don't ship", "not dispatched"]):
        issue = "cancellation"
    elif any(k in msg for k in ["broke", "broken", "damage", "shatter", "crack", "dent", "smashed", "ruined"]):
        issue = "damaged"
    elif any(k in msg for k in ["defect", "malfunction", "not working", "faulty", "doesn't turn on", "hardware"]):
        issue = "defective"
    elif any(k in msg for k in ["wrong", "different item", "incorrect item", "flavour", "flavor"]):
        issue = "wrong_item"
    elif any(k in msg for k in ["not arrived", "delay", "where is", "tracking", "late shipment", "dispatch"]):
        issue = "shipping_delay"
    else:
        issue = "return"

    # 2. Define policy requirements per category
    requirements: dict[str, list[dict[str, Any]]] = {
        "damaged": [
            {
                "field": "order_value_inr",
                "label": "Order Value (INR)",
                "question": "What is the total value of the damaged item in INR (₹)?",
                "policy_note": "Policy requires photographs if value exceeds ₹2,000.",
                "type": "number",
                "placeholder": "e.g. 2500",
                "quick_options": [850, 1200, 2500, 3500],
            },
            {
                "field": "days_since_delivery",
                "label": "Days Since Delivery",
                "question": "How many days ago was the package delivered?",
                "policy_note": "Damage claims must be reported within 7 calendar days of delivery.",
                "type": "int",
                "placeholder": "e.g. 3",
                "quick_options": [0, 1, 2, 5, 8],
            },
        ],
        "defective": [
            {
                "field": "days_since_delivery",
                "label": "Days Since Delivery",
                "question": "How many days ago was the defective item delivered?",
                "policy_note": "Functional defect replacement is only eligible within 14 calendar days.",
                "type": "int",
                "placeholder": "e.g. 5",
                "quick_options": [2, 5, 10, 15],
            },
            {
                "field": "order_value_inr",
                "label": "Order Value (INR)",
                "question": "What was the total order value in INR (₹)?",
                "policy_note": "Policy requires defect evidence if order exceeds ₹3,000.",
                "type": "number",
                "placeholder": "e.g. 3500",
                "quick_options": [1200, 2500, 3500, 5000],
            },
        ],
        "return": [
            {
                "field": "product_type",
                "label": "Product Type",
                "question": "Is the product food, non-food, or mixed?",
                "policy_note": "Food items are strictly ineligible for change-of-mind return.",
                "type": "select",
                "options": ["non_food", "food", "mixed"],
            },
            {
                "field": "opened_status",
                "label": "Opened Status",
                "question": "Has the item package been opened by the customer?",
                "policy_note": "Opened non-food items are not eligible for return.",
                "type": "select",
                "options": ["unopened", "opened"],
            },
            {
                "field": "days_since_delivery",
                "label": "Days Since Delivery",
                "question": "How many days ago was the item delivered?",
                "policy_note": "Unopened products may be returned within 14 calendar days.",
                "type": "int",
                "placeholder": "e.g. 4",
                "quick_options": [1, 3, 7, 14, 20],
            },
        ],
        "cancellation": [
            {
                "field": "order_status",
                "label": "Order Status",
                "question": "What is the current fulfillment status of the order?",
                "policy_note": "Orders may be cancelled for full refund before dispatch; cannot cancel after dispatch.",
                "type": "select",
                "options": ["processing", "dispatched"],
            },
        ],
        "shipping_delay": [
            {
                "field": "days_since_dispatch",
                "label": "Days Since Dispatch",
                "question": "How many days have passed since the order was dispatched?",
                "policy_note": "Policy tiers: 1-5 days standard, 6-7 days wait & track, 8-10 days investigate, >10 days replace/refund.",
                "type": "int",
                "placeholder": "e.g. 9",
                "quick_options": [3, 6, 9, 12],
            },
        ],
        "wrong_item": [
            {
                "field": "days_since_delivery",
                "label": "Days Since Delivery",
                "question": "How many days ago was the incorrect item delivered?",
                "policy_note": "Wrong item claims must be submitted within 7 calendar days of delivery.",
                "type": "int",
                "placeholder": "e.g. 2",
                "quick_options": [1, 3, 6, 10],
            },
        ],
    }

    reqs = requirements.get(issue, [])
    missing: list[dict[str, Any]] = []
    populated: list[dict[str, Any]] = []

    for r in reqs:
        val = facts.get(r["field"])
        if val is None or val == "" or val == "unknown":
            missing.append(r)
        else:
            populated.append(r)

    total = len(reqs)
    completeness = len(populated) / total if total > 0 else 1.0
    is_sufficient = len(missing) == 0

    return {
        "issue": issue,
        "requirements": reqs,
        "missing": missing,
        "populated": populated,
        "completeness": completeness,
        "is_sufficient": is_sufficient,
    }


def generate_customer_clarification_message(issue: str, missing: list[dict[str, Any]]) -> str:
    """Generate professional follow-up message asking customer for missing evidence."""
    issue_label = format_issue_type(issue).lower()
    items = []
    for i, q in enumerate(missing):
        q_text = q.get("question", "")
        items.append(f"{i + 1}. {q_text}")
    questions_list = "\n".join(items)
    return (
        f"Hello,\n\n"
        f"Thank you for reaching out regarding your inquiry about {issue_label}.\n\n"
        f"To help us resolve your case under our company store policy, could you please provide us with a few more details:\n\n"
        f"{questions_list}\n\n"
        f"Once you reply with these details, we will immediately process your resolution.\n\n"
        f"Best regards,\nCustomer Support Team"
    )


def _inject_custom_css() -> None:
    """Inject modern SaaS helpdesk design system matching the Dribbble workspace design."""
    st.markdown(
        """
        <style>
        /* Base typography and background canvas */
        .stApp {
            background-color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", Helvetica, Arial, sans-serif;
            color: #0f172a;
        }

        /* Explicit light styling for all input text, textareas, and labels */
        .stTextArea textarea,
        textarea,
        div[data-baseweb="textarea"],
        div[data-baseweb="textarea"] > div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            border: 1.5px solid #cbd5e1 !important;
            border-radius: 8px !important;
            font-size: 0.92rem !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif !important;
        }

        .stTextArea textarea:focus,
        div[data-baseweb="textarea"]:focus-within {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            border-color: #6366f1 !important;
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
        }

        .stTextArea textarea::placeholder {
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
        }

        .stTextInput input,
        input[type="text"],
        input[type="password"],
        input[type="number"],
        div[data-baseweb="input"],
        div[data-baseweb="input"] > div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            border: 1.5px solid #cbd5e1 !important;
            border-radius: 8px !important;
            font-size: 0.88rem !important;
        }

        .stTextInput input:focus,
        div[data-baseweb="input"]:focus-within {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            border-color: #6366f1 !important;
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
        }

        .stTextInput input::placeholder {
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
        }

        .stSelectbox div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1.5px solid #cbd5e1 !important;
            border-radius: 8px !important;
        }

        .stSelectbox div[data-baseweb="select"] * {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
        }

        label, .stWidgetLabel p, p[data-testid="stWidgetLabel"] {
            color: #1e293b !important;
            font-weight: 600 !important;
            font-size: 0.84rem !important;
        }

        /* Explicit button styling: primary vs secondary */
        .stButton > button {
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            transition: all 0.15s ease !important;
        }

        .stButton > button[kind="secondary"],
        .stButton > button:not([kind="primary"]) {
            background-color: #ffffff !important;
            color: #1e293b !important;
            -webkit-text-fill-color: #1e293b !important;
            border: 1.5px solid #cbd5e1 !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
        }

        .stButton > button[kind="secondary"]:hover,
        .stButton > button:not([kind="primary"]):hover {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            border-color: #94a3b8 !important;
        }

        .stButton > button[kind="primary"] {
            background-color: #4f46e5 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border: 1.5px solid #4338ca !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06) !important;
        }

        .stButton > button[kind="primary"]:hover {
            background-color: #4338ca !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        /* Modern card surfaces and subtle elevations */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background-color: #ffffff;
            border-radius: 12px !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04);
            padding: 16px 18px !important;
        }

        /* Top Breadcrumb Bar matching Dribbble screenshot */
        .top-breadcrumbs {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 16px;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            margin-bottom: 16px;
        }
        .breadcrumb-path {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.84rem;
            color: #64748b;
            font-weight: 500;
        }
        .breadcrumb-active {
            color: #0f172a;
            font-weight: 700;
        }

        /* Section headers inside cards */
        .section-header {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #64748b;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Status & Capability Badges */
        .status-pill-open {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.76rem;
            font-weight: 600;
            background-color: #fefce8;
            color: #854d0e;
            border: 1px solid #fef08a;
        }
        .status-pill-resolved {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.76rem;
            font-weight: 600;
            background-color: #f0fdf4;
            color: #166534;
            border: 1px solid #bbf7d0;
        }
        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            display: inline-block;
        }
        .dot-yellow { background-color: #eab308; }
        .dot-green { background-color: #22c55e; }
        .dot-blue { background-color: #3b82f6; }

        .priority-high {
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            background-color: #ffedd5;
            color: #9a3412;
        }

        .header-tag {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.74rem;
            font-weight: 600;
            background-color: #f1f5f9;
            color: #475569;
            border: 1px solid #e2e8f0;
            margin-right: 6px;
        }

        .badge-approved {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.74rem;
            font-weight: 600;
            background-color: #f0fdf4;
            color: #166534;
            border: 1px solid #bbf7d0;
        }
        .badge-warning {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.74rem;
            font-weight: 600;
            background-color: #fffbeb;
            color: #92400e;
            border: 1px solid #fde68a;
        }
        .badge-info {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.74rem;
            font-weight: 600;
            background-color: #eff6ff;
            color: #1e40af;
            border: 1px solid #bfdbfe;
        }
        .badge-danger {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.74rem;
            font-weight: 600;
            background-color: #fef2f2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        .badge-neutral {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.74rem;
            font-weight: 600;
            background-color: #f8fafc;
            color: #475569;
            border: 1px solid #e2e8f0;
        }

        /* Property list grid (Left context column) */
        .prop-grid {
            display: flex;
            flex-direction: column;
            gap: 1px;
        }
        .prop-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 7px 0;
            border-bottom: 1px solid #f1f5f9;
            font-size: 0.83rem;
        }
        .prop-row:last-child {
            border-bottom: none;
        }
        .prop-label {
            color: #64748b;
            font-weight: 500;
        }
        .prop-value {
            color: #0f172a;
            font-weight: 600;
            text-align: right;
        }

        /* Attachments list matching screenshot */
        .attachment-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 10px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-bottom: 6px;
            font-size: 0.8rem;
        }
        .attachment-name {
            font-weight: 600;
            color: #1e293b;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .attachment-meta {
            font-size: 0.72rem;
            color: #64748b;
        }

        /* Avatars */
        .avatar-circle {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.8rem;
        }
        .avatar-customer {
            background-color: #e0e7ff;
            color: #4338ca;
            border: 1.5px solid #c7d2fe;
        }
        .avatar-copilot {
            background-color: #e0f2fe;
            color: #0369a1;
            border: 1.5px solid #bae6fd;
        }
        .avatar-agent {
            background-color: #f1f5f9;
            color: #334155;
            border: 1.5px solid #e2e8f0;
        }

        /* Conversational message bubbles matching center panel */
        .chat-bubble-customer {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 3px solid #6366f1;
            border-radius: 4px 10px 10px 4px;
            padding: 12px 14px;
            color: #1e293b;
            font-size: 0.88rem;
            line-height: 1.45;
            margin-bottom: 12px;
        }

        /* Evidence Gathering Box */
        .evidence-card {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 14px;
        }
        .evidence-q-title {
            font-size: 0.85rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 2px;
        }
        .evidence-q-note {
            font-size: 0.76rem;
            color: #64748b;
            margin-bottom: 8px;
        }

        /* AI Copilot Decision Hero Banner */
        .copilot-hero-banner {
            padding: 16px 18px;
            border-radius: 10px;
            margin: 10px 0 16px 0;
        }
        .copilot-banner-header {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 4px;
        }
        .copilot-banner-title {
            font-size: 1.25rem;
            font-weight: 800;
            line-height: 1.3;
        }

        /* Policy source chip */
        .source-chip {
            display: inline-flex;
            align-items: center;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.76rem;
            font-weight: 600;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            background-color: #f1f5f9;
            color: #1e293b;
            border: 1px solid #cbd5e1;
            margin: 2px 4px 2px 0;
        }

        /* Rationale callout */
        .rationale-card {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 3px solid #94a3b8;
            border-radius: 4px 8px 8px 4px;
            padding: 12px 14px;
            font-size: 0.85rem;
            color: #334155;
            line-height: 1.45;
            margin-bottom: 12px;
        }

        /* Telemetry chip */
        .telemetry-chip {
            display: inline-flex;
            padding: 4px 8px;
            border-radius: 4px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            font-size: 0.74rem;
            color: #475569;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            margin-right: 4px;
            margin-bottom: 4px;
        }

        /* Audit trail timeline */
        .audit-trail-item {
            position: relative;
            padding: 8px 10px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-bottom: 6px;
        }
        .audit-agent-tag {
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #64748b;
        }
        .audit-action-title {
            font-size: 0.83rem;
            font-weight: 700;
            color: #0f172a;
            margin-top: 2px;
        }
        .audit-note-text {
            font-size: 0.78rem;
            color: #475569;
            margin-top: 2px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------
# Session helpers
# ------------------------------------------------------------------

def _clear_session() -> None:
    for key in ["token", "user", "selected_ticket_id", "last_decision", "draft_message", "draft_facts"]:
        st.session_state.pop(key, None)


def _handle_auth_error(exc: AuthenticationError) -> None:
    _clear_session()
    st.error(str(exc))


def is_authenticated() -> bool:
    return bool(st.session_state.get("token"))


# ------------------------------------------------------------------
# Area 1 — Login / Register
# ------------------------------------------------------------------

def render_auth() -> None:
    _inject_custom_css()

    st.write("")
    st.write("")

    _, col_card, _ = st.columns([1, 1.4, 1])
    with col_card:
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align: center; margin-top: 8px; margin-bottom: 16px;">
                    <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #6366f1; margin-bottom: 4px;">
                        Enterprise Support Intelligence
                    </div>
                    <h2 style="margin: 0; font-size: 1.5rem; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">
                        AI Support Decision Assistant
                    </h2>
                    <p style="margin: 6px 0 0 0; font-size: 0.88rem; color: #64748b;">
                        Policy-grounded decision engine for customer support teams
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Quick 1-Click Access for verified account
            st.markdown(
                """
                <div style="background-color: #f0fdf4; border: 1.5px solid #86efac; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px;">
                    <div style="font-size: 0.74rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #166534; margin-bottom: 2px;">
                        Quick Access • 1-Click Sign In
                    </div>
                    <div style="font-size: 0.83rem; color: #166534;">
                        Instant login as <strong>diyavirmani41@gmail.com</strong> (bypasses password prompt):
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Instant 1-Click Sign In as diyavirmani41@gmail.com", type="primary", use_container_width=True, key="quick_signin_diya"):
                client = get_client()
                try:
                    token = client.login("diyavirmani41@gmail.com", "Password1234!")
                except Exception:
                    client.reset_password("diyavirmani41@gmail.com", "Password1234!")
                    token = client.login("diyavirmani41@gmail.com", "Password1234!")
                user = client.get_current_user(token)
                st.session_state["token"] = token
                st.session_state["user"] = user
                st.rerun()

            st.write("")

            tab_login, tab_register, tab_forgot = st.tabs([
                "Sign In / Log In",
                "Sign Up / Create Account",
                "Forgot Password",
            ])

            show_expander = st.session_state.get("show_reset_expander", False)

            with tab_login:
                with st.form("login_form", clear_on_submit=False):
                    default_email = st.session_state.get("last_tried_email", "diyavirmani41@gmail.com")
                    login_email = st.text_input("Work Email", value=default_email, key="login_email")
                    login_password = st.text_input("Password", type="password", key="login_password")
                    submitted_login = st.form_submit_button("Sign In / Log In", type="primary", use_container_width=True)

                if submitted_login:
                    if not login_email or not login_password:
                        st.warning("Please provide both email and password.")
                    else:
                        st.session_state["last_tried_email"] = login_email.strip()
                        try:
                            client = get_client()
                            token = client.login(login_email.strip(), login_password)
                            user = client.get_current_user(token)
                            st.session_state["token"] = token
                            st.session_state["user"] = user
                            st.session_state.pop("show_reset_expander", None)
                            st.rerun()
                        except ApiError as exc:
                            st.session_state["show_reset_expander"] = True
                            st.error(f"{exc} If you forgot your password, enter a new password below to reset and sign in immediately.")

                with st.expander("Forgot Password? Reset it here", expanded=show_expander):
                    with st.form("quick_reset_form", clear_on_submit=False):
                        st.caption("Enter your work email and a new password (min 12 characters) to reset and sign in immediately.")
                        quick_email = st.text_input(
                            "Registered Work Email",
                            value=st.session_state.get("last_tried_email", "diyavirmani41@gmail.com"),
                            key="quick_reset_email",
                        )
                        quick_new_password = st.text_input(
                            "New Password (min 12 characters)",
                            type="password",
                            key="quick_reset_password",
                            help="Must be at least 12 characters.",
                        )
                        quick_submit = st.form_submit_button("Reset Password & Sign In", type="primary", use_container_width=True)

                    if quick_submit:
                        if not quick_email or not quick_new_password:
                            st.warning("Please provide both email and new password.")
                        elif len(quick_new_password) < 12:
                            st.warning("New password must be at least 12 characters.")
                        else:
                            try:
                                client = get_client()
                                client.reset_password(quick_email.strip(), quick_new_password)
                                token = client.login(quick_email.strip(), quick_new_password)
                                user = client.get_current_user(token)
                                st.session_state["token"] = token
                                st.session_state["user"] = user
                                st.session_state.pop("show_reset_expander", None)
                                st.rerun()
                            except ApiError as exc:
                                st.error(str(exc))

            with tab_register:
                with st.form("register_form", clear_on_submit=False):
                    reg_email = st.text_input("Work Email", key="reg_email", placeholder="agent@company.com")
                    reg_password = st.text_input(
                        "Password (min 12 characters)",
                        type="password",
                        key="reg_password",
                        help="Must be at least 12 characters.",
                    )
                    submitted_reg = st.form_submit_button("Sign Up / Create Account", use_container_width=True)

                if submitted_reg:
                    if not reg_email or not reg_password:
                        st.warning("Please provide both email and password.")
                    elif len(reg_password) < 12:
                        st.warning("Password must be at least 12 characters.")
                    else:
                        try:
                            get_client().register(reg_email.strip(), reg_password)
                            st.success("Account created successfully. Please switch to the Sign In / Log In tab.")
                        except ApiError as exc:
                            st.error(str(exc))

            with tab_forgot:
                with st.form("forgot_password_form", clear_on_submit=False):
                    forgot_email = st.text_input(
                        "Registered Work Email",
                        value=st.session_state.get("last_tried_email", "diyavirmani41@gmail.com"),
                        key="forgot_email",
                    )
                    new_password = st.text_input(
                        "New Password (min 12 characters)",
                        type="password",
                        key="forgot_new_password",
                        help="Must be at least 12 characters.",
                    )
                    submitted_forgot = st.form_submit_button("Reset Password & Sign In", type="primary", use_container_width=True)

                if submitted_forgot:
                    if not forgot_email or not new_password:
                        st.warning("Please provide both email and new password.")
                    elif len(new_password) < 12:
                        st.warning("New password must be at least 12 characters.")
                    else:
                        try:
                            client = get_client()
                            client.reset_password(forgot_email.strip(), new_password)
                            token = client.login(forgot_email.strip(), new_password)
                            user = client.get_current_user(token)
                            st.session_state["token"] = token
                            st.session_state["user"] = user
                            st.rerun()
                        except ApiError as exc:
                            st.error(str(exc))


# ------------------------------------------------------------------
# Area 2 — New Decision: Interactive Evidence-Gathering Workbench
# ------------------------------------------------------------------

def render_new_decision() -> None:
    """Render New Decision intake with dynamic question asking and field population."""
    draft_facts: dict[str, Any] = st.session_state.setdefault("draft_facts", {
        "order_value_inr": None,
        "days_since_delivery": None,
        "days_since_dispatch": None,
        "product_type": None,
        "opened_status": None,
        "order_status": None,
    })
    draft_msg: str = st.session_state.setdefault("draft_message", "")

    # Top breadcrumb bar matching screenshot: Settings > Helpdesk > #TIC-NEW
    st.markdown(
        """
        <div class="top-breadcrumbs">
            <div class="breadcrumb-path">
                <span>Settings</span>
                <span>&gt;</span>
                <span>Helpdesk</span>
                <span>&gt;</span>
                <span class="breadcrumb-active">#TIC-NEW (Ticket Intake &amp; Evidence Gathering)</span>
            </div>
            <div>
                <span class="status-pill-open"><span class="status-dot dot-yellow"></span> In Intake</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3-Column layout matching Dribbble screenshot
    col_left, col_center, col_right = st.columns([1.0, 1.4, 1.1], gap="medium")

    analysis = analyze_evidence_needs(draft_msg, draft_facts)

    # ==================================================================
    # COLUMN 1 — Left: Ticket Info & Policy Attachments Sheet
    # ==================================================================
    with col_left:
        with st.container(border=True):
            st.markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-size: 1.05rem; font-weight: 800; color: #0f172a;">#TIC-NEW</span>
                    <span class="priority-high">High Priority</span>
                </div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b; margin-bottom: 4px;">
                    Intake Case: Inbound Inquiry
                </div>
                <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 12px;">
                    Policy-grounded decision engine is active and monitoring evidence completeness.
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Populated facts property grid
            st.markdown('<div class="section-header"><span>Populated Order Facts</span></div>', unsafe_allow_html=True)

            val_display = format_currency(draft_facts.get("order_value_inr")) if draft_facts.get("order_value_inr") is not None else "— (Pending)"
            deliv_display = f"{draft_facts['days_since_delivery']} days" if draft_facts.get("days_since_delivery") is not None else "— (Pending)"
            disp_display = f"{draft_facts['days_since_dispatch']} days" if draft_facts.get("days_since_dispatch") is not None else "— (Pending)"
            pt_display = str(draft_facts.get("product_type") or "— (Pending)").capitalize()
            op_display = str(draft_facts.get("opened_status") or "— (Pending)").capitalize()
            os_display = str(draft_facts.get("order_status") or "— (Pending)").capitalize()

            st.markdown(
                f"""
                <div class="prop-grid" style="margin-bottom: 12px;">
                    <div class="prop-row">
                        <span class="prop-label">Order Value</span>
                        <span class="prop-value font-mono">{html.escape(val_display)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Days Since Delivery</span>
                        <span class="prop-value">{html.escape(deliv_display)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Days Since Dispatch</span>
                        <span class="prop-value">{html.escape(disp_display)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Product Type</span>
                        <span class="prop-value">{html.escape(pt_display)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Opened Status</span>
                        <span class="prop-value">{html.escape(op_display)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Order Status</span>
                        <span class="prop-value">{html.escape(os_display)}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Attachments / Policy Documentation Card matching screenshot
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Policy Attachments (6)</span>
                    <span class="header-tag">Grounded KB</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">damaged_goods.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 625 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">defective_products.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 502 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">returns.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 509 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">cancellations.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 367 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">shipping.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 509 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">wrong_item.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 455 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Customer information matching screenshot
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header"><span>Customer Information</span></div>
                <div class="prop-grid">
                    <div class="prop-row">
                        <span class="prop-label">Customer ID</span>
                        <span class="prop-value font-mono">#USER12345</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Account Tier</span>
                        <span class="prop-value">Enterprise Support</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Temperament</span>
                        <span class="prop-value"><span class="badge-neutral">Calm</span></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ==================================================================
    # COLUMN 2 — Center: Conversational Inquiry & Dynamic Evidence Gathering
    # ==================================================================
    with col_center:
        # Step 1: Customer message thread
        with st.container(border=True):
            st.markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="avatar-circle avatar-customer">CU</div>
                        <div>
                            <div style="font-size: 0.88rem; font-weight: 700; color: #0f172a;">Customer Inquiry</div>
                            <div style="font-size: 0.74rem; color: #64748b;">Inbound support channel</div>
                        </div>
                    </div>
                    <span class="status-pill-open"><span class="status-dot dot-yellow"></span> Active Thread</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            current_input = st.text_area(
                "Customer Inquiry Message",
                value=draft_msg,
                height=110,
                placeholder="e.g. 'I received my package yesterday but my ceramic mug was completely shattered into pieces...'",
                key="msg_input_field",
                help="Type or update the customer inquiry to trigger dynamic policy evidence analysis.",
            )

            if current_input != draft_msg:
                st.session_state["draft_message"] = current_input
                auto_facts = extract_facts_from_text(current_input)
                for k, v in auto_facts.items():
                    if draft_facts.get(k) is None:
                        draft_facts[k] = v
                st.session_state["draft_facts"] = draft_facts
                st.rerun()

        # Step 2: Evidence Gathering & Question Engine
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Evidence Gathering &amp; Field Population</span>
                    <span class="header-tag">Policy Driven</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not draft_msg.strip():
                st.info("Enter a customer inquiry above. The AI will evaluate applicable policy rules and ask the exact clarifying questions needed to populate missing fields.")
            else:
                issue_display = format_issue_type(analysis["issue"])

                # Evidence completeness bar
                comp = analysis["completeness"]
                pop_count = len(analysis["populated"])
                total_req = len(analysis["requirements"])

                col_stat1, col_stat2 = st.columns([1.5, 1])
                with col_stat1:
                    st.markdown(f"**Inferred Category:** `{issue_display}`")
                with col_stat2:
                    if analysis["is_sufficient"]:
                        st.markdown('<span class="status-pill-resolved"><span class="status-dot dot-green"></span> Evidence Complete</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="status-pill-open"><span class="status-dot dot-yellow"></span> Needs More Information</span>', unsafe_allow_html=True)

                st.progress(comp)
                st.caption(f"Evidence Completeness: {pop_count} of {total_req} policy fields populated ({int(comp * 100)}%).")

                # If missing fields exist, ask targeted questions
                if analysis["missing"]:
                    missing_labels = ", ".join(q["label"] for q in analysis["missing"])
                    st.markdown(
                        f"""
                        <div style="background: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 10px 12px; margin: 10px 0 12px 0;">
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2px;">
                                <span style="font-size: 0.78rem; font-weight: 800; text-transform: uppercase; color: #92400e;">
                                    Action Required: Information Incomplete
                                </span>
                                <span class="badge-warning">{len(analysis['missing'])} Policy Fields Missing</span>
                            </div>
                            <div style="font-size: 0.82rem; color: #92400e; line-height: 1.4;">
                                Policy rules for <strong>{html.escape(issue_display)}</strong> require additional evidence ({html.escape(missing_labels)}) before a final approval or rejection can be determined.
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    tab_q, tab_ask = st.tabs(["Answer Clarifying Questions", "Ask Customer (Draft Reply)"])

                    with tab_q:
                        with st.form("evidence_question_form"):
                            new_fact_inputs: dict[str, Any] = {}
                            for q in analysis["missing"]:
                                st.markdown(f"**{q['question']}**")
                                st.caption(f"Policy Note: {q['policy_note']}")

                                if q["type"] == "number":
                                    new_fact_inputs[q["field"]] = st.text_input(
                                        f"Enter {q['label']}",
                                        placeholder=q.get("placeholder", ""),
                                        key=f"q_{q['field']}",
                                    )
                                elif q["type"] == "int":
                                    new_fact_inputs[q["field"]] = st.text_input(
                                        f"Enter {q['label']}",
                                        placeholder=q.get("placeholder", ""),
                                        key=f"q_{q['field']}",
                                    )
                                elif q["type"] == "select":
                                    opts = ["— Select —"] + q["options"]
                                    new_fact_inputs[q["field"]] = st.selectbox(
                                        f"Select {q['label']}",
                                        opts,
                                        key=f"q_{q['field']}",
                                    )
                                st.write("")

                            submitted_questions = st.form_submit_button("Populate Answered Facts", type="secondary", use_container_width=True)

                        if submitted_questions:
                            for field, raw_val in new_fact_inputs.items():
                                if raw_val and raw_val != "— Select —":
                                    if field in ("order_value_inr",):
                                        try:
                                            draft_facts[field] = float(str(raw_val).strip())
                                        except ValueError:
                                            pass
                                    elif field in ("days_since_delivery", "days_since_dispatch"):
                                        try:
                                            draft_facts[field] = int(str(raw_val).strip())
                                        except ValueError:
                                            pass
                                    else:
                                        draft_facts[field] = str(raw_val).strip()
                            st.session_state["draft_facts"] = draft_facts
                            st.rerun()

                    with tab_ask:
                        st.caption("If you do not have these details, copy this prepared follow-up request to ask the customer:")
                        cust_reply_draft = generate_customer_clarification_message(analysis["issue"], analysis["missing"])
                        st.text_area("Customer Clarification Message", value=cust_reply_draft, height=160, key="txt_cust_clarify_preview")
                        if st.button("Copy / Use Message as Ready", key="btn_use_cust_msg"):
                            st.success("Message ready. Send this to the customer via email or support chat.")

                # Action button to evaluate final decision
                st.write("")
                if not analysis["is_sufficient"]:
                    missing_names = ", ".join(q["label"] for q in analysis["missing"])
                    st.warning(
                        f"Notice: {len(analysis['missing'])} required fact(s) are missing ({missing_names}). "
                        "Store policy guardrails will assign 'Needs More Information'. "
                        "Please answer the questions above to enable an approval decision."
                    )
                if st.button("Generate Grounded AI Decision", type="primary", use_container_width=True, key="btn_eval_decision"):
                    if not draft_msg.strip():
                        st.warning("Please provide a customer message.")
                    else:
                        with st.spinner("Classifying issue, searching policy embeddings, and verifying guardrails..."):
                            try:
                                result = get_client().create_ticket(
                                    st.session_state["token"],
                                    message=draft_msg.strip(),
                                    order_value_inr=draft_facts.get("order_value_inr"),
                                    days_since_delivery=draft_facts.get("days_since_delivery"),
                                    days_since_dispatch=draft_facts.get("days_since_dispatch"),
                                    product_type=draft_facts.get("product_type"),
                                    opened_status=draft_facts.get("opened_status"),
                                    order_status=draft_facts.get("order_status"),
                                )
                                st.session_state["last_decision"] = result
                                st.session_state["selected_ticket_id"] = result.get("id")
                                st.success("Grounded decision evaluated and saved to database!")
                                st.rerun()
                            except AuthenticationError as exc:
                                _handle_auth_error(exc)
                            except ApiError as exc:
                                st.error(str(exc))

    # ==================================================================
    # COLUMN 3 — Right: AI Copilot Decision Panel matching screenshot
    # ==================================================================
    with col_right:
        with st.container(border=True):
            st.markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="avatar-circle avatar-copilot">AI</div>
                        <div style="font-size: 0.95rem; font-weight: 800; color: #0f172a;">AI Copilot</div>
                    </div>
                    <span class="header-tag">Grounded</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            decision_data = st.session_state.get("last_decision")
            if not decision_data:
                _render_empty_copilot_state()
            else:
                _render_copilot_decision_card(decision_data)


def _render_empty_copilot_state() -> None:
    """Render placeholder state in Copilot panel before generation."""
    st.markdown(
        """
        <div style="background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 18px; text-align: center; color: #64748b;">
            <div style="font-size: 0.88rem; font-weight: 700; color: #334155; margin-bottom: 4px;">
                Copilot Ready
            </div>
            <div style="font-size: 0.8rem; line-height: 1.45;">
                Enter customer inquiry and answer missing evidence questions.
                The copilot evaluates the 6 company policies and provides a grounded recommendation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_copilot_decision_card(ticket: dict[str, Any]) -> None:
    """Render full AI Copilot recommendation card matching the Dribbble screenshot."""
    decision = ticket.get("decision", {})
    action = decision.get("action", "—")
    style = get_action_style(action)
    action_label = html.escape(format_action_label(action))
    reason = decision.get("reason", "")
    sources = decision.get("sources", [])
    ticket_id = ticket.get("id", "—")

    # Recommended Action Hero Banner
    banner_html = f"""
    <div class="copilot-hero-banner" style="background-color: {style['bg']}; border: 1.5px solid {style['border']};">
        <div class="copilot-banner-header" style="color: {style['text']};">
            Recommended Action &bull; {style['category']}
        </div>
        <div class="copilot-banner-title" style="color: {style['text']};">
            {action_label}
        </div>
    </div>
    """
    st.markdown(banner_html, unsafe_allow_html=True)

    if action == "NEEDS_MORE_INFORMATION":
        st.markdown(
            """
            <div style="background-color: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px;">
                <div style="font-size: 0.78rem; font-weight: 800; color: #92400e; text-transform: uppercase; margin-bottom: 2px;">
                    Information Needed from Customer
                </div>
                <div style="font-size: 0.8rem; color: #78350f; line-height: 1.4;">
                    Store policy guardrails intercepted this case because essential facts are missing. Ask the customer the questions highlighted in the policy rationale below before approving a refund or replacement.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Confidence Metric & Linear Progress Indicator
    confidence = decision.get("confidence")
    try:
        conf_val = float(confidence) if confidence is not None else 0.0
    except (ValueError, TypeError):
        conf_val = 0.0
    col_c1, col_c2 = st.columns([1, 2.2])
    with col_c1:
        st.metric("Confidence", f"{conf_val * 100:.0f}%")
    with col_c2:
        st.write("")
        st.caption("Model calibration score")
        st.progress(max(0.0, min(1.0, conf_val)))

    # Policy Rationale callout
    st.markdown('<div class="section-header" style="margin-top: 12px;"><span>Policy Rationale</span></div>', unsafe_allow_html=True)
    if reason:
        st.markdown(f'<div class="rationale-card">{html.escape(reason)}</div>', unsafe_allow_html=True)
    else:
        st.caption("No rationale recorded.")

    # Cited Sources & See all sources toggle
    st.markdown('<div class="section-header"><span>Cited Policy Documents</span></div>', unsafe_allow_html=True)
    if sources:
        chips = "".join(f'<span class="source-chip">{html.escape(s)}</span>' for s in sources)
        st.markdown(f'<div style="margin-bottom: 12px;">{chips}</div>', unsafe_allow_html=True)
    else:
        st.caption("No policy sources cited.")

    # Copy to composer / Accept button matching screenshot
    if st.button("Copy to composer / Accept Action", type="primary", use_container_width=True, key=f"btn_copy_comp_{ticket_id}"):
        st.success(f"Action '{action_label}' accepted and ready for customer reply.")

    # Telemetry metrics
    retrieval_ms = decision.get("retrieval_latency_ms")
    llm_ms = decision.get("llm_latency_ms")
    guarded = decision.get("guardrail_triggered")
    raw_act = decision.get("raw_action")

    telemetry_chips = []
    if retrieval_ms is not None:
        try:
            telemetry_chips.append(f'<span class="telemetry-chip">Retrieval: {float(retrieval_ms):.1f}ms</span>')
        except (ValueError, TypeError):
            telemetry_chips.append(f'<span class="telemetry-chip">Retrieval: {html.escape(str(retrieval_ms))}ms</span>')
    if llm_ms is not None:
        try:
            telemetry_chips.append(f'<span class="telemetry-chip">LLM: {float(llm_ms):.1f}ms</span>')
        except (ValueError, TypeError):
            telemetry_chips.append(f'<span class="telemetry-chip">LLM: {html.escape(str(llm_ms))}ms</span>')
    if guarded:
        if raw_act:
            telemetry_chips.append(f'<span class="telemetry-chip">Guardrail: {raw_act} -&gt; {action}</span>')
        else:
            telemetry_chips.append('<span class="telemetry-chip">[Guardrail Intervened]</span>')
    else:
        telemetry_chips.append('<span class="telemetry-chip">[Guardrail Verified]</span>')

    if telemetry_chips:
        st.markdown(
            f"""
            <div class="section-header" style="margin-top: 14px;"><span>Pipeline Telemetry</span></div>
            <div>{''.join(telemetry_chips)}</div>
            """,
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------------
# Area 3 — History: Individual Result Inspection in 3-Column Workspace
# ------------------------------------------------------------------

def render_history() -> None:
    """Render historical tickets queue with single-ticket detail workspace."""
    try:
        tickets = get_client().list_tickets(st.session_state["token"])
    except AuthenticationError as exc:
        _handle_auth_error(exc)
        return
    except ApiError as exc:
        st.error(str(exc))
        return

    if not tickets:
        with st.container(border=True):
            st.info("No tickets recorded yet. Submit a ticket in New Decision to view history.")
        return

    def _make_ticket_label(t: dict[str, Any]) -> str:
        tid = t.get("id", "?")
        dec = t.get("decision") or {}
        act = format_action_label(dec.get("action", "—"))
        conf_raw = dec.get("confidence")
        try:
            conf_pct = f"{float(conf_raw) * 100:.0f}%" if conf_raw is not None else "0%"
        except (ValueError, TypeError):
            conf_pct = "0%"
        raw_msg = (t.get("message") or "").replace("\n", " ").strip()
        msg_snip = raw_msg[:60] + ("..." if len(raw_msg) > 60 else "")
        return f"Ticket #{tid} • {act} ({conf_pct}) • {msg_snip}"

    options = {t["id"]: _make_ticket_label(t) for t in tickets}
    ticket_ids = list(options.keys())
    labels = list(options.values())

    col_sel, col_btn = st.columns([3.5, 1])
    with col_sel:
        selected_idx = st.selectbox(
            "Select Ticket from History Queue",
            range(len(ticket_ids)),
            format_func=lambda i: labels[i],
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("Load Ticket", type="primary", use_container_width=True):
            if selected_idx is not None:
                st.session_state["selected_ticket_id"] = ticket_ids[selected_idx]

    current_selected = st.session_state.get("selected_ticket_id")
    if current_selected is None and ticket_ids:
        current_selected = ticket_ids[0]
        st.session_state["selected_ticket_id"] = current_selected

    if current_selected is not None:
        _render_history_ticket_workspace(current_selected)


def _render_history_ticket_workspace(ticket_id: int) -> None:
    """Render historical ticket in full 3-column Dribbble layout matching screenshot."""
    try:
        ticket = get_client().get_ticket(st.session_state["token"], ticket_id)
    except AuthenticationError as exc:
        _handle_auth_error(exc)
        return
    except ApiError as exc:
        st.error(str(exc))
        return

    decision = ticket.get("decision", {})
    action = decision.get("action", "—")
    style = get_action_style(action)
    action_label = html.escape(format_action_label(action))
    issue_display = html.escape(format_issue_type(decision.get("inferred_issue_type")))
    created_at = ticket.get("created_at", "—")
    reviewed_at = decision.get("reviewed_at")
    reviews = ticket.get("reviews") or []
    cust_code = f"USER{int(ticket_id):04d}" if str(ticket_id).isdigit() else f"USER{ticket_id}"

    # Top Breadcrumbs Bar matching screenshot
    st.markdown(
        f"""
        <div class="top-breadcrumbs">
            <div class="breadcrumb-path">
                <span>Settings</span>
                <span>&gt;</span>
                <span>Helpdesk</span>
                <span>&gt;</span>
                <span class="breadcrumb-active">#TIC-{ticket_id}</span>
            </div>
            <div>
                {"<span class='status-pill-resolved'><span class='status-dot dot-green'></span> Resolved / Reviewed</span>" if reviewed_at else "<span class='status-pill-open'><span class='status-dot dot-yellow'></span> Open</span>"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_center, col_right = st.columns([1.0, 1.4, 1.1], gap="medium")

    # ==================================================================
    # COLUMN 1 — Left: Ticket Details & Attachments
    # ==================================================================
    with col_left:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-size: 1.05rem; font-weight: 800; color: #0f172a;">#TIC-{ticket_id}</span>
                    <span class="priority-high">High Priority</span>
                </div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b; margin-bottom: 4px;">
                    Issue with {issue_display}
                </div>
                <div style="font-size: 0.82rem; color: #475569; line-height: 1.4; margin-bottom: 12px;">
                    {html.escape(ticket.get("message", "—")[:120])}...
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Metadata properties matching screenshot
            st.markdown('<div class="section-header"><span>Ticket Metadata</span></div>', unsafe_allow_html=True)
            order_val = format_currency(ticket.get("order_value_inr"))
            deliv_days = f"{ticket['days_since_delivery']} days" if ticket.get("days_since_delivery") is not None else "—"
            disp_days = f"{ticket['days_since_dispatch']} days" if ticket.get("days_since_dispatch") is not None else "—"
            p_type = str(ticket.get("product_type") or "—").capitalize()
            o_opened = str(ticket.get("opened_status") or "—").capitalize()
            o_status = str(ticket.get("order_status") or "—").capitalize()

            st.markdown(
                f"""
                <div class="prop-grid" style="margin-bottom: 12px;">
                    <div class="prop-row">
                        <span class="prop-label">Order Value</span>
                        <span class="prop-value font-mono">{html.escape(order_val)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Order Status</span>
                        <span class="prop-value">{html.escape(o_status)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Product Type</span>
                        <span class="prop-value">{html.escape(p_type)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Opened Status</span>
                        <span class="prop-value">{html.escape(o_opened)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Days Since Delivery</span>
                        <span class="prop-value">{html.escape(deliv_days)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Days Since Dispatch</span>
                        <span class="prop-value">{html.escape(disp_days)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Created At</span>
                        <span class="prop-value">{html.escape(str(created_at)[:19])}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Policy Attachments (6)</span>
                    <span class="header-tag">Grounded KB</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">damaged_goods.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 625 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">returns.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 509 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">cancellations.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 367 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">defective_products.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 502 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">shipping.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 509 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                <div class="attachment-card">
                    <div>
                        <div class="attachment-name">wrong_item.md</div>
                        <div class="attachment-meta">Policy Rules &bull; 455 bytes</div>
                    </div>
                    <span class="header-tag">Indexed</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            st.markdown(
                f"""
                <div class="section-header"><span>Customer Information</span></div>
                <div class="prop-grid">
                    <div class="prop-row">
                        <span class="prop-label">Customer ID</span>
                        <span class="prop-value font-mono">#{cust_code}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Account Tier</span>
                        <span class="prop-value">Enterprise Support</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Temperament</span>
                        <span class="prop-value"><span class="badge-neutral">Calm</span></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ==================================================================
    # COLUMN 2 — Center: Conversation Thread matching screenshot
    # ==================================================================
    with col_center:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="avatar-circle avatar-customer">CU</div>
                        <div>
                            <div style="font-size: 0.9rem; font-weight: 700; color: #0f172a;">Customer #{cust_code}</div>
                            <div style="font-size: 0.74rem; color: #64748b;">Submitted {html.escape(str(created_at)[:19])}</div>
                        </div>
                    </div>
                    <span class="badge-neutral">Calm</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            msg = ticket.get("message", "—")
            safe_msg = html.escape(msg).replace("\n", "<br>")

            st.markdown(
                f"""
                <div class="chat-bubble-customer">
                    {safe_msg}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Facts summary card
            st.markdown(
                f"""
                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px; margin-top: 14px;">
                    <div class="section-header" style="margin-bottom: 6px;">
                        <span>Grounded Evidence Summary</span>
                        <span class="badge-approved">Verified Facts</span>
                    </div>
                    <div style="font-size: 0.82rem; color: #334155; line-height: 1.5;">
                        <strong>Inferred Category:</strong> {issue_display}<br>
                        <strong>Order Value:</strong> {order_val} &bull; <strong>Delivery:</strong> {deliv_days} &bull; <strong>Dispatch:</strong> {disp_days}<br>
                        <strong>Product:</strong> {p_type} &bull; <strong>Package:</strong> {o_opened} &bull; <strong>Status:</strong> {o_status}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # If ticket needs more information, provide follow-up request and re-evaluation form
            hist_analysis = analyze_evidence_needs(ticket.get("message", ""), ticket)
            if action == "NEEDS_MORE_INFORMATION" and hist_analysis["missing"]:
                missing_labels = ", ".join(q["label"] for q in hist_analysis["missing"])
                st.markdown(
                    f"""
                    <div style="background-color: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 12px 14px; margin-top: 14px;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                            <span style="font-size: 0.82rem; font-weight: 800; text-transform: uppercase; color: #92400e;">
                                Action Required: Incomplete Information
                            </span>
                            <span class="badge-warning">{len(hist_analysis['missing'])} Missing Facts</span>
                        </div>
                        <div style="font-size: 0.82rem; color: #78350f; line-height: 1.45;">
                            This ticket cannot receive an automatic approval because policy facts ({html.escape(missing_labels)}) are missing. Ask the customer for clarification, or provide their response below to re-evaluate.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                hist_tab_q, hist_tab_ask = st.tabs(["Provide Customer's Answer & Re-Evaluate", "Ask Customer (Draft Reply)"])

                with hist_tab_ask:
                    st.caption("Copy this message to send to the customer via chat or email:")
                    clarify_text = generate_customer_clarification_message(hist_analysis["issue"], hist_analysis["missing"])
                    st.text_area("Customer Clarification Request", value=clarify_text, height=150, key=f"hist_clarify_{ticket_id}")
                    if st.button("Copy / Use Message as Ready", key=f"hist_btn_copy_{ticket_id}"):
                        st.success("Message ready to send to customer.")

                with hist_tab_q:
                    with st.form(f"hist_resolve_form_{ticket_id}"):
                        st.markdown("**Enter Customer's Clarifying Information:**")
                        updated_inputs: dict[str, Any] = {}
                        for q in hist_analysis["missing"]:
                            st.markdown(f"*{q['question']}*")
                            st.caption(f"Policy Note: {q['policy_note']}")
                            if q["type"] in ("number", "int"):
                                updated_inputs[q["field"]] = st.text_input(
                                    f"Enter {q['label']}",
                                    placeholder=q.get("placeholder", ""),
                                    key=f"h_in_{q['field']}_{ticket_id}",
                                )
                            elif q["type"] == "select":
                                opts = ["— Select —"] + q["options"]
                                updated_inputs[q["field"]] = st.selectbox(
                                    f"Select {q['label']}",
                                    opts,
                                    key=f"h_in_{q['field']}_{ticket_id}",
                                )
                            st.write("")

                        submit_update = st.form_submit_button("Re-Evaluate Ticket with New Information", type="primary", use_container_width=True)

                    if submit_update:
                        merged_facts = {
                            "order_value_inr": ticket.get("order_value_inr"),
                            "days_since_delivery": ticket.get("days_since_delivery"),
                            "days_since_dispatch": ticket.get("days_since_dispatch"),
                            "product_type": ticket.get("product_type"),
                            "opened_status": ticket.get("opened_status"),
                            "order_status": ticket.get("order_status"),
                        }
                        for field, raw_val in updated_inputs.items():
                            if raw_val and raw_val != "— Select —":
                                if field in ("order_value_inr",):
                                    try:
                                        merged_facts[field] = float(str(raw_val).strip())
                                    except ValueError:
                                        pass
                                elif field in ("days_since_delivery", "days_since_dispatch"):
                                    try:
                                        merged_facts[field] = int(str(raw_val).strip())
                                    except ValueError:
                                        pass
                                else:
                                    merged_facts[field] = str(raw_val).strip()

                        with st.spinner("Re-evaluating ticket against company policies..."):
                            try:
                                new_ticket = get_client().create_ticket(
                                    st.session_state["token"],
                                    message=ticket.get("message", ""),
                                    order_value_inr=merged_facts.get("order_value_inr"),
                                    days_since_delivery=merged_facts.get("days_since_delivery"),
                                    days_since_dispatch=merged_facts.get("days_since_dispatch"),
                                    product_type=merged_facts.get("product_type"),
                                    opened_status=merged_facts.get("opened_status"),
                                    order_status=merged_facts.get("order_status"),
                                )
                                st.session_state["selected_ticket_id"] = new_ticket.get("id")
                                st.success("New evidence applied! Re-evaluated ticket resolution generated.")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

    # ==================================================================
    # COLUMN 3 — Right: AI Copilot & HITL Review Panel
    # ==================================================================
    with col_right:
        with st.container(border=True):
            st.markdown(
                """
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="avatar-circle avatar-copilot">AI</div>
                        <div style="font-size: 0.95rem; font-weight: 800; color: #0f172a;">AI Copilot</div>
                    </div>
                    <span class="header-tag">Grounded</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            _render_copilot_decision_card(ticket)

            # Agent Review & Override Panel
            st.divider()
            st.markdown('<div class="section-header"><span>Agent Review &amp; Override (HITL)</span></div>', unsafe_allow_html=True)

            if reviewed_at:
                override_act = decision.get("human_override_action") or "Accepted"
                override_reason = decision.get("human_override_reason") or "Verified compliant."
                st.markdown(
                    f"""
                    <div style="background-color: #f0fdf4; padding: 10px 12px; border-radius: 6px; border: 1px solid #bbf7d0; margin-bottom: 12px;">
                        <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: #166534; margin-bottom: 2px;">
                            Active Resolution
                        </div>
                        <div style="font-size: 0.88rem; font-weight: 700; color: #166534;">
                            {html.escape(format_action_label(override_act))}
                        </div>
                        <div style="font-size: 0.78rem; color: #334155; margin-top: 2px;">
                            Note: {html.escape(override_reason)}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            col_acc, col_ovr = st.columns([1, 1.2])
            with col_acc:
                if st.button("Accept AI Decision", type="primary", use_container_width=True, key=f"hist_accept_{ticket_id}"):
                    try:
                        get_client().review_ticket(st.session_state["token"], ticket_id, accept=True)
                        st.success("Decision verified and accepted!")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            with col_ovr:
                action_options = [
                    "APPROVE_REFUND_OR_REPLACEMENT",
                    "APPROVE_REPLACEMENT",
                    "APPROVE_RETURN",
                    "CANCEL_AND_REFUND",
                    "CANNOT_CANCEL_AFTER_DISPATCH",
                    "NEEDS_MORE_INFORMATION",
                    "OFFER_REPLACEMENT_OR_REFUND",
                    "OPEN_SHIPPING_INVESTIGATION",
                    "REJECT_FOOD_RETURN",
                    "REJECT_OPENED_ITEM",
                    "REJECT_OUTSIDE_WINDOW",
                    "REPLACE_CORRECT_ITEM",
                    "REQUEST_DEFECT_EVIDENCE",
                    "REQUEST_PHOTOS",
                    "WAIT_AND_TRACK",
                ]
                override_action = st.selectbox("Override Action", action_options, key=f"hist_ovr_act_{ticket_id}")

            override_reason = st.text_input(
                "Override Audit Reason *",
                placeholder="e.g. Approved exception for VIP customer",
                key=f"hist_ovr_rsn_{ticket_id}",
            )
            if st.button("Submit Override", type="secondary", use_container_width=True, key=f"hist_btn_ovr_{ticket_id}"):
                if not override_reason or not override_reason.strip():
                    st.warning("Please provide a reason for overriding.")
                else:
                    try:
                        get_client().review_ticket(
                            st.session_state["token"],
                            ticket_id,
                            action=override_action,
                            reason=override_reason.strip(),
                            accept=False,
                        )
                        st.success("Override recorded in audit log!")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            # Review Audit Trail
            if reviews:
                st.markdown('<div class="section-header" style="margin-top: 14px;"><span>Review Audit Trail</span></div>', unsafe_allow_html=True)
                for rev in reviews:
                    st.markdown(
                        f"""
                        <div class="audit-trail-item">
                            <div class="audit-agent-tag">
                                Agent ID #{rev.get('reviewer_id')} &bull; {html.escape(str(rev.get('created_at', ''))[:19])}
                            </div>
                            <div class="audit-action-title">
                                Action: {html.escape(format_action_label(rev.get('action', '')))}
                            </div>
                            <div class="audit-note-text">
                                Note: {html.escape(rev.get('reason', ''))}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


# ------------------------------------------------------------------
# Main layout & Top Navigation Bar
# ------------------------------------------------------------------

def main() -> None:
    if not is_authenticated():
        render_auth()
        return

    _inject_custom_css()

    user = st.session_state.get("user", {})
    user_email = user.get("email", "support@company.com")

    # Enterprise Top Navigation Bar matching screenshot
    col_hdr, col_auth = st.columns([3, 1])
    with col_hdr:
        st.markdown(
            """
            <div style="margin-bottom: 2px;">
                <span style="font-size: 1.25rem; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">
                    AI Support Decision Assistant
                </span>
                <span class="badge-approved" style="margin-left: 8px;">Enterprise Helpdesk</span>
            </div>
            <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 6px;">
                Interactive Evidence Gathering &bull; Local Policy Grounding &bull; Human-in-the-Loop Audit Trail
            </div>
            <div>
                <span class="header-tag">6 Policy Documents</span>
                <span class="header-tag">Zero Label Leakage</span>
                <span class="header-tag">Private Workspace</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_auth:
        st.write("")
        st.markdown(
            f"""
            <div style="text-align: right; margin-bottom: 6px;">
                <span style="font-size: 0.82rem; color: #475569; font-weight: 600;">Agent: {html.escape(user_email)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Sign Out / Log Out", type="secondary", use_container_width=True):
            _clear_session()
            st.rerun()

    st.divider()

    # Workspace Navigation Tabs: New Decision vs Ticket History
    nav = st.segmented_control(
        "Workspace Navigation",
        ["New Decision", "History"],
        default="New Decision" if not st.session_state.get("selected_ticket_id") else "History",
        label_visibility="collapsed",
    )

    if nav == "New Decision" or nav is None:
        render_new_decision()
    else:
        render_history()


if __name__ == "__main__":
    main()
