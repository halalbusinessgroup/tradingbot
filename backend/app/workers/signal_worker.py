"""Celery task: periodic TA signal scanning.

Runs every SIGNAL_INTERVAL_MINUTES minutes (default: 30).
For each configured symbol, runs the signal engine, stores result in DB,
and sends a Telegram notification if a non-neutral signal is found and
the cooldown period has elapsed.
"""
import json
import logging
from datetime import datetime, timezone, timedelta

from app.workers.celery_app import celery_app
from app.database import SessionLocal
from app.models.signal import Signal
from app.config import settings
from app.services.signal_engine import analyze_symbol, NEUTRAL

log = logging.getLogger(__name__)


def _send_telegram(message: str, chat_id: str) -> None:
    """Send a Telegram message. Errors are caught so the bot doesn't stop."""
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        log.debug("[signal] Telegram not configured — skipping notification")
        return
    try:
        import httpx
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        httpx.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        log.error(f"[signal] Telegram send error: {e}")


def _cooldown_ok(db, symbol: str, exchange: str, timeframe: str,
                 signal: str, hours: int) -> bool:
    """Return True if the same signal for this symbol hasn't fired within `hours`."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    existing = (
        db.query(Signal)
        .filter(
            Signal.symbol == symbol.upper(),
            Signal.exchange == exchange,
            Signal.timeframe == timeframe,
            Signal.signal == signal,
            Signal.created_at >= cutoff,
        )
        .first()
    )
    return existing is None


def _save_signal(db, result: dict) -> Signal:
    """Persist signal to DB and return the model instance."""
    risk   = result.get("risk", {})
    levels = result.get("levels", {})
    row = Signal(
        symbol     = result["symbol"],
        exchange   = result["exchange"],
        timeframe  = result["timeframe"],
        signal     = result["signal"],
        score      = result["score"],
        price      = result["price"],
        atr        = result.get("atr"),
        sl         = risk.get("sl"),
        tp1        = risk.get("tp1"),
        tp2        = risk.get("tp2"),
        rr_ratio   = risk.get("rr"),
        support    = levels.get("support"),
        resistance = levels.get("resistance"),
        details_json = json.dumps({
            "score_breakdown": result.get("score_breakdown", {}),
            "details":         result.get("details", {}),
            "telegram_message": result.get("telegram_message", ""),
        }),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@celery_app.task(name="app.workers.signal_worker.run_signal_scan")
def run_signal_scan():
    """Scan all configured symbols and generate TA signals."""
    symbols   = [s.strip().upper() for s in settings.SIGNAL_SYMBOLS.split(",") if s.strip()]
    exchange  = settings.SIGNAL_EXCHANGE
    timeframe = settings.SIGNAL_TIMEFRAME
    cooldown  = settings.SIGNAL_COOLDOWN_HOURS
    chat_id   = settings.SIGNAL_TELEGRAM_CHAT_ID

    results = []
    for symbol in symbols:
        try:
            result = analyze_symbol(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                risk_multiplier=settings.SIGNAL_RISK_MULT,
                tp1_multiplier=settings.SIGNAL_TP1_MULT,
                tp2_multiplier=settings.SIGNAL_TP2_MULT,
                threshold_strong=settings.SIGNAL_THRESHOLD_STRONG,
                threshold_weak=settings.SIGNAL_THRESHOLD_WEAK,
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
            # Always store (for history / dashboard)
            _save_signal(db, result)

            # Send Telegram only for actionable signals within cooldown
            if signal != NEUTRAL:
                if _cooldown_ok(db, symbol, exchange, timeframe, signal, cooldown):
                    _send_telegram(result["telegram_message"], chat_id)
                    log.info(f"[signal] Telegram sent for {symbol} {signal}")
                else:
                    log.info(f"[signal] {symbol} {signal} — cooldown active, skipping Telegram")

            results.append(f"{symbol}:{signal}")
        except Exception as e:
            log.error(f"[signal] DB/Telegram error for {symbol}: {e}")
            db.rollback()
        finally:
            db.close()

    return f"scanned {len(symbols)}: {', '.join(results)}"
