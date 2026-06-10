"""Authentication and user management service functions."""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from ..models.user import User
from ..core.security import verify_password, get_password_hash

logger = logging.getLogger(__name__)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Fetch a user by email address (case-insensitive)."""
    return db.query(User).filter(User.email == email.lower().strip()).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Validate email + password.  Returns the User on success, None otherwise."""
    user = get_user_by_email(db, email)
    if user is None:
        logger.warning("Login attempt for unknown email: %s", email)
        return None
    if not verify_password(password, user.hashed_password):
        logger.warning("Invalid password for email: %s", email)
        return None
    if not user.is_active:
        logger.warning("Login attempt for deactivated account: %s", email)
        return None
    return user


def create_user(
    db: Session,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    role: str = "user",
) -> User:
    """Create and persist a new user.

    Raises:
        ValueError: if the email is already registered.
    """
    existing = get_user_by_email(db, email)
    if existing:
        raise ValueError(f"Email '{email}' is already registered")

    hashed = get_password_hash(password)
    user = User(
        email=email.lower().strip(),
        hashed_password=hashed,
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created new user: %s (role=%s)", user.email, user.role)
    return user
