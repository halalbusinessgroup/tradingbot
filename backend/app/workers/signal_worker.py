"""Celery task: periodic TA signal scanning — per-user watchlists.

Flow:
  1. Collect all unique (symbol, exchange) pairs from all users' watchlists
     (fallback: global SIGNAL_SYMBOLS setting if no watchlists exist)
  2. Run signal engine for each pair
  3. For each actionable signal (cooldown respected):
     a. Send to global SIGNAL_TELEGRAM_CHAT_ID (if configured)
     b. Send to every user who watches this symbol:
        - their personal Telegram chat
        - their linked Telegram groups (active only)
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import List

import httpx

from app.workers.celery_app import celery_app
from app.database import SessionLocal
from app.models.signal import Signal
from app.models.user import User
from app.models.watchlist import UserWatchlist
from app.models.telegram_group import UserTelegramGroup
from app.config import settings
from app.services.signal_engine import analyze_symbol, NEUTRAL

log = logging.getLogger(__name__)


# ─── Telegram sender ──────────────────────────────────────────────────────────

def _send_telegram(message: str, chat_id: str) -> bool:
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


def _broadcast_to_global(message: str) -> bool:
    if not settings.SIGNAL_TELEGRAM_CHAT_ID:
        return False
    ok = _send_telegram(message, settings.SIGNAL_TELEGRAM_CHAT_ID)
    if ok:
        log.info("[signal] ✅ Sent to global channel/group")
    return ok


def _broadcast_to_user(message: str, user, db) -> dict:
    """Send to user's personal chat + all their active groups."""
    personal_ok = False
    groups_sent = 0

    if user.telegram_chat_id:
        personal_ok = _send_telegram(message, user.telegram_chat_id)

    groups: List[UserTelegramGroup] = (
        db.query(UserTelegramGroup)
        .filter(
            UserTelegramGroup.user_id == user.id,
            UserTelegramGroup.is_active == True,
        )
        .all()
    )
    for grp in groups:
        ok = _send_telegram(message, grp.chat_id)
        if ok:
            groups_sent += 1

    return {"personal": personal_ok, "groups_sent": groups_sent, "groups_total": len(groups)}


def _broadcast(message: str, db) -> dict:
    """Legacy: send to global channel + ALL active users (used by manual send button)."""
    channel_ok = _broadcast_to_global(message)
    users_sent = 0
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
        result = _broadcast_to_user(message, user, db)
        if result["personal"]:
            users_sent += 1
    log.info(f"[signal] Legacy broadcast — channel: {channel_ok}, users: {users_sent}/{len(users)}")
    return {"channel": channel_ok, "users_sent": users_sent, "users_total": len(users)}


# ─── Cooldown check ───────────────────────────────────────────────────────────

def _cooldown_ok(db, symbol: str, exchange: str, timeframe: str,
                 signal: str, hours: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    existing = (
        db.query(Signal)
        .filter(
            Signal.symbol    == symbol.upper(),
            Signal.exchange  == exchange,
            Signal.timeframe == timeframe,
            Signal.signal    == signal,
            Signal.created_at >= cutoff,
        )
        .first()
    )
    return existing is None


# ─── DB helper ────────────────────────────────────────────────────────────────

def _save_signal(db, result: dict) -> Signal:
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
            "score_breakdown":  result.get("score_breakdown", {}),
            "details":          result.get("details", {}),
            "telegram_message": result.get("telegram_message", ""),
        }),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ─── Build per-symbol user map ────────────────────────────────────────────────

def _build_symbol_user_map(db) -> dict:
    """Returns {(symbol, exchange): [User, ...]} for all active watchlist entries."""
    symbol_map: dict = defaultdict(list)

    rows: List[UserWatchlist] = (
        db.query(UserWatchlist)
        .join(User, User.id == UserWatchlist.user_id)
        .filter(User.is_active == True)
        .all()
    )

    if rows:
        user_cache = {}
        for row in rows:
            if row.user_id not in user_cache:
                user_cache[row.user_id] = db.query(User).filter(User.id == row.user_id).first()
            user = user_cache[row.user_id]
            if not user:
                continue
            has_personal = bool(user.telegram_chat_id)
            has_groups = db.query(UserTelegramGroup).filter(
                UserTelegramGroup.user_id == user.id,
                UserTelegramGroup.is_active == True,
            ).count() > 0
            if has_personal or has_groups:
                key = (row.symbol.upper(), row.exchange.lower())
                if user not in symbol_map[key]:
                    symbol_map[key].append(user)
        log.info(f"[signal] Watchlist mode: {len(symbol_map)} unique symbols")
    else:
        # Fallback to global SIGNAL_SYMBOLS
        log.info("[signal] No watchlists — using global SIGNAL_SYMBOLS")
        symbols = [s.strip().upper() for s in settings.SIGNAL_SYMBOLS.split(",") if s.strip()]
        exchange = settings.SIGNAL_EXCHANGE
        users: List[User] = (
            db.query(User)
            .filter(User.is_active == True, User.telegram_chat_id != None, User.telegram_chat_id != "")
            .all()
        )
        for sym in symbols:
            symbol_map[(sym, exchange)] = list(users)

    return dict(symbol_map)


# ─── Main Celery task ─────────────────────────────────────────────────────────

@celery_app.task(name="app.workers.signal_worker.run_signal_scan")
def run_signal_scan():
    """Scan all watched symbols and send signals to relevant users + their groups."""
    timeframe = settings.SIGNAL_TIMEFRAME
    cooldown  = settings.SIGNAL_COOLDOWN_HOURS

    db = SessionLocal()
    try:
        symbol_map = _build_symbol_user_map(db)
    finally:
        db.close()

    if not symbol_map:
        log.info("[signal] No symbols to scan")
        return "scanned 0"

    results = []

    for (symbol, exchange), users in symbol_map.items():
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
            _save_signal(db, result)

            if signal != NEUTRAL and _cooldown_ok(db, symbol, exchange, timeframe, signal, cooldown):
                message = result["telegram_message"]
                _broadcast_to_global(message)

                total_personal = 0
                total_groups   = 0
                for user in users:
                    stats = _broadcast_to_user(message, user, db)
                    if stats["personal"]:
                        total_personal += 1
                    total_groups += stats["groups_sent"]

                log.info(
                    f"[signal] {symbol} {signal} broadcast — "
                    f"personal: {total_personal}/{len(users)}, groups: {total_groups}"
                )
            elif signal != NEUTRAL:
                log.info(f"[signal] {symbol} {signal} — cooldown active, skipping")

            results.append(f"{symbol}:{signal}")

        except Exception as e:
            log.error(f"[signal] DB/broadcast error for {symbol}: {e}")
            db.rollback()
        finally:
            db.close()

    return f"scanned {len(symbol_map)}: {', '.join(results)}"
