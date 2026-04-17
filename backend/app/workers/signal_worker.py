"""Celery task: periodic TA signal scanning.

Runs every SIGNAL_INTERVAL_MINUTES minutes (default: 30).
For each configured symbol, runs the signal engine, stores result in DB,
then — if signal is actionable and cooldown has elapsed — sends Telegram to:
  1. The global channel/group (SIGNAL_TELEGRAM_CHAT_ID in .env)
  2. Every active user who has Telegram linked (telegram_chat_id set)
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List

import httpx

from app.workers.celery_app import celery_app
from app.database import SessionLocal
from app.models.signal import Signal
from app.models.user import User
from app.config import settings
from app.services.signal_engine import analyze_symbol, NEUTRAL

log = logging.getLogger(__name__)


# ─── Telegram sender ──────────────────────────────────────────────────────────

def _send_telegram(message: str, chat_id: str) -> bool:
    """Send a message to one chat_id. Returns True on success."""
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        if not resp.is_success:
            log.warning(f"[signal] Telegram {chat_id} → {resp.status_code}: {resp.text[:100]}")
            return False
        return True
    except Exception as e:
        log.error(f"[signal] Telegram send error ({chat_id}): {e}")
        return False


def _broadcast(message: str, db) -> dict:
    """
    Send signal message to:
      - Global channel/group (settings.SIGNAL_TELEGRAM_CHAT_ID)
      - All active users with telegram_chat_id set

    Returns counts: {channel: bool, users_sent: int, users_total: int}
    """
    channel_ok = False
    users_sent = 0

    # 1. Global channel / group
    if settings.SIGNAL_TELEGRAM_CHAT_ID:
        channel_ok = _send_telegram(message, settings.SIGNAL_TELEGRAM_CHAT_ID)
        if channel_ok:
            log.info("[signal] ✅ Sent to channel/group")

    # 2. Per-user (all active users with Telegram linked)
    users: List[User] = (
        db.query(User)
        .filter(
            User.is_active == True,
            User.telegram_chat_id != None,
            User.telegram_chat_id != "",
        )
        .all()
    )

    for user in users:
        ok = _send_telegram(message, user.telegram_chat_id)
        if ok:
            users_sent += 1
        else:
            log.warning(f"[signal] Failed to send to user {user.id} ({user.email})")

    log.info(f"[signal] Broadcast complete — channel: {channel_ok}, users: {users_sent}/{len(users)}")
    return {
        "channel": channel_ok,
        "users_sent": users_sent,
        "users_total": len(users),
    }


# ─── Cooldown check ───────────────────────────────────────────────────────────

def _cooldown_ok(db, symbol: str, exchange: str, timeframe: str,
                 signal: str, hours: int) -> bool:
    """True if the same signal for this symbol hasn't fired within `hours`."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    existing = (
        db.query(Signal)
        .filter(
            Signal.symbol   == symbol.upper(),
            Signal.exchange == exchange,
            Signal.timeframe== timeframe,
            Signal.signal   == signal,
            Signal.created_at >= cutoff,
        )
        .first()
    )
    return existing is None


# ─── DB helper ────────────────────────────────────────────────────────────────

def _save_signal(db, result: dict) -> Signal:
    """Persist signal to DB and return the model instance."""
    risk   = result.get("risk", {})
    levels = result.get("levels", {})
    row = Signal(
        symbol       = result["symbol"],
        exchange     = result["exchange"],
        timeframe    = result["timeframe"],
        signal       = result["signal"],
        score        = result["score"],
        price        = result["price"],
        atr          = result.get("atr"),
        sl           = risk.get("sl"),
        tp1          = risk.get("tp1"),
        tp2          = risk.get("tp2"),
        rr_ratio     = risk.get("rr"),
        support      = levels.get("support"),
        resistance   = levels.get("resistance"),
        details_json = json.dumps({
            "score_breakdown":   result.get("score_breakdown", {}),
            "details":           result.get("details", {}),
            "telegram_message":  result.get("telegram_message", ""),
        }),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ─── Main Celery task ─────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.signal_worker.run_signal_scan")
def run_signal_scan():
    """Scan all configured symbols and broadcast signals to channel + all users."""
    symbols   = [s.strip().upper() for s in settings.SIGNAL_SYMBOLS.split(",") if s.strip()]
    exchange  = settings.SIGNAL_EXCHANGE
    timeframe = settings.SIGNAL_TIMEFRAME
    cooldown  = settings.SIGNAL_COOLDOWN_HOURS

    results = []
    for symbol in symbols:
        try:
            result = analyze_symbol(
                symbol           = symbol,
                exchange         = exchange,
                timeframe        = timeframe,
                risk_multiplier  = settings.SIGNAL_RISK_MULT,
                tp1_multiplier   = settings.SIGNAL_TP1_MULT,
                tp2_multiplier   = settings.SIGNAL_TP2_MULT,
                threshold_strong = settings.SIGNAL_THRESHOLD_STRONG,
                threshold_weak   = settings.SIGNAL_THRESHOLD_WEAK,
            )
        except Exception as e:
            log.error(f"[signal] analyze_symbol failed for {symbol}: {e}")
            continue

        if not result:
            log.info(f"[signal] {symbol}: no result")
            continue

        signal = result["signal"]
        log.info(f"[signal] {symbol} → {signal} (score={result['score']})")

        db = SessionLocal()
        try:
            # Always save to DB (dashboard history)
            _save_signal(db, result)

            # Broadcast only for actionable signals + cooldown respected
            if signal != NEUTRAL:
                if _cooldown_ok(db, symbol, exchange, timeframe, signal, cooldown):
                    stats = _broadcast(result["telegram_message"], db)
                    log.info(
                        f"[signal] {symbol} {signal} broadcast — "
                        f"channel={stats['channel']}, "
                        f"users={stats['users_sent']}/{stats['users_total']}"
                    )
                else:
                    log.info(f"[signal] {symbol} {signal} — cooldown active, skipping")

            results.append(f"{symbol}:{signal}")

        except Exception as e:
            log.error(f"[signal] DB/broadcast error for {symbol}: {e}")
            db.rollback()
        finally:
            db.close()

    return f"scanned {len(symbols)}: {', '.join(results)}"
