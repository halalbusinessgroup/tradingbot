"""TA Signal API endpoints."""
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.signal import Signal
from app.config import settings
from app.services.signal_engine import analyze_symbol

router = APIRouter(prefix="/api/signals", tags=["signals"])


# ─── Response schemas ─────────────────────────────────────────────────────────

class SignalOut(BaseModel):
    id: int
    symbol: str
    exchange: str
    timeframe: str
    signal: str
    score: float
    price: float
    atr: Optional[float]
    sl: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    rr_ratio: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    details: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


def _enrich(row: Signal) -> dict:
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    try:
        blob = json.loads(row.details_json or "{}")
        d["details"] = blob.get("details", {})
        d["score_breakdown"] = blob.get("score_breakdown", {})
        d["telegram_message"] = blob.get("telegram_message", "")
    except Exception:
        d["details"] = {}
        d["score_breakdown"] = {}
        d["telegram_message"] = ""
    return d


# ─── GET /api/signals/latest ──────────────────────────────────────────────────

@router.get("/latest")
def get_latest_signals(
    limit: int = Query(20, ge=1, le=100),
    symbol: Optional[str] = Query(None),
    signal_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Latest signals (newest first). Optionally filter by symbol or signal type."""
    q = db.query(Signal).order_by(Signal.created_at.desc())
    if symbol:
        q = q.filter(Signal.symbol == symbol.upper())
    if signal_type:
        q = q.filter(Signal.signal == signal_type.upper())
    rows = q.limit(limit).all()
    return [_enrich(r) for r in rows]


# ─── GET /api/signals/stats ───────────────────────────────────────────────────

@router.get("/stats")
def get_signal_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Signal distribution stats over the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(Signal).filter(Signal.created_at >= cutoff).all()

    counts: dict = {}
    by_symbol: dict = {}
    for r in rows:
        counts[r.signal] = counts.get(r.signal, 0) + 1
        if r.symbol not in by_symbol:
            by_symbol[r.symbol] = {}
        by_symbol[r.symbol][r.signal] = by_symbol[r.symbol].get(r.signal, 0) + 1

    return {
        "total": len(rows),
        "days": days,
        "by_signal": counts,
        "by_symbol": by_symbol,
    }


# ─── POST /api/signals/analyze ───────────────────────────────────────────────

class AnalyzeNowRequest(BaseModel):
    symbol: str = "BTCUSDT"
    exchange: str = "binance"
    timeframe: str = "1h"


@router.post("/analyze")
def analyze_now(
    req: AnalyzeNowRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a one-shot signal analysis immediately and return + store the result."""
    result = analyze_symbol(
        symbol=req.symbol,
        exchange=req.exchange,
        timeframe=req.timeframe,
        risk_multiplier=settings.SIGNAL_RISK_MULT,
        tp1_multiplier=settings.SIGNAL_TP1_MULT,
        tp2_multiplier=settings.SIGNAL_TP2_MULT,
        threshold_strong=settings.SIGNAL_THRESHOLD_STRONG,
        threshold_weak=settings.SIGNAL_THRESHOLD_WEAK,
    )
    if not result:
        return {"error": f"Could not fetch data for {req.symbol}"}

    # Store in DB
    from app.workers.signal_worker import _save_signal
    row = _save_signal(db, result)
    result["id"] = row.id
    return result


# ─── POST /api/signals/{id}/send-telegram ────────────────────────────────────

@router.post("/{signal_id}/send-telegram")
def send_signal_to_telegram(
    signal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually send a stored signal to Telegram (channel + all linked users)."""
    row = db.query(Signal).filter(Signal.id == signal_id).first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Signal not found")

    try:
        blob = json.loads(row.details_json or "{}")
        message = blob.get("telegram_message", "")
    except Exception:
        message = ""

    if not message:
        # Fallback: build a minimal message
        message = (
            f"📊 <b>{row.signal}</b> — {row.symbol}\n"
            f"Score: {row.score:+.1f} | Price: {row.price}\n"
            f"SL: {row.sl} | TP1: {row.tp1} | TP2: {row.tp2}"
        )

    from app.workers.signal_worker import _broadcast
    stats = _broadcast(message, db)
    return {"ok": True, "channel": stats["channel"], "users_sent": stats["users_sent"], "users_total": stats["users_total"]}


# ─── POST /api/signals/test-telegram (deprecated → use /api/telegram/test) ────

@router.post("/test-telegram")
def test_telegram_legacy(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Deprecated: redirects to new /api/telegram/test logic."""
    from app.api.telegram_config import test_telegram as _test
    return _test(db=db, user=user)


# ─── GET /api/signals/config ──────────────────────────────────────────────────

@router.get("/config")
def get_signal_config(user: User = Depends(get_current_user)):
    """Return current signal engine configuration."""
    return {
        "symbols":          [s.strip() for s in settings.SIGNAL_SYMBOLS.split(",")],
        "exchange":         settings.SIGNAL_EXCHANGE,
        "timeframe":        settings.SIGNAL_TIMEFRAME,
        "interval_minutes": settings.SIGNAL_INTERVAL_MINUTES,
        "cooldown_hours":   settings.SIGNAL_COOLDOWN_HOURS,
        "threshold_strong": settings.SIGNAL_THRESHOLD_STRONG,
        "threshold_weak":   settings.SIGNAL_THRESHOLD_WEAK,
    }
