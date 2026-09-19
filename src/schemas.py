"""Validated authentication API contracts."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class RegistrationRequest(EmailRequest):
    password: SecretStr = Field(min_length=12, max_length=128)
    role: str = Field(default="agent", max_length=32)


class LoginRequest(EmailRequest):
    password: SecretStr = Field(min_length=1, max_length=128)


class ResetPasswordRequest(EmailRequest):
    new_password: SecretStr = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class ProductType(str, Enum):
    FOOD = "food"
    NON_FOOD = "non_food"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class OpenedStatus(str, Enum):
    OPENED = "opened"
    UNOPENED = "unopened"
    UNKNOWN = "unknown"


class OrderStatus(str, Enum):
    PROCESSING = "processing"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    UNKNOWN = "unknown"


class Action(str, Enum):
    APPROVE_REFUND_OR_REPLACEMENT = "APPROVE_REFUND_OR_REPLACEMENT"
    APPROVE_REPLACEMENT = "APPROVE_REPLACEMENT"
    APPROVE_RETURN = "APPROVE_RETURN"
    CANCEL_AND_REFUND = "CANCEL_AND_REFUND"
    CANNOT_CANCEL_AFTER_DISPATCH = "CANNOT_CANCEL_AFTER_DISPATCH"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    OFFER_REPLACEMENT_OR_REFUND = "OFFER_REPLACEMENT_OR_REFUND"
    OPEN_SHIPPING_INVESTIGATION = "OPEN_SHIPPING_INVESTIGATION"
    REJECT_FOOD_RETURN = "REJECT_FOOD_RETURN"
    REJECT_OPENED_ITEM = "REJECT_OPENED_ITEM"
    REJECT_OUTSIDE_WINDOW = "REJECT_OUTSIDE_WINDOW"
    REPLACE_CORRECT_ITEM = "REPLACE_CORRECT_ITEM"
    REQUEST_DEFECT_EVIDENCE = "REQUEST_DEFECT_EVIDENCE"
    REQUEST_PHOTOS = "REQUEST_PHOTOS"
    WAIT_AND_TRACK = "WAIT_AND_TRACK"


class IssueType(str, Enum):
    CANCELLATION = "cancellation"
    DAMAGED = "damaged"
    DEFECTIVE = "defective"
    RETURN = "return"
    SHIPPING_DELAY = "shipping_delay"
    UNKNOWN = "unknown"
    WRONG_ITEM = "wrong_item"


class TicketRequest(BaseModel):
    """Ticket facts supplied to the decision workflow; issue type is inferred."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4_000)
    order_value_inr: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    days_since_delivery: int | None = Field(default=None, ge=0, le=36_500)
    days_since_dispatch: int | None = Field(default=None, ge=0, le=36_500)
    product_type: ProductType | None = None
    opened_status: OpenedStatus | None = None
    order_status: OrderStatus | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class DecisionDraft(BaseModel):
    """Validated structured decision before it reaches persistence."""

    model_config = ConfigDict(extra="forbid")

    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=1_500)
    sources: list[str] = Field(min_length=1, max_length=6)
    inferred_issue_type: IssueType
    retrieval_latency_ms: float | None = None
    llm_latency_ms: float | None = None
    guardrail_triggered: bool | None = False
    raw_action: Action | None = None
    raw_reason: str | None = None

    @field_validator("confidence")
    @classmethod
    def finite_confidence(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("confidence must be finite")
        return value

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reason must not be blank")
        return stripped

    @field_validator("sources")
    @classmethod
    def valid_sources(cls, value: list[str]) -> list[str]:
        normalized = [source.strip() for source in value]
        if any(not source for source in normalized):
            raise ValueError("sources must not contain blank filenames")
        if len(set(normalized)) != len(normalized):
            raise ValueError("sources must be deduplicated")
        return normalized


class DecisionResponse(DecisionDraft):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    raw_action: Action | None = None
    human_override_action: str | None = None
    human_override_reason: str | None = None
    reviewed_at: datetime | None = None


class ReviewRequest(BaseModel):
    """Human-in-the-Loop review: accept or override an AI decision."""

    model_config = ConfigDict(extra="forbid")

    action: Action | None = None
    reason: str | None = Field(default=None, max_length=1_000)
    accept: bool = False

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is not None:
            stripped = value.strip()
            return stripped if stripped else None
        return None


class TicketReviewRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    reviewer_id: int
    action: str
    reason: str
    created_at: datetime


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message: str
    order_value_inr: Decimal | None
    days_since_delivery: int | None
    days_since_dispatch: int | None
    product_type: ProductType | None
    opened_status: OpenedStatus | None
    order_status: OrderStatus | None
    created_at: datetime
    decision: DecisionResponse
    reviews: list[TicketReviewRecord] = []
