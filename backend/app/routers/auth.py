"""Authentication router: login, register, me."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.user import UserCreate, UserLogin, UserResponse, Token
from ..services.auth_service import authenticate_user, create_user
from ..core.security import create_access_token
from ..core.deps import get_current_user
from ..core.logging_config import log_event
from ..models.user import User
from ..config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    try:
        user = create_user(
            db=db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role or "user",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    log_event(
        db=db,
        event_type="user_registered",
        message=f"New user registered: {user.email}",
        level="info",
        user_id=str(user.id),
    )
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate and return a JWT bearer token."""
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        log_event(
            db=db,
            event_type="login_failed",
            message=f"Failed login attempt for {payload.email}",
            level="warning",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role},
        expires_delta=expire_delta,
    )

    log_event(
        db=db,
        event_type="login_success",
        message=f"User logged in: {user.email}",
        level="info",
        user_id=str(user.id),
    )

    return Token(access_token=token, token_type="bearer", user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
