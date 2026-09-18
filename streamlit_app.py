"""Streamlit presentation layer: AI Support Decision Assistant Workbench.

Communicates with FastAPI exclusively through HTTP via ApiClient.
Never accesses SQLite, SQLAlchemy, embeddings, or Gemini directly.
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
            "category": "Ineligible",
        }
    return {
        "bg": "#f8fafc",
        "border": "#e2e8f0",
        "text": "#334155",
        "icon": "",
        "category": "Decision",
    }


def _inject_custom_css() -> None:
    """Inject a restrained light-theme design system using the system font stack."""
    st.markdown(
        """
        <style>
        /* Base page tone */
        .stApp {
            background-color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #0f172a;
        }

        /* Card surfaces and rounded borders */
        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background-color: #ffffff;
            border-radius: 12px !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04);
        }

        /* Header capability tags */
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

        /* Policy source chip */
        .source-chip {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 500;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            background-color: #f8fafc;
            color: #1e293b;
            border: 1px solid #cbd5e1;
            margin: 3px 6px 3px 0;
        }

        /* Fact tag */
        .fact-badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            background-color: #f8fafc;
            color: #334155;
            border: 1px solid #e2e8f0;
            margin: 3px 6px 3px 0;
        }

        /* Step cards in empty decision preview */
        .preview-step {
            padding: 12px 14px;
            border-radius: 8px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            margin-bottom: 10px;
        }

        /* Trust note on auth screen */
        .trust-note {
            font-size: 0.8rem;
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

    st.write("")  # Spacing
    st.write("")

    _, col_card, _ = st.columns([1, 1.4, 1])
    with col_card:
        with st.container(border=True):
            st.markdown(
                """
                <div style="text-align: center; margin-top: 6px; margin-bottom: 12px;">
                    <h2 style="margin: 0; font-size: 1.45rem; font-weight: 700; color: #0f172a;">AI Support Decision Assistant</h2>
                    <p style="margin: 6px 0 0 0; font-size: 0.88rem; color: #64748b;">Policy-grounded recommendations for support teams</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

            with tab_login:
                with st.form("login_form", clear_on_submit=True):
                    login_email = st.text_input("Work Email", key="login_email", placeholder="agent@company.com")
                    login_password = st.text_input("Password", type="password", key="login_password")
                    submitted_login = st.form_submit_button("Sign In", type="primary", use_container_width=True)

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
                    submitted_reg = st.form_submit_button("Create Account", use_container_width=True)

                if submitted_reg:
                    if not reg_email or not reg_password:
                        st.warning("Please provide both email and password.")
                    elif len(reg_password) < 12:
                        st.warning("Password must be at least 12 characters.")
                    else:
                        try:
                            get_client().register(reg_email, reg_password)
                            st.success("Account created successfully. Please switch to the Sign In tab.")
                        except ApiError as exc:
                            st.error(str(exc))

            st.markdown(
                '<div class="trust-note">Secure JWT authentication • Private ticket history</div>',
                unsafe_allow_html=True,
            )


# ------------------------------------------------------------------
# Area 2 — New Decision Workbench
# ------------------------------------------------------------------

def render_new_decision() -> None:
    col_input, col_decision = st.columns([1, 1], gap="large")

    with col_input:
        with st.container(border=True):
            st.markdown("### New Support Ticket")
            st.caption("Provide the customer inquiry and any known order facts to generate a policy-grounded recommendation.")

            with st.form("ticket_form"):
                message = st.text_area(
                    "Customer message *",
                    height=130,
                    placeholder="Describe the customer problem or request (e.g. 'My item arrived with broken glass...').",
                )

                with st.expander("Additional order details (optional facts)", expanded=True):
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        order_value_str = st.text_input(
                            "Order value (INR)",
                            placeholder="e.g. 3500",
                            help="Leave blank if unknown.",
                        )
                        delivery_str = st.text_input(
                            "Days since delivery",
                            placeholder="e.g. 3",
                            help="Leave blank if unknown or not yet delivered.",
                        )
                        product_options = ["— Not specified —", "food", "non_food", "mixed", "unknown"]
                        product_type = st.selectbox("Product type", product_options)
                    with col_f2:
                        order_options = ["— Not specified —", "processing", "dispatched", "delivered", "unknown"]
                        order_status = st.selectbox("Order status", order_options)
                        dispatch_str = st.text_input(
                            "Days since dispatch",
                            placeholder="e.g. 9",
                            help="Leave blank if unknown.",
                        )
                        opened_options = ["— Not specified —", "opened", "unopened", "unknown"]
                        opened_status = st.selectbox("Opened status", opened_options)

                submitted = st.form_submit_button("Generate AI Decision", type="primary", use_container_width=True)

            if submitted:
                if not message or not message.strip():
                    st.warning("Please enter a customer message.")
                    return

                # Parse nullable numeric fields cleanly
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

                with st.spinner("Retrieving relevant policy documents and generating decision..."):
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
        st.markdown("### Decision Preview")
        st.caption("Submit a ticket on the left to evaluate applicable company policies and receive an evidence-grounded recommendation.")

        st.markdown(
            """
            <div class="preview-step">
                <div style="font-weight: 600; font-size: 0.9rem; color: #1e293b; margin-bottom: 2px;">1. Infer Issue Type</div>
                <div style="font-size: 0.82rem; color: #64748b;">Classifies the request category (e.g. damaged goods, return) from message semantics without caller bias.</div>
            </div>
            <div class="preview-step">
                <div style="font-weight: 600; font-size: 0.9rem; color: #1e293b; margin-bottom: 2px;">2. Retrieve Policy Evidence</div>
                <div style="font-size: 0.82rem; color: #64748b;">Searches only the 6 trusted Markdown policy documents using rule-aware chunking and embedding cosine similarity.</div>
            </div>
            <div class="preview-step">
                <div style="font-weight: 600; font-size: 0.9rem; color: #1e293b; margin-bottom: 2px;">3. Grounded Validation</div>
                <div style="font-size: 0.82rem; color: #64748b;">Constrains recommendations to a closed action vocabulary and verifies that all cited sources exist in the retrieved set.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_decision_result(ticket: dict[str, Any]) -> None:
    """Render a structured AI decision result card."""
    decision = ticket.get("decision", {})
    action = decision.get("action", "—")
    style = get_action_style(action)
    action_label = html.escape(format_action_label(action))
    category = html.escape(style["category"])

    with st.container(border=True):
        # Header line with Ticket ID and Inferred Issue
        issue_raw = decision.get("inferred_issue_type")
        issue_display = html.escape(format_issue_type(issue_raw))
        ticket_id = ticket.get("id", "—")

        st.markdown(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
                <div>
                    <span style="font-size: 0.95rem; font-weight: 700; color: #0f172a;">Ticket #{ticket_id}</span>
                    <span style="font-size: 0.78rem; color: #64748b; margin-left: 8px;">Saved to database</span>
                </div>
                <div>
                    <span class="header-tag">Issue: {issue_display}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Action Hero Banner (The most visually prominent element)
        banner_html = f"""
        <div style="padding: 16px 18px; border-radius: 10px; background-color: {style['bg']}; border: 1.5px solid {style['border']}; margin: 8px 0 16px 0;">
            <div style="font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: {style['text']}; opacity: 0.9; margin-bottom: 4px;">
                Recommended Action • {category}
            </div>
            <div style="font-size: 1.35rem; font-weight: 800; color: {style['text']}; line-height: 1.3;">
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
            st.caption("Model confidence score")
            st.progress(max(0.0, min(1.0, conf_val)))

        # Policy rationale / reasoning
        reason = decision.get("reason", "")
        st.markdown("**Policy Rationale**")
        if reason:
            st.info(reason)
        else:
            st.caption("No rationale provided.")

        # Source citations
        sources = decision.get("sources", [])
        st.markdown("**Cited Policy Documents**")
        if sources:
            chips = "".join(f'<span class="source-chip">{html.escape(s)}</span>' for s in sources)
            st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)
        else:
            st.caption("No policy sources cited.")

        # Pipeline Telemetry & Guardrails
        retrieval_ms = decision.get("retrieval_latency_ms")
        llm_ms = decision.get("llm_latency_ms")
        guarded = decision.get("guardrail_triggered")
        telemetry_items = []
        if retrieval_ms is not None:
            telemetry_items.append(f"Retrieval: {retrieval_ms:.1f}ms")
        if llm_ms is not None:
            telemetry_items.append(f"LLM: {llm_ms:.1f}ms")
        if guarded:
            telemetry_items.append("[Guardrail Intervened]")
        elif retrieval_ms is not None or llm_ms is not None:
            telemetry_items.append("[Guardrail Verified]")

        if telemetry_items:
            st.caption(f"Pipeline Telemetry: {' • '.join(telemetry_items)}")


# ------------------------------------------------------------------
# Area 3 — History Review Workspace
# ------------------------------------------------------------------

def render_history() -> None:
    st.markdown("### Ticket Review Workspace")
    st.caption("Review previous support ticket submissions and stored grounded decisions.")

    try:
        tickets = get_client().list_tickets(st.session_state["token"])
    except AuthenticationError as exc:
        _handle_auth_error(exc)
        return
    except ApiError as exc:
        st.error(str(exc))
        return

    if not tickets:
        st.info("No tickets recorded yet. Create a ticket in New Decision to view history.")
        return

    # Selection dropdown driven solely by list_tickets payload (no N+1 requests)
    options = {
        t["id"]: (
            f"#{t['id']} • {format_action_label(t.get('decision', {}).get('action', '—'))} "
            f"({(t.get('decision', {}).get('confidence', 0) * 100):.0f}%) • "
            f"{t.get('message', '')[:70]}..."
        )
        for t in tickets
    }
    ticket_ids = list(options.keys())
    labels = list(options.values())

    col_sel, col_btn = st.columns([3.5, 1])
    with col_sel:
        selected_idx = st.selectbox(
            "Select a ticket to review",
            range(len(ticket_ids)),
            format_func=lambda i: labels[i],
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("View Ticket Details", type="primary", use_container_width=True):
            if selected_idx is not None:
                st.session_state["selected_ticket_id"] = ticket_ids[selected_idx]

    # Auto-select the first ticket if none explicitly selected
    current_selected = st.session_state.get("selected_ticket_id")
    if current_selected is None and ticket_ids:
        current_selected = ticket_ids[0]
        st.session_state["selected_ticket_id"] = current_selected

    # Fetch detail only for the single selected ticket
    if current_selected is not None:
        _render_ticket_detail_workspace(current_selected)


def _render_ticket_detail_workspace(ticket_id: int) -> None:
    """Fetch and display details for a single selected ticket."""
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

    with st.container(border=True):
        # Top metadata bar
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; margin-bottom: 16px;">
                <div>
                    <span style="font-size: 1.15rem; font-weight: 700; color: #0f172a;">Ticket #{ticket_id}</span>
                    <span style="font-size: 0.82rem; color: #64748b; margin-left: 8px;">Created: {html.escape(str(created_at))}</span>
                </div>
                <div>
                    <span class="header-tag">Issue: {issue_display}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_left, col_right = st.columns([1, 1], gap="large")

        with col_left:
            st.markdown("#### Customer Request")
            msg = ticket.get("message", "—")
            st.markdown(f"> {msg}")

            st.write("")
            st.markdown("#### Order Facts")
            facts: list[str] = []
            if ticket.get("order_value_inr") is not None:
                facts.append(f"Order Value: ₹{ticket['order_value_inr']}")
            if ticket.get("days_since_delivery") is not None:
                facts.append(f"Days Since Delivery: {ticket['days_since_delivery']}")
            if ticket.get("days_since_dispatch") is not None:
                facts.append(f"Days Since Dispatch: {ticket['days_since_dispatch']}")
            if ticket.get("product_type"):
                facts.append(f"Product Type: {ticket['product_type']}")
            if ticket.get("opened_status"):
                facts.append(f"Opened Status: {ticket['opened_status']}")
            if ticket.get("order_status"):
                facts.append(f"Order Status: {ticket['order_status']}")

            if facts:
                badges = "".join(f'<span class="fact-badge">{html.escape(f)}</span>' for f in facts)
                st.markdown(f"<div>{badges}</div>", unsafe_allow_html=True)
            else:
                st.caption("No structured facts were provided for this ticket.")

        with col_right:
            st.markdown("#### Grounded Decision")

            banner_html = f"""
            <div style="padding: 14px 16px; border-radius: 10px; background-color: {style['bg']}; border: 1.5px solid {style['border']}; margin: 8px 0 14px 0;">
                <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: {style['text']}; opacity: 0.9; margin-bottom: 3px;">
                    {style['category']}
                </div>
                <div style="font-size: 1.25rem; font-weight: 800; color: {style['text']}; line-height: 1.3;">
                    {action_label}
                </div>
            </div>
            """
            st.markdown(banner_html, unsafe_allow_html=True)

            confidence = decision.get("confidence")
            conf_val = float(confidence) if confidence is not None else 0.0
            st.metric("Confidence Score", f"{conf_val * 100:.0f}%")
            st.progress(max(0.0, min(1.0, conf_val)))

            st.write("")
            st.markdown("**Policy Rationale**")
            reason = decision.get("reason", "")
            if reason:
                st.info(reason)
            else:
                st.caption("No rationale recorded.")

            st.markdown("**Cited Policy Documents**")
            sources = decision.get("sources", [])
            if sources:
                chips = "".join(f'<span class="source-chip">{html.escape(s)}</span>' for s in sources)
                st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)
            else:
                st.caption("No sources cited.")

            # Pipeline Telemetry & Guardrails
            retrieval_ms = decision.get("retrieval_latency_ms")
            llm_ms = decision.get("llm_latency_ms")
            guarded = decision.get("guardrail_triggered")
            telemetry_items = []
            if retrieval_ms is not None:
                telemetry_items.append(f"Retrieval: {retrieval_ms:.1f}ms")
            if llm_ms is not None:
                telemetry_items.append(f"LLM: {llm_ms:.1f}ms")
            if guarded:
                telemetry_items.append("[Guardrail Intervened]")
            elif retrieval_ms is not None or llm_ms is not None:
                telemetry_items.append("[Guardrail Verified]")

            if telemetry_items:
                st.caption(f"**Pipeline Telemetry:** {' • '.join(telemetry_items)}")

            # Human-in-the-Loop (HITL) Review & Override Panel
            st.divider()
            st.markdown("#### Agent Review & Override (HITL)")
            reviewed_at = decision.get("reviewed_at")
            if reviewed_at:
                override_act = decision.get("human_override_action") or "Accepted"
                override_reason = decision.get("human_override_reason") or "No note provided."
                st.markdown(
                    f"""
                    <div style="background-color: #f0fdf4; padding: 12px 14px; border-radius: 8px; border: 1px solid #bbf7d0; margin-top: 4px;">
                        <div style="font-size: 0.76rem; font-weight: 700; text-transform: uppercase; color: #166534; margin-bottom: 2px;">
                            Review Completed
                        </div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #166534;">
                            Resolution: {html.escape(format_action_label(override_act))}
                        </div>
                        <div style="font-size: 0.84rem; color: #334155; margin-top: 4px;">
                            <strong>Note:</strong> {html.escape(override_reason)}
                        </div>
                        <div style="font-size: 0.74rem; color: #64748b; margin-top: 4px;">
                            Timestamp: {html.escape(str(reviewed_at))}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                col_accept, col_override = st.columns([1, 1.2])
                with col_accept:
                    if st.button("Accept AI Decision", type="primary", use_container_width=True, key=f"accept_{ticket_id}"):
                        try:
                            get_client().review_ticket(st.session_state["token"], ticket_id, accept=True)
                            st.success("Decision verified and accepted!")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                with col_override:
                    with st.expander("Override Decision", expanded=False):
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
                        override_action = st.selectbox("Corrected Action", action_options, key=f"override_act_{ticket_id}")
                        override_reason = st.text_input("Override Reason (Audit Log)", placeholder="e.g. Approved VIP customer exception", key=f"override_rsn_{ticket_id}")
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


# ------------------------------------------------------------------
# Main layout & Header
# ------------------------------------------------------------------

def main() -> None:
    if not is_authenticated():
        render_auth()
        return

    _inject_custom_css()

    user = st.session_state.get("user", {})
    user_email = user.get("email", "support@company.com")

    # Header bar
    col_hdr, col_auth = st.columns([3, 1])
    with col_hdr:
        st.markdown(
            """
            <div style="margin-bottom: 2px;">
                <span style="font-size: 1.35rem; font-weight: 800; color: #0f172a; letter-spacing: -0.01em;">AI Support Decision Assistant</span>
            </div>
            <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 8px;">
                Policy-grounded recommendations for customer support teams
            </div>
            <div>
                <span class="header-tag">6 Policy Documents</span>
                <span class="header-tag">Validated Citations</span>
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
                <span style="font-size: 0.82rem; color: #475569; font-weight: 500;">User: {html.escape(user_email)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Sign Out", type="secondary", use_container_width=True):
            _clear_session()
            st.rerun()

    st.divider()

    # Navigation: Segmented control or radio fallback
    nav = st.segmented_control(
        "Workspace Navigation",
        ["New Decision", "Ticket History"],
        default="New Decision",
        label_visibility="collapsed",
    )

    if nav == "New Decision" or nav is None:
        render_new_decision()
    else:
        render_history()


if __name__ == "__main__":
    main()
