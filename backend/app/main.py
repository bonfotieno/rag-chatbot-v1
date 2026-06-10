"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.logging_config import setup_logging
from .database import init_db
from .routers import auth, documents, chat, logs

setup_logging()
logger = logging.getLogger(__name__)


def _ensure_default_admin() -> None:
    """Create a default admin account if no admin user exists."""
    from .database import SessionLocal
    from .models.user import User
    from .services.auth_service import create_user
    import os

    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.role == "admin").first()
        if admin_exists:
            return

        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123456")

        create_user(
            db=db,
            email=admin_email,
            password=admin_password,
            full_name="System Administrator",
            role="admin",
        )
        logger.info("Default admin account created: %s", admin_email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not create default admin: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialise DB on startup."""
    logger.info("Starting Chatbot backend…")
    try:
        init_db()
        logger.info("Database initialised")
        _ensure_default_admin()
    except Exception as exc:
        logger.exception("Startup error: %s", exc)
        raise
    yield
    logger.info("Chatbot backend shutting down")


app = FastAPI(
    title="Chatbot API",
    description="RAG-powered chatbot with document management and admin features",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Filter
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(logs.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe."""
    return {"status": "ok"}
