"""Database schema and constraint tests."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database import engine
from src.models import User


def test_required_tables_columns_and_constraints_exist(db_session: Session) -> None:
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {"users", "tickets", "decisions"}

    raw_user_columns = inspector.get_columns("users")
    user_columns = {column["name"] for column in raw_user_columns}
    assert user_columns == {"id", "email", "password_hash", "created_at"}
    assert all(not column["nullable"] for column in raw_user_columns)

    raw_ticket_columns = inspector.get_columns("tickets")
    ticket_columns = {column["name"] for column in raw_ticket_columns}
    assert {
        "id",
        "user_id",
        "message",
        "order_value_inr",
        "days_since_delivery",
        "days_since_dispatch",
        "product_type",
        "opened_status",
        "order_status",
        "created_at",
    } == ticket_columns
    ticket_nullability = {
        column["name"]: column["nullable"] for column in raw_ticket_columns
    }
    assert all(
        not ticket_nullability[name]
        for name in ("id", "user_id", "message", "created_at")
    )
    assert all(
        ticket_nullability[name]
        for name in (
            "order_value_inr",
            "days_since_delivery",
            "days_since_dispatch",
            "product_type",
            "opened_status",
            "order_status",
        )
    )

    raw_decision_columns = inspector.get_columns("decisions")
    decision_columns = {column["name"] for column in raw_decision_columns}
    assert {
        "id",
        "ticket_id",
        "action",
        "inferred_issue_type",
        "reason",
        "confidence",
        "sources",
        "created_at",
    } == decision_columns
    assert all(not column["nullable"] for column in raw_decision_columns)

    email_indexes = inspector.get_indexes("users")
    assert any(
        index["unique"] and index["column_names"] == ["email"]
        for index in email_indexes
    )
    decision_uniques = inspector.get_unique_constraints("decisions")
    assert any(item["column_names"] == ["ticket_id"] for item in decision_uniques)
    assert inspector.get_foreign_keys("tickets")[0]["referred_table"] == "users"
    assert inspector.get_foreign_keys("decisions")[0]["referred_table"] == "tickets"
    assert {item["name"] for item in inspector.get_check_constraints("tickets")} == {
        "ck_tickets_order_value_nonnegative",
        "ck_tickets_delivery_days_nonnegative",
        "ck_tickets_dispatch_days_nonnegative",
    }
    assert {
        item["name"] for item in inspector.get_check_constraints("decisions")
    } == {"ck_decisions_confidence_range"}


def test_unique_email_constraint_is_enforced(db_session: Session) -> None:
    db_session.add_all(
        [
            User(email="same@example.com", password_hash="hash-one"),
            User(email="same@example.com", password_hash="hash-two"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_sqlite_foreign_keys_are_enforced(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO tickets (user_id, message, created_at) "
                "VALUES (999999, 'orphan', CURRENT_TIMESTAMP)"
            )
        )
        db_session.commit()
