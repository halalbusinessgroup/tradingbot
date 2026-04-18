"""Telegram bot configuration — readable/writable from UI."""
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.bot_setting import BotSetting
from app.config import settings

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


# ─── helpers ──────────────────────────────────────────────────────────────────

def get_db_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(BotSetting).filter(BotSetting.key == key).first()
    return row.value if (row and row.value) else default


def set_db_setting(db: Session, key: str, value: str):
    row = db.query(BotSetting).filter(BotSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(BotSetting(key=key, value=value))
    db.commit()


def get_effective_chat_id(db: Session) -> str:
    """Returns DB-stored chat_id or falls back to env."""
    return get_db_setting(db, "signal_telegram_chat_id") or settings.SIGNAL_TELEGRAM_CHAT_ID


def get_effective_bot_token() -> str:
    return settings.TELEGRAM_BOT_TOKEN


def _send(message: str, chat_id: str, token: str) -> tuple[bool, str]:
    if not token or not chat_id:
        return False, "Token or chat_id missing"
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = httpx.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        if r.is_success:
            return True, "ok"
        return False, r.json().get("description", r.text[:100])
    except Exception as e:
        return False, str(e)


# ─── GET /api/telegram/config ─────────────────────────────────────────────────

@router.get("/config")
def get_telegram_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return current effective Telegram configuration."""
    token = get_effective_bot_token()
    chat_id = get_effective_chat_id(db)
    username = settings.TELEGRAM_BOT_USERNAME

    return {
        "bot_token_set":    bool(token),
        "bot_token_masked": (f"...{token[-8:]}" if len(token) > 8 else "set") if token else "",
        "bot_username":     username,
        "bot_link":         f"https://t.me/{username}" if username else "",
        "signal_chat_id":   chat_id,
        "personal_linked":  bool(user.telegram_chat_id),
        "personal_chat_id": user.telegram_chat_id or "",
    }


# ─── POST /api/telegram/config ────────────────────────────────────────────────

class TelegramConfigIn(BaseModel):
    signal_chat_id: str = ""


@router.post("/config")
def save_telegram_config(
    body: TelegramConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save the global signal channel/group chat ID."""
    set_db_setting(db, "signal_telegram_chat_id", body.signal_chat_id.strip())
    return {"ok": True, "signal_chat_id": body.signal_chat_id.strip()}


# ─── POST /api/telegram/test ──────────────────────────────────────────────────

@router.post("/test")
def test_telegram(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send test messages to all configured targets and return detailed results."""
    token   = get_effective_bot_token()
    chat_id = get_effective_chat_id(db)
    results = {}

    # Global channel
    if chat_id:
        ok, err = _send("🧪 <b>Test mesajı</b> — Signal botu işləyir! ✅", chat_id, token)
        results["global"] = {"chat_id": chat_id, "ok": ok, "error": err if not ok else ""}
    else:
        results["global"] = {"chat_id": "", "ok": False, "error": "Channel ID təyin edilməyib"}

    # Personal
    if user.telegram_chat_id:
        ok, err = _send(f"🧪 <b>Şəxsi test</b> — {user.email} hesabı bağlıdır! ✅", user.telegram_chat_id, token)
        results["personal"] = {"chat_id": user.telegram_chat_id, "ok": ok, "error": err if not ok else ""}
    else:
        results["personal"] = {"chat_id": "", "ok": False, "error": "Şəxsi Telegram bağlanmayıb"}

    # Groups
    from app.models.telegram_group import UserTelegramGroup
    groups = db.query(UserTelegramGroup).filter(
        UserTelegramGroup.user_id == user.id,
        UserTelegramGroup.is_active == True,
    ).all()
    results["groups"] = []
    for g in groups:
        ok, err = _send(f"🧪 <b>Qrup testi</b> — {g.title} ✅", g.chat_id, token)
        results["groups"].append({"title": g.title, "chat_id": g.chat_id, "ok": ok, "error": err if not ok else ""})

    results["bot_token_set"] = bool(token)
    return results
