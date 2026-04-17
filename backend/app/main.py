import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.signal import Signal  # noqa — ensure table is registered
from app.core.security import hash_password
from app.api import auth, users, strategies, trades, admin, backtest
from app.api import webhook
from app.api import ai
from app.api import signals

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tradingbot")

app = FastAPI(title="Trading Bot API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://mytradingbot.com",
        "http://mytradingbot.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(strategies.router)
app.include_router(trades.router)
app.include_router(admin.router)
app.include_router(backtest.router)
app.include_router(webhook.router)
app.include_router(ai.router)
app.include_router(signals.router)


# ── Auto-migration: safely add missing columns to existing tables ─────────────
_MIGRATIONS = [
    # users table
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS can_trade BOOLEAN DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS bot_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(30)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(64)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_link_token VARCHAR(64)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_code VARCHAR(10)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_code_expires TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verify_pending_email VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(128)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_notifications BOOLEAN DEFAULT TRUE",
    # trades table
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS paper_trade BOOLEAN DEFAULT FALSE",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_sl FLOAT",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS binance_order_id VARCHAR(64)",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS tp_order_id VARCHAR(64)",
    "ALTER TABLE trades ADD COLUMN IF NOT EXISTS sl_order_id VARCHAR(64)",
    # strategies table
    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE",
    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS public_description VARCHAR(500)",
    "ALTER TABLE strategies ADD COLUMN IF NOT EXISTS webhook_token VARCHAR(64)",
    # generate webhook tokens for strategies that don't have one
    "UPDATE strategies SET webhook_token = encode(gen_random_bytes(24), 'base64') WHERE webhook_token IS NULL",
]


def _run_migrations():
    """Run all migrations idempotently — safe to call on every startup."""
    try:
        with engine.connect() as conn:
            for sql in _MIGRATIONS:
                try:
                    conn.execute(text(sql))
                except Exception as e:
                    log.warning(f"Migration skipped ({sql[:55]}…): {e}")
            conn.commit()
        log.info("✅ DB auto-migration complete")
    except Exception as e:
        log.error(f"❌ DB migration error: {e}")


@app.on_event("startup")
def startup():
    # 1. Create brand-new tables (no-op for tables that already exist)
    Base.metadata.create_all(bind=engine)

    # 2. Add any missing columns to existing tables (idempotent)
    _run_migrations()

    # 3. Ensure admin user exists
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin_user:
            db.add(User(
                email=settings.ADMIN_EMAIL,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True,
                is_approved=True,
                can_trade=True,
                email_notifications=True,
            ))
            db.commit()
            log.info(f"✅ Admin user created: {settings.ADMIN_EMAIL}")
        else:
            # Ensure existing admin is always approved
            if not admin_user.is_approved:
                admin_user.is_approved = True
                db.commit()
    except Exception as e:
        log.error(f"❌ Admin user setup error: {e}")
        db.rollback()
    finally:
        db.close()


@app.get("/")
def root():
    return {"name": "Trading Bot API", "status": "ok", "version": "0.2.0"}


@app.get("/health")
def health():
    return {"ok": True}
