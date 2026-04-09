"""Backtesting API — simulate a strategy on historical OHLCV data."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.exchange_service import make_public_client, to_ccxt_symbol
from app.services.indicators import evaluate_condition

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class ConditionModel(BaseModel):
    indicator: str
    period: int = 14
    op: str = "<"
    value: float = 30


class BacktestRequest(BaseModel):
    symbol: str = "SOLUSDT"
    exchange: str = "binance"
    timeframe: str = "1h"
    days: int = 30
    tp_percent: float = 3.0
    sl_percent: float = 1.5
    amount_usdt: float = 100.0
    no_conditions: bool = False
    entry_conditions: List[ConditionModel] = []


# Number of candles required as look-back before we start evaluating
LOOKBACK = 200

# Approximate candles per day for common timeframes
TF_CANDLES_PER_DAY = {
    "1m": 1440, "3m": 480, "5m": 288, "15m": 96, "30m": 48,
    "1h": 24, "2h": 12, "4h": 6, "6h": 4, "8h": 3, "12h": 2,
    "1d": 1, "3d": 0.33, "1w": 0.14,
}


@router.post("/run")
def run_backtest(
    payload: BacktestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Run a vectorised backtest on public historical OHLCV data.
    No real orders are placed — this is pure simulation.
    """
    days = max(1, min(payload.days, 365))
    cpd = TF_CANDLES_PER_DAY.get(payload.timeframe, 24)
    needed = int(days * cpd) + LOOKBACK + 10
    limit = min(needed, 1000)  # ccxt max is typically 1000 per call

    # ── Fetch historical OHLCV ───────────────────────────────────────
    try:
        pub = make_public_client(payload.exchange)
        pub.load_markets()
        ohlcv = pub.fetch_ohlcv(
            to_ccxt_symbol(payload.symbol),
            timeframe=payload.timeframe,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(400, f"OHLCV fetch failed: {e}")

    if len(ohlcv) < LOOKBACK + 5:
        raise HTTPException(400, f"Not enough candles ({len(ohlcv)}) for this timeframe/period combination.")

    conditions = [c.model_dump() for c in payload.entry_conditions]

    # ── Simulation ───────────────────────────────────────────────────
    FEE = 0.001  # 0.1% per side
    open_trade = None
    closed_trades = []

    for i in range(LOOKBACK, len(ohlcv)):
        window = ohlcv[:i + 1]
        candle = ohlcv[i]
        ts = candle[0]
        candle_open = float(candle[1])
        candle_high = float(candle[2])
        candle_low = float(candle[3])
        candle_close = float(candle[4])
        date_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

        # ── Check if open trade hits TP or SL on this candle ────────
        if open_trade:
            tp = open_trade["tp_price"]
            sl = open_trade["sl_price"]
            hit_tp = candle_high >= tp
            hit_sl = candle_low <= sl

            if hit_tp or hit_sl:
                if hit_tp and not hit_sl:
                    exit_p, reason = tp, "TP"
                elif hit_sl and not hit_tp:
                    exit_p, reason = sl, "SL"
                else:
                    # Both hit same candle — use which is closer to open price
                    if abs(candle_open - sl) <= abs(candle_open - tp):
                        exit_p, reason = sl, "SL"
                    else:
                        exit_p, reason = tp, "TP"

                gross_pnl = (exit_p - open_trade["entry_price"]) * open_trade["qty"]
                fee = exit_p * open_trade["qty"] * FEE
                net_pnl = gross_pnl - fee

                open_trade.update({
                    "exit_price": round(exit_p, 6),
                    "closed_at": date_str,
                    "pnl": round(net_pnl, 4),
                    "reason": reason,
                })
                closed_trades.append(open_trade)
                open_trade = None
                continue

        # ── Entry check ──────────────────────────────────────────────
        if open_trade is None:
            if payload.no_conditions or not conditions:
                entry = True
            else:
                try:
                    entry = all(evaluate_condition(window, c) for c in conditions)
                except Exception:
                    entry = False

            if entry:
                qty = (payload.amount_usdt / candle_close) * (1 - FEE)
                tp_price = candle_close * (1 + payload.tp_percent / 100)
                sl_price = candle_close * (1 - payload.sl_percent / 100)
                open_trade = {
                    "symbol": payload.symbol,
                    "entry_price": round(candle_close, 6),
                    "qty": round(qty, 8),
                    "tp_price": round(tp_price, 6),
                    "sl_price": round(sl_price, 6),
                    "opened_at": date_str,
                    "exit_price": None,
                    "closed_at": None,
                    "pnl": None,
                    "reason": None,
                }

    # ── Compute stats ────────────────────────────────────────────────
    total_trades = len(closed_trades)
    wins = sum(1 for t in closed_trades if t["reason"] == "TP")
    losses = total_trades - wins
    total_pnl = round(sum(t["pnl"] for t in closed_trades), 4)
    win_rate = round((wins / total_trades) * 100, 1) if total_trades > 0 else 0

    # Max drawdown
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in closed_trades:
        running += t["pnl"]
        peak = max(peak, running)
        dd = peak - running
        max_dd = max(max_dd, dd)

    # Equity curve
    cumulative = 0.0
    equity_curve = []
    for t in closed_trades:
        cumulative += t["pnl"]
        equity_curve.append({
            "date": t["closed_at"],
            "pnl": round(cumulative, 4),
            "symbol": t["symbol"],
            "reason": t["reason"],
        })

    # Best / worst trade
    best = max(closed_trades, key=lambda t: t["pnl"]) if closed_trades else None
    worst = min(closed_trades, key=lambda t: t["pnl"]) if closed_trades else None

    return {
        "symbol": payload.symbol,
        "exchange": payload.exchange,
        "timeframe": payload.timeframe,
        "days": days,
        "candles_analyzed": len(ohlcv) - LOOKBACK,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "max_drawdown": round(max_dd, 4),
        "best_trade_pnl": round(best["pnl"], 4) if best else 0,
        "worst_trade_pnl": round(worst["pnl"], 4) if worst else 0,
        "equity_curve": equity_curve,
        "trades": closed_trades,
    }
