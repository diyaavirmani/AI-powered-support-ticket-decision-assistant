"""FastAPI application and authentication endpoints."""

from contextlib import asynccontextmanager
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from src.auth import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from src.database import SessionLocal, get_db, init_db
from src.decision import (
    DecisionError,
    DecisionValidationError,
    DecisionWorkflow,
    LazyProductionDecisionWorkflow,
    get_ticket_workflow,
)
from src.dependencies import get_current_user, get_current_user_id
from src.models import Decision, Ticket, TicketReview, User, utc_now
from src.retrieval import ProviderConfigurationError, ProviderServiceError, RetrievalError
from src.schemas import (
    DecisionDraft,
    LoginRequest,
    RegistrationRequest,
    ResetPasswordRequest,
    ReviewRequest,
    TicketRequest,
    TicketResponse,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger("support_assistant.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("Database initialized with WAL mode and schema auto-migrations")
    yield


app = FastAPI(title="AI Support Decision Assistant", version="0.2.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        sanitized = {key: value for key, value in error.items() if key != "input"}
        errors.append(sanitized)
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))


@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegistrationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    existing_user = db.scalar(select(User).where(User.email == str(request.email)))
    if existing_user is not None:
        logger.warning("Registration rejected: email %s already exists", request.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=str(request.email),
        password_hash=hash_password(request.password.get_secret_value()),
        role=request.role or "agent",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None
    db.refresh(user)
    logger.info("Registered user %d with role %s", user.id, user.role)
    return user


@app.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(request.email)))
    encoded_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(
        request.password.get_secret_value(), encoded_hash
    )
    if user is None or not password_matches:
        logger.warning("Failed login attempt for email: %s", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("User %d logged in successfully", user.id)
    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == str(request.email)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with this email address",
        )
    user.password_hash = hash_password(request.new_password.get_secret_value())
    db.commit()
    logger.info("Password reset successfully for user %d (%s)", user.id, user.email)
    return {"message": "Password reset successfully"}


@app.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


def ticket_workflow_dependency() -> DecisionWorkflow:
    return LazyProductionDecisionWorkflow()


def _persist_ticket(
    db: Session, user_id: int, request: TicketRequest, decision: DecisionDraft
) -> Ticket:
    ticket = Ticket(
        user_id=user_id,
        message=request.message,
        order_value_inr=request.order_value_inr,
        days_since_delivery=request.days_since_delivery,
        days_since_dispatch=request.days_since_dispatch,
        product_type=request.product_type.value if request.product_type else None,
        opened_status=request.opened_status.value if request.opened_status else None,
        order_status=request.order_status.value if request.order_status else None,
    )
    ticket.decision = Decision(
        action=decision.action.value,
        raw_action=decision.raw_action.value if decision.raw_action else None,
        inferred_issue_type=decision.inferred_issue_type,
        reason=decision.reason,
        confidence=decision.confidence,
        sources=decision.sources,
        retrieval_latency_ms=decision.retrieval_latency_ms,
        llm_latency_ms=decision.llm_latency_ms,
        guardrail_triggered=decision.guardrail_triggered,
    )
    db.add(ticket)
    try:
        db.commit()
    except (IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        logger.exception("Failed to persist ticket decision: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store ticket decision",
        ) from None
    db.refresh(ticket)
    # Ensure decision and reviews are loaded before returning
    _ = ticket.decision
    _ = ticket.reviews
    logger.info("Persisted ticket %d with decision action %s", ticket.id, ticket.decision.action)
    return ticket


@app.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(
    request: TicketRequest,
    current_user_id: Annotated[int, Depends(get_current_user_id)],
    workflow: Annotated[DecisionWorkflow, Depends(ticket_workflow_dependency)],
) -> Ticket:
    # Notice: zero DB connections held during slow external LLM inference
    try:
        decision = workflow.decide(request)
    except ProviderConfigurationError as exc:
        logger.error("Provider configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI decision service is not configured",
        ) from None
    except ProviderServiceError as exc:
        logger.error("Provider service error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI decision service is unavailable",
        ) from None
    except (DecisionValidationError, DecisionError) as exc:
        logger.error("Decision validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI decision service returned an unusable decision",
        ) from None
    except RetrievalError as exc:
        logger.error("Retrieval error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Policy retrieval service is unavailable",
        ) from None

    # Momentary connection checked out only for the atomic insert transaction
    with SessionLocal() as db:
        return _persist_ticket(db, current_user_id, request, decision)


@app.get("/tickets", response_model=list[TicketResponse])
def list_tickets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 20,
    offset: int = 0,
) -> list[Ticket]:
    bounded_limit = min(max(limit, 1), 100)
    bounded_offset = max(offset, 0)
    statement = (
        select(Ticket)
        .options(selectinload(Ticket.decision), selectinload(Ticket.reviews))
        .where(Ticket.user_id == current_user.id)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .limit(bounded_limit)
        .offset(bounded_offset)
    )
    return list(db.scalars(statement))


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Ticket:
    statement = (
        select(Ticket)
        .options(selectinload(Ticket.decision), selectinload(Ticket.reviews))
        .where(Ticket.id == ticket_id, Ticket.user_id == current_user.id)
    )
    ticket = db.scalar(statement)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@app.post("/tickets/{ticket_id}/review", response_model=TicketResponse)
def review_ticket(
    ticket_id: int,
    request: ReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Ticket:
    if current_user.role not in ("agent", "admin"):
        logger.warning("Unauthorized review attempt by non-agent user %d", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only support agents can review or override ticket decisions.",
        )

    statement = (
        select(Ticket)
        .options(selectinload(Ticket.decision), selectinload(Ticket.reviews))
        .where(Ticket.id == ticket_id, Ticket.user_id == current_user.id)
    )
    ticket = db.scalar(statement)
    if ticket is None or ticket.decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    if request.accept:
        final_action = ticket.decision.action
        final_reason = request.reason or "Accepted by human agent"
    else:
        if not request.action or not request.reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Action and reason are required when overriding a decision.",
            )
        final_action = request.action.value
        final_reason = request.reason

    # Append-only audit record
    review_record = TicketReview(
        ticket_id=ticket.id,
        reviewer_id=current_user.id,
        action=final_action,
        reason=final_reason,
        created_at=utc_now(),
    )
    db.add(review_record)

    # Denormalized latest review fields on decision for quick access
    ticket.decision.human_override_action = final_action
    ticket.decision.human_override_reason = final_reason
    ticket.decision.reviewed_at = utc_now()

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to record review for ticket %d: %s", ticket_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not record review",
        ) from None
    db.refresh(ticket)
    _ = ticket.reviews
    logger.info("Review recorded for ticket %d: action=%s by user=%d", ticket.id, final_action, current_user.id)
    return ticket
