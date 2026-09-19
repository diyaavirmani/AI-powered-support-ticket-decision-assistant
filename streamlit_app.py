"""Streamlit presentation layer: AI Support Decision Assistant Workbench.

SaaS Customer Support Ticket Detail Workspace modeled after Dribbble design
by Omeiza Patrick Adanini (shot 25672248).

Communicates with FastAPI exclusively through HTTP via ApiClient.
Never accesses SQLite, SQLAlchemy, embeddings, or Gemini directly.
Strict zero-emoji design system throughout all views.
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

        /* Modern card surfaces and subtle elevations */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background-color: #ffffff;
            border-radius: 12px !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04);
            padding: 16px 18px !important;
        }

        /* Top header navbar styling */
        .top-navbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 0 12px 0;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 16px;
        }
        .nav-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.02em;
        }
        .nav-subtitle {
            font-size: 0.8rem;
            color: #64748b;
            margin-top: 2px;
        }

        /* Section headers inside cards */
        .section-header {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #64748b;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Status & Capability Badges */
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
            gap: 2px;
        }
        .prop-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f1f5f9;
            font-size: 0.84rem;
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

        /* Customer avatar & profile */
        .user-card {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        .avatar-circle {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.88rem;
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
        .user-info-name {
            font-size: 0.92rem;
            font-weight: 700;
            color: #0f172a;
        }
        .user-info-meta {
            font-size: 0.78rem;
            color: #64748b;
        }

        /* Customer message bubble */
        .inquiry-bubble {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 3px solid #6366f1;
            border-radius: 4px 10px 10px 4px;
            padding: 14px 16px;
            color: #1e293b;
            font-size: 0.9rem;
            line-height: 1.5;
            margin-bottom: 16px;
        }

        /* AI Copilot Decision Hero Banner */
        .decision-banner {
            padding: 16px 18px;
            border-radius: 10px;
            margin: 10px 0 16px 0;
        }
        .decision-banner-header {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 4px;
        }
        .decision-banner-title {
            font-size: 1.25rem;
            font-weight: 800;
            line-height: 1.3;
        }

        /* Policy source chip */
        .source-chip {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            background-color: #f1f5f9;
            color: #1e293b;
            border: 1px solid #cbd5e1;
            margin: 3px 6px 3px 0;
        }

        /* Rationale callout */
        .rationale-card {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 3px solid #94a3b8;
            border-radius: 4px 8px 8px 4px;
            padding: 12px 14px;
            font-size: 0.86rem;
            color: #334155;
            line-height: 1.45;
            margin-bottom: 14px;
        }

        /* Telemetry micro card */
        .telemetry-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 12px;
        }
        .telemetry-chip {
            padding: 6px 10px;
            border-radius: 6px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            font-size: 0.78rem;
            color: #475569;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        /* Audit trail timeline */
        .audit-trail-item {
            position: relative;
            padding: 10px 12px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .audit-agent-tag {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #64748b;
        }
        .audit-action-title {
            font-size: 0.86rem;
            font-weight: 700;
            color: #0f172a;
            margin-top: 2px;
        }
        .audit-note-text {
            font-size: 0.8rem;
            color: #475569;
            margin-top: 3px;
        }

        /* Preview step cards */
        .preview-step {
            padding: 12px 14px;
            border-radius: 8px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            margin-bottom: 10px;
        }

        /* Trust note on auth screen */
        .trust-note {
            font-size: 0.78rem;
            color: #64748b;
            text-align: center;
            margin-top: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------
# Session helpers
# ------------------------------------------------------------------

def _clear_session() -> None:
    for key in ["token", "user", "selected_ticket_id", "last_decision"]:
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

            tab_login, tab_register, tab_forgot = st.tabs([
                "Sign In / Log In",
                "Sign Up / Create Account",
                "Forgot Password",
            ])

            with tab_login:
                with st.form("login_form", clear_on_submit=True):
                    login_email = st.text_input("Work Email", key="login_email", placeholder="agent@company.com")
                    login_password = st.text_input("Password", type="password", key="login_password")
                    submitted_login = st.form_submit_button("Sign In / Log In", type="primary", use_container_width=True)

                if submitted_login:
                    if not login_email or not login_password:
                        st.warning("Please provide both email and password.")
                    else:
                        try:
                            client = get_client()
                            token = client.login(login_email, login_password)
                            user = client.get_current_user(token)
                            st.session_state["token"] = token
                            st.session_state["user"] = user
                            st.rerun()
                        except ApiError as exc:
                            st.error(str(exc))

            with tab_register:
                with st.form("register_form", clear_on_submit=True):
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
                            get_client().register(reg_email, reg_password)
                            st.success("Account created successfully. Please switch to the Sign In / Log In tab.")
                        except ApiError as exc:
                            st.error(str(exc))

            with tab_forgot:
                with st.form("forgot_password_form", clear_on_submit=True):
                    forgot_email = st.text_input("Registered Work Email", key="forgot_email", placeholder="agent@company.com")
                    new_password = st.text_input(
                        "New Password (min 12 characters)",
                        type="password",
                        key="forgot_new_password",
                        help="Must be at least 12 characters.",
                    )
                    submitted_forgot = st.form_submit_button("Reset Password", type="primary", use_container_width=True)

                if submitted_forgot:
                    if not forgot_email or not new_password:
                        st.warning("Please provide both email and new password.")
                    elif len(new_password) < 12:
                        st.warning("New password must be at least 12 characters.")
                    else:
                        try:
                            get_client().reset_password(forgot_email.strip(), new_password)
                            st.success("Password reset successfully! You can now switch to the Sign In / Log In tab to log in.")
                        except ApiError as exc:
                            st.error(str(exc))

            st.markdown(
                '<div class="trust-note">Argon2 Password Hashing • JWT Authentication • Multi-Tenant Isolation</div>',
                unsafe_allow_html=True,
            )


# ------------------------------------------------------------------
# Area 2 — New Ticket Intake & Decision Generation
# ------------------------------------------------------------------

def render_new_decision() -> None:
    col_input, col_decision = st.columns([1, 1], gap="large")

    with col_input:
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>New Ticket Intake</span>
                    <span class="header-tag">Grounded RAG Pipeline</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption("Enter the customer message and structured order attributes. The decision engine infers the issue type and retrieves grounded policy rules.")

            with st.form("ticket_form"):
                message = st.text_area(
                    "Customer Message *",
                    height=130,
                    placeholder="Provide the customer issue or request (e.g. 'I received my package yesterday but the ceramic mug was shattered into pieces...').",
                )

                with st.expander("Structured Order Facts (Optional)", expanded=True):
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        order_value_str = st.text_input(
                            "Order Value (INR)",
                            placeholder="e.g. 3500",
                            help="Leave blank if unknown.",
                        )
                        delivery_str = st.text_input(
                            "Days Since Delivery",
                            placeholder="e.g. 3",
                            help="Leave blank if unknown or not yet delivered.",
                        )
                        product_options = ["— Not specified —", "food", "non_food", "mixed", "unknown"]
                        product_type = st.selectbox("Product Type", product_options)
                    with col_f2:
                        order_options = ["— Not specified —", "processing", "dispatched", "delivered", "unknown"]
                        order_status = st.selectbox("Order Status", order_options)
                        dispatch_str = st.text_input(
                            "Days Since Dispatch",
                            placeholder="e.g. 9",
                            help="Leave blank if unknown.",
                        )
                        opened_options = ["— Not specified —", "opened", "unopened", "unknown"]
                        opened_status = st.selectbox("Opened Status", opened_options)

                submitted = st.form_submit_button("Generate Grounded Decision", type="primary", use_container_width=True)

            if submitted:
                if not message or not message.strip():
                    st.warning("Please enter a customer message.")
                    return

                order_value = None
                if order_value_str and order_value_str.strip():
                    try:
                        order_value = float(order_value_str.strip())
                        if order_value < 0:
                            st.warning("Order value cannot be negative.")
                            return
                    except ValueError:
                        st.warning("Order value must be a valid number.")
                        return

                days_delivery = None
                if delivery_str and delivery_str.strip():
                    try:
                        days_delivery = int(delivery_str.strip())
                        if days_delivery < 0:
                            st.warning("Days since delivery cannot be negative.")
                            return
                    except ValueError:
                        st.warning("Days since delivery must be a whole number.")
                        return

                days_dispatch = None
                if dispatch_str and dispatch_str.strip():
                    try:
                        days_dispatch = int(dispatch_str.strip())
                        if days_dispatch < 0:
                            st.warning("Days since dispatch cannot be negative.")
                            return
                    except ValueError:
                        st.warning("Days since dispatch must be a whole number.")
                        return

                pt = product_type if product_type != "— Not specified —" else None
                os_val = opened_status if opened_status != "— Not specified —" else None
                ost = order_status if order_status != "— Not specified —" else None

                with st.spinner("Classifying issue, retrieving policy rules, and applying guardrails..."):
                    try:
                        result = get_client().create_ticket(
                            st.session_state["token"],
                            message=message.strip(),
                            order_value_inr=order_value,
                            days_since_delivery=days_delivery,
                            days_since_dispatch=days_dispatch,
                            product_type=pt,
                            opened_status=os_val,
                            order_status=ost,
                        )
                        st.session_state["last_decision"] = result
                        st.session_state["selected_ticket_id"] = result.get("id")
                    except AuthenticationError as exc:
                        _handle_auth_error(exc)
                        return
                    except ApiError as exc:
                        st.error(str(exc))
                        return

    with col_decision:
        decision_data = st.session_state.get("last_decision")
        if decision_data:
            _render_decision_result(decision_data)
        else:
            _render_empty_decision_state()


def _render_empty_decision_state() -> None:
    """Render an intentional empty state before a ticket has been submitted."""
    with st.container(border=True):
        st.markdown(
            """
            <div class="section-header">
                <span>AI Decision Engine</span>
                <span class="badge-neutral">Ready</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Submit a ticket on the left to evaluate applicable company policies and receive an evidence-grounded recommendation.")

        st.markdown(
            """
            <div class="preview-step">
                <div style="font-weight: 700; font-size: 0.88rem; color: #1e293b; margin-bottom: 2px;">
                    1. Issue Type Classification
                </div>
                <div style="font-size: 0.82rem; color: #64748b;">
                    Analyzes customer message semantics without caller bias to determine the primary category (e.g. damaged goods, return request, cancellation).
                </div>
            </div>
            <div class="preview-step">
                <div style="font-weight: 700; font-size: 0.88rem; color: #1e293b; margin-bottom: 2px;">
                    2. Policy-Only RAG Retrieval
                </div>
                <div style="font-size: 0.82rem; color: #64748b;">
                    Retrieves relevant clauses exclusively from the 6 trusted Markdown policy documents using rule-aware chunking and vector embeddings.
                </div>
            </div>
            <div class="preview-step">
                <div style="font-weight: 700; font-size: 0.88rem; color: #1e293b; margin-bottom: 2px;">
                    3. Deterministic Guardrail Validation
                </div>
                <div style="font-size: 0.82rem; color: #64748b;">
                    Enforces strict boundary constraints (e.g. 7-day damage limits, photo evidence over ₹2,000, dispatched cancellation blocks) before finalizing.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_decision_result(ticket: dict[str, Any]) -> None:
    """Render a structured AI decision result card for the intake view."""
    decision = ticket.get("decision", {})
    action = decision.get("action", "—")
    style = get_action_style(action)
    action_label = html.escape(format_action_label(action))
    category = html.escape(style["category"])
    issue_display = html.escape(format_issue_type(decision.get("inferred_issue_type")))
    ticket_id = ticket.get("id", "—")

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div class="avatar-circle avatar-copilot">AI</div>
                    <div>
                        <div style="font-size: 0.95rem; font-weight: 800; color: #0f172a;">Ticket #{ticket_id} Decision</div>
                        <div style="font-size: 0.78rem; color: #64748b;">Grounded Copilot Recommendation</div>
                    </div>
                </div>
                <div>
                    <span class="header-tag">Issue: {issue_display}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Action Hero Banner
        banner_html = f"""
        <div class="decision-banner" style="background-color: {style['bg']}; border: 1.5px solid {style['border']};">
            <div class="decision-banner-header" style="color: {style['text']};">
                Recommended Action • {category}
            </div>
            <div class="decision-banner-title" style="color: {style['text']};">
                {action_label}
            </div>
        </div>
        """
        st.markdown(banner_html, unsafe_allow_html=True)

        # Confidence metric and progress indicator
        confidence = decision.get("confidence")
        conf_val = float(confidence) if confidence is not None else 0.0
        conf_display = f"{conf_val * 100:.0f}%"

        col_m1, col_m2 = st.columns([1, 2.5])
        with col_m1:
            st.metric("Confidence", conf_display)
        with col_m2:
            st.write("")
            st.caption("Model calibration score")
            st.progress(max(0.0, min(1.0, conf_val)))

        # Policy rationale
        reason = decision.get("reason", "")
        st.markdown(
            """
            <div class="section-header" style="margin-top: 14px;">
                <span>Policy Rationale</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if reason:
            st.markdown(
                f'<div class="rationale-card">{html.escape(reason)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("No rationale recorded.")

        # Source citations
        sources = decision.get("sources", [])
        st.markdown(
            """
            <div class="section-header">
                <span>Cited Policy Documents</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if sources:
            chips = "".join(f'<span class="source-chip">{html.escape(s)}</span>' for s in sources)
            st.markdown(f'<div style="margin-bottom: 14px;">{chips}</div>', unsafe_allow_html=True)
        else:
            st.caption("No policy sources cited.")

        # Pipeline Telemetry & Guardrails
        retrieval_ms = decision.get("retrieval_latency_ms")
        llm_ms = decision.get("llm_latency_ms")
        guarded = decision.get("guardrail_triggered")
        raw_act = decision.get("raw_action")
        confidence = decision.get("confidence", 0.0)
        is_fallback = confidence == 0.0 or "[System Fallback" in str(decision.get("reason", ""))

        telemetry_items: list[str] = []
        if retrieval_ms is not None:
            telemetry_items.append(f"Retrieval: {retrieval_ms:.1f}ms")
        if llm_ms is not None:
            telemetry_items.append(f"LLM: {llm_ms:.1f}ms")
        if is_fallback:
            telemetry_items.append("[Fallback Escalation]")
        elif guarded:
            if raw_act:
                telemetry_items.append(f"[Guardrail: {raw_act} -> {decision.get('action')}]")
            else:
                telemetry_items.append("[Guardrail Intervened]")
        elif retrieval_ms is not None or llm_ms is not None:
            telemetry_items.append("[Guardrail Verified]")

        if telemetry_items:
            chips_html = "".join(f'<span class="telemetry-chip">{html.escape(item)}</span>' for item in telemetry_items)
            st.markdown(
                f"""
                <div class="section-header" style="margin-top: 10px;">
                    <span>Pipeline Telemetry</span>
                </div>
                <div class="telemetry-row">{chips_html}</div>
                """,
                unsafe_allow_html=True,
            )


# ------------------------------------------------------------------
# Area 3 — Dribbble-Inspired Ticket Detail Workspace
# ------------------------------------------------------------------

def render_history() -> None:
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
            st.info("No tickets recorded yet. Create a ticket in New Ticket Intake to view history.")
        return

    options = {
        t["id"]: (
            f"Ticket #{t['id']} • {format_action_label(t.get('decision', {}).get('action', '—'))} "
            f"({(t.get('decision', {}).get('confidence', 0) * 100):.0f}%) • "
            f"{t.get('message', '')[:65]}..."
        )
        for t in tickets
    }
    ticket_ids = list(options.keys())
    labels = list(options.values())

    # Ticket queue selector bar
    col_sel, col_btn = st.columns([3.5, 1])
    with col_sel:
        selected_idx = st.selectbox(
            "Select Ticket from Queue",
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
        _render_ticket_detail_workspace(current_selected)


def _render_ticket_detail_workspace(ticket_id: int) -> None:
    """Render the full 3-column ticket detail workspace matching Omeiza Patrick Adanini's Dribbble design."""
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

    # ------------------------------------------------------------------
    # Top Ticket Breadcrumbs & Status Bar
    # ------------------------------------------------------------------
    status_badge_html = (
        '<span class="badge-approved">[Reviewed]</span>'
        if reviewed_at
        else '<span class="badge-warning">[Pending Review]</span>'
    )

    st.markdown(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 12px 16px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 0.84rem; color: #64748b; font-weight: 600;">Tickets /</span>
                <span style="font-size: 1.1rem; font-weight: 800; color: #0f172a;">Ticket #{ticket_id}</span>
                {status_badge_html}
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="header-tag">Category: {issue_display}</span>
                <span class="header-tag">Created: {html.escape(str(created_at)[:19])}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # 3-Column SaaS Split Layout
    # Column 1: Context & Metadata (Customer, Order Facts, Policy Engine)
    # Column 2: Conversational Inquiry & Grounded AI Decision
    # Column 3: Telemetry & Human-In-The-Loop Review
    # ------------------------------------------------------------------
    col_context, col_center, col_review = st.columns([1.0, 1.4, 1.1], gap="medium")

    # ==================================================================
    # COLUMN 1 — Customer & Order Context
    # ==================================================================
    with col_context:
        # Customer Profile Card
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Customer Profile</span>
                    <span class="badge-neutral">Verified</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div class="user-card">
                    <div class="avatar-circle avatar-customer">CU</div>
                    <div>
                        <div class="user-info-name">Support Requester</div>
                        <div class="user-info-meta">Account ID: CUST-{ticket_id:04d}</div>
                    </div>
                </div>
                <div class="prop-grid">
                    <div class="prop-row">
                        <span class="prop-label">Account Tier</span>
                        <span class="prop-value">Enterprise SLA</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Support Channel</span>
                        <span class="prop-value">Web Portal</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Ticket ID</span>
                        <span class="prop-value font-mono">#{ticket_id}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Order Details Card
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Order Context</span>
                    <span class="header-tag">Facts</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            order_val = f"₹{ticket['order_value_inr']:.2f}" if ticket.get("order_value_inr") is not None else "—"
            deliv_days = f"{ticket['days_since_delivery']} days" if ticket.get("days_since_delivery") is not None else "—"
            dispatch_days = f"{ticket['days_since_dispatch']} days" if ticket.get("days_since_dispatch") is not None else "—"
            p_type = ticket.get("product_type") or "—"
            o_opened = ticket.get("opened_status") or "—"
            o_status = ticket.get("order_status") or "—"

            st.markdown(
                f"""
                <div class="prop-grid">
                    <div class="prop-row">
                        <span class="prop-label">Order Value</span>
                        <span class="prop-value">{html.escape(order_val)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Order Status</span>
                        <span class="prop-value">{html.escape(o_status.capitalize())}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Product Type</span>
                        <span class="prop-value">{html.escape(p_type.capitalize())}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Opened Status</span>
                        <span class="prop-value">{html.escape(o_opened.capitalize())}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Days Since Delivery</span>
                        <span class="prop-value">{html.escape(deliv_days)}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Days Since Dispatch</span>
                        <span class="prop-value">{html.escape(dispatch_days)}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Policy Grounding Status Card
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Grounding Guardrails</span>
                    <span class="badge-approved">Active</span>
                </div>
                <div class="prop-grid">
                    <div class="prop-row">
                        <span class="prop-label">Knowledge Base</span>
                        <span class="prop-value">6 Markdown Policies</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Historical Tickets</span>
                        <span class="prop-value">Excluded (No Leakage)</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Enforcement</span>
                        <span class="prop-value">Deterministic Fail-Closed</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ==================================================================
    # COLUMN 2 — Conversation Thread & AI Grounded Resolution
    # ==================================================================
    with col_center:
        # Customer Message Thread Card
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Customer Inquiry</span>
                    <span class="header-tag">Inbound</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            msg = ticket.get("message", "—")
            safe_msg = html.escape(msg).replace("\n", "<br>")

            st.markdown(
                f"""
                <div class="user-card" style="margin-bottom: 8px;">
                    <div class="avatar-circle avatar-customer" style="width: 32px; height: 32px; font-size: 0.78rem;">CU</div>
                    <div>
                        <div style="font-size: 0.86rem; font-weight: 700; color: #0f172a;">Customer</div>
                        <div style="font-size: 0.74rem; color: #64748b;">Submitted {html.escape(str(created_at)[:19])}</div>
                    </div>
                </div>
                <div class="inquiry-bubble">
                    {safe_msg}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # AI Grounded Decision Card
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="avatar-circle avatar-copilot" style="width: 32px; height: 32px; font-size: 0.78rem;">AI</div>
                        <div>
                            <div style="font-size: 0.92rem; font-weight: 800; color: #0f172a;">AI Copilot Recommendation</div>
                            <div style="font-size: 0.75rem; color: #64748b;">Grounding Verified Against Company Policy</div>
                        </div>
                    </div>
                    <div>
                        <span class="header-tag">{issue_display}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Recommended Action Banner
            banner_html = f"""
            <div class="decision-banner" style="background-color: {style['bg']}; border: 1.5px solid {style['border']};">
                <div class="decision-banner-header" style="color: {style['text']};">
                    Recommended Action • {style['category']}
                </div>
                <div class="decision-banner-title" style="color: {style['text']};">
                    {action_label}
                </div>
            </div>
            """
            st.markdown(banner_html, unsafe_allow_html=True)

            # Confidence Metric & Linear Progress Indicator
            confidence = decision.get("confidence")
            conf_val = float(confidence) if confidence is not None else 0.0
            col_m1, col_m2 = st.columns([1, 2.2])
            with col_m1:
                st.metric("Confidence", f"{conf_val * 100:.0f}%")
            with col_m2:
                st.write("")
                st.caption("Model calibration score")
                st.progress(max(0.0, min(1.0, conf_val)))

            # Policy Rationale
            st.markdown(
                """
                <div class="section-header" style="margin-top: 14px;">
                    <span>Policy Rationale</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            reason = decision.get("reason", "")
            if reason:
                st.markdown(
                    f'<div class="rationale-card">{html.escape(reason)}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No rationale recorded.")

            # Cited Policy Documents
            st.markdown(
                """
                <div class="section-header">
                    <span>Cited Policy Documents</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            sources = decision.get("sources", [])
            if sources:
                chips = "".join(f'<span class="source-chip">{html.escape(s)}</span>' for s in sources)
                st.markdown(f'<div style="margin-bottom: 6px;">{chips}</div>', unsafe_allow_html=True)
            else:
                st.caption("No sources cited.")

    # ==================================================================
    # COLUMN 3 — Pipeline Telemetry & HITL Review Panel
    # ==================================================================
    with col_review:
        # Pipeline Telemetry Card
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Pipeline Telemetry</span>
                    <span class="header-tag">Observability</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            retrieval_ms = decision.get("retrieval_latency_ms")
            llm_ms = decision.get("llm_latency_ms")
            guarded = decision.get("guardrail_triggered")
            raw_act = decision.get("raw_action")
            confidence = decision.get("confidence", 0.0)
            is_fallback = confidence == 0.0 or "[System Fallback" in str(decision.get("reason", ""))

            st.markdown(
                f"""
                <div class="prop-grid">
                    <div class="prop-row">
                        <span class="prop-label">Policy Retrieval</span>
                        <span class="prop-value">{f"{retrieval_ms:.1f} ms" if retrieval_ms is not None else "—"}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">LLM Generation</span>
                        <span class="prop-value">{f"{llm_ms:.1f} ms" if llm_ms is not None else "—"}</span>
                    </div>
                    <div class="prop-row">
                        <span class="prop-label">Guardrail State</span>
                        <span class="prop-value">
                            {"[Intervened]" if guarded else ("[Fallback]" if is_fallback else "[Verified Compliant]")}
                        </span>
                    </div>
                    {f'<div class="prop-row"><span class="prop-label">Raw Model Action</span><span class="prop-value font-mono">{html.escape(str(raw_act))}</span></div>' if raw_act else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Agent Review & Override (HITL) Panel
        with st.container(border=True):
            st.markdown(
                """
                <div class="section-header">
                    <span>Agent Review & Override</span>
                    <span class="badge-neutral">HITL</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Current Effective Resolution Status
            if reviewed_at:
                override_act = decision.get("human_override_action") or "Accepted"
                override_reason = decision.get("human_override_reason") or "Verified compliant."
                st.markdown(
                    f"""
                    <div style="background-color: #f0fdf4; padding: 12px 14px; border-radius: 8px; border: 1px solid #bbf7d0; margin-bottom: 14px;">
                        <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: #166534; margin-bottom: 2px;">
                            Active Resolution
                        </div>
                        <div style="font-size: 0.92rem; font-weight: 800; color: #166534;">
                            {html.escape(format_action_label(override_act))}
                        </div>
                        <div style="font-size: 0.8rem; color: #334155; margin-top: 4px;">
                            <strong>Audit Note:</strong> {html.escape(override_reason)}
                        </div>
                        <div style="font-size: 0.72rem; color: #64748b; margin-top: 4px;">
                            Recorded: {html.escape(str(reviewed_at)[:19])}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Review actions
            col_acc, col_ovr = st.columns([1, 1.2])
            with col_acc:
                if st.button("Accept AI Decision", type="primary", use_container_width=True, key=f"accept_{ticket_id}"):
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
                override_action = st.selectbox("Override Action", action_options, key=f"override_act_{ticket_id}")

            override_reason = st.text_input(
                "Override Audit Reason *",
                placeholder="e.g. Granted exception for valued customer",
                key=f"override_rsn_{ticket_id}",
            )
            if st.button("Submit Override", type="secondary", use_container_width=True, key=f"btn_override_{ticket_id}"):
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

        # Review Audit Trail (Multi-review history)
        if reviews:
            with st.container(border=True):
                st.markdown(
                    """
                    <div class="section-header">
                        <span>Review Audit Trail</span>
                        <span class="badge-neutral">History</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                for rev in reviews:
                    st.markdown(
                        f"""
                        <div class="audit-trail-item">
                            <div class="audit-agent-tag">
                                Agent ID #{rev.get('reviewer_id')} • {html.escape(str(rev.get('created_at', ''))[:19])}
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

    # Enterprise Top Navigation Bar
    col_hdr, col_auth = st.columns([3, 1])
    with col_hdr:
        st.markdown(
            """
            <div style="margin-bottom: 2px;">
                <span class="nav-title">AI Support Decision Assistant</span>
                <span class="badge-approved" style="margin-left: 8px;">Enterprise Helpdesk</span>
            </div>
            <div class="nav-subtitle">
                Local Policy Grounding • Deterministic Guardrails • Human-in-the-Loop Audit Trail
            </div>
            <div style="margin-top: 6px;">
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

    # Workspace Navigation Tabs
    nav = st.segmented_control(
        "Workspace Navigation",
        ["New Ticket Intake", "Ticket Detail Workspace"],
        default="Ticket Detail Workspace" if st.session_state.get("selected_ticket_id") else "New Ticket Intake",
        label_visibility="collapsed",
    )

    if nav == "New Ticket Intake":
        render_new_decision()
    else:
        render_history()


if __name__ == "__main__":
    main()
