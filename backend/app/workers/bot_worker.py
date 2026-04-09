"""Celery tasks for running the trading bot per user."""
import logging
from app.workers.celery_app import celery_app
from app.database import SessionLocal
from app.models.user import User
from app.services.strategy_engine import run_user_cycle

log = logging.getLogger(__name__)


@celery_app.task(name="app.workers.bot_worker.scan_all_users")
def scan_all_users():
    """Periodic: dispatch a per-user task for everyone with bot enabled."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.bot_enabled == True, User.is_active == True).all()
        for u in users:
            run_user_bot.delay(u.id)
        return f"dispatched {len(users)}"
    finally:
        db.close()


@celery_app.task(name="app.workers.bot_worker.run_user_bot")
def run_user_bot(user_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "no user"
        run_user_cycle(db, user)
        return "ok"
    except Exception as e:
        log.exception("user bot error")
        return f"error: {e}"
    finally:
        db.close()
