"""Streamlit frontend for the AI Support Decision Assistant.

Communicates with FastAPI exclusively through HTTP.
Never accesses SQLite, SQLAlchemy, embeddings, or Gemini directly.
"""

import os

import streamlit as st

from src.api_client import ApiClient, ApiError, AuthenticationError

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Support Decision Assistant",
    layout="centered",
)


def get_client() -> ApiClient:
    return ApiClient(base_url=API_BASE_URL)


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
# Login / Register
# ------------------------------------------------------------------

def render_auth() -> None:
    st.title("🔐 Login or Register")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_register:
        with st.form("register_form"):
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            submitted = st.form_submit_button("Register")
        if submitted:
            if not reg_email or not reg_password:
                st.warning("Please provide both email and password.")
            else:
                try:
                    get_client().register(reg_email, reg_password)
                    st.success("Account created. Please switch to the Login tab to sign in.")
                except ApiError as exc:
                    st.error(str(exc))

    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")
        if submitted:
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


# ------------------------------------------------------------------
# New Decision
# ------------------------------------------------------------------

def render_new_decision() -> None:
    st.header("📝 New Support Ticket Decision")

    with st.form("ticket_form"):
        message = st.text_area(
            "Customer message *",
            height=120,
            placeholder="Describe the support issue…",
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            order_value_str = st.text_input(
                "Order value (INR)",
                placeholder="e.g. 3500",
                help="Leave blank if unknown.",
            )
        with col2:
            delivery_str = st.text_input(
                "Days since delivery",
                placeholder="e.g. 3",
                help="Leave blank if unknown or not yet delivered.",
            )
        with col3:
            dispatch_str = st.text_input(
                "Days since dispatch",
                placeholder="e.g. 9",
                help="Leave blank if unknown.",
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            product_options = ["— Not specified —", "food", "non_food", "mixed", "unknown"]
            product_type = st.selectbox("Product type", product_options)
        with col5:
            opened_options = ["— Not specified —", "opened", "unopened", "unknown"]
            opened_status = st.selectbox("Opened status", opened_options)
        with col6:
            order_options = ["— Not specified —", "processing", "dispatched", "delivered", "unknown"]
            order_status = st.selectbox("Order status", order_options)

        submitted = st.form_submit_button("Get AI Decision")

    if submitted:
        if not message or not message.strip():
            st.warning("Please enter a customer message.")
            return

        # Parse nullable numeric fields.
        order_value = None
        if order_value_str and order_value_str.strip():
            try:
                order_value = float(order_value_str.strip())
                if order_value < 0:
                    st.warning("Order value cannot be negative.")
                    return
            except ValueError:
                st.warning("Order value must be a number.")
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

        with st.spinner("Requesting AI decision…"):
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

    # Display most recent decision.
    decision_data = st.session_state.get("last_decision")
    if decision_data:
        _render_decision_result(decision_data)


def _render_decision_result(ticket: dict) -> None:
    decision = ticket.get("decision", {})
    st.divider()
    st.subheader("✅ AI Decision")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Recommended Action", decision.get("action", "—"))
    with col2:
        confidence = decision.get("confidence")
        display = f"{confidence * 100:.0f}%" if confidence is not None else "—"
        st.metric("Confidence", display)

    reason = decision.get("reason", "")
    if reason:
        st.markdown(f"**Reason:** {reason}")

    sources = decision.get("sources", [])
    if sources:
        st.markdown("**Policy sources:** " + ", ".join(f"`{s}`" for s in sources))


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

def render_history() -> None:
    st.header("📋 Ticket History")

    try:
        tickets = get_client().list_tickets(st.session_state["token"])
    except AuthenticationError as exc:
        _handle_auth_error(exc)
        return
    except ApiError as exc:
        st.error(str(exc))
        return

    if not tickets:
        st.info("No tickets yet. Submit a new ticket to get started.")
        return

    for t in tickets:
        decision = t.get("decision", {})
        preview = (t.get("message", "")[:80] + "…") if len(t.get("message", "")) > 80 else t.get("message", "")
        label = (
            f"**#{t['id']}** — {decision.get('action', '—')} "
            f"({(decision.get('confidence', 0) * 100):.0f}% confidence) — "
            f"_{preview}_"
        )
        with st.expander(label):
            _render_ticket_detail(t["id"])


def _render_ticket_detail(ticket_id: int) -> None:
    try:
        ticket = get_client().get_ticket(st.session_state["token"], ticket_id)
    except AuthenticationError as exc:
        _handle_auth_error(exc)
        return
    except ApiError as exc:
        st.error(str(exc))
        return

    st.markdown(f"**Created:** {ticket.get('created_at', '—')}")
    st.markdown(f"**Message:** {ticket.get('message', '—')}")

    facts = []
    if ticket.get("order_value_inr") is not None:
        facts.append(f"Order value: ₹{ticket['order_value_inr']}")
    if ticket.get("days_since_delivery") is not None:
        facts.append(f"Days since delivery: {ticket['days_since_delivery']}")
    if ticket.get("days_since_dispatch") is not None:
        facts.append(f"Days since dispatch: {ticket['days_since_dispatch']}")
    if ticket.get("product_type"):
        facts.append(f"Product type: {ticket['product_type']}")
    if ticket.get("opened_status"):
        facts.append(f"Opened status: {ticket['opened_status']}")
    if ticket.get("order_status"):
        facts.append(f"Order status: {ticket['order_status']}")
    if facts:
        st.markdown("**Ticket facts:** " + " · ".join(facts))

    decision = ticket.get("decision", {})
    if decision:
        st.divider()
        st.markdown(f"**Action:** `{decision.get('action', '—')}`")
        confidence = decision.get("confidence")
        if confidence is not None:
            st.markdown(f"**Confidence:** {confidence * 100:.0f}%")
        st.markdown(f"**Reason:** {decision.get('reason', '—')}")
        sources = decision.get("sources", [])
        if sources:
            st.markdown("**Sources:** " + ", ".join(f"`{s}`" for s in sources))


# ------------------------------------------------------------------
# Main layout
# ------------------------------------------------------------------

def main() -> None:
    if not is_authenticated():
        render_auth()
        return

    user = st.session_state.get("user", {})
    st.sidebar.markdown(f"**Logged in as:** {user.get('email', '—')}")
    if st.sidebar.button("Logout"):
        _clear_session()
        st.rerun()

    page = st.sidebar.radio("Navigate", ["New Decision", "History"], label_visibility="collapsed")
    if page == "New Decision":
        render_new_decision()
    else:
        render_history()


if __name__ == "__main__":
    main()
