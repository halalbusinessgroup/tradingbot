"""Strategy API — CRUD + webhook token + marketplace."""
import secrets
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.strategy import Strategy
from app.models.trade import Trade
from app.models.api_key import ApiKey
from app.models.log import Log
from app.schemas.schemas import StrategyIn, StrategyOut
from app.core.deps import get_current_user
from app.core.security import decrypt_str

log = logging.getLogger("strategies")

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=List[StrategyOut])
def list_strategies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Strategy).filter(Strategy.user_id == user.id).order_by(Strategy.id.desc()).all()


@router.post("", response_model=StrategyOut)
def create_strategy(payload: StrategyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.can_trade:
        raise HTTPException(403, "Admin trading icazənizi deaktiv etmişdir")
    cfg = payload.config.model_dump()
    s = Strategy(
        user_id=user.id,
        name=payload.name,
        config=cfg,
        is_active=payload.is_active,
        is_public=payload.is_public,
        public_description=payload.public_description,
        webhook_token=secrets.token_urlsafe(32),  # auto-generate webhook token
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, payload: StrategyIn,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Strategiya tapılmadı")
    s.name = payload.name
    s.config = payload.config.model_dump()
    s.is_active = payload.is_active
    s.is_public = payload.is_public
    s.public_description = payload.public_description
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Strategiya tapılmadı")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/{strategy_id}/deactivate")
def deactivate_strategy_with_convert(
    strategy_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Deactivate strategy AND market-sell all open trades to USDT (auto_convert)."""
    s = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Strategy not found")

    exchange = s.config.get("exchange", "binance")
    open_trades = db.query(Trade).filter(
        Trade.user_id == user.id,
        Trade.strategy_id == strategy_id,
        Trade.status == "OPEN",
    ).all()

    errors = []
    if open_trades:
        # Get API key for exchange
        key_rec = db.query(ApiKey).filter(
            ApiKey.user_id == user.id,
            ApiKey.exchange == exchange,
            ApiKey.is_active == True,
        ).first()

        if key_rec:
            from app.services.exchange_service import ExchangeService
            try:
                svc = ExchangeService(
                    exchange,
                    decrypt_str(key_rec.api_key_enc),
                    decrypt_str(key_rec.api_secret_enc),
                )
                for trade in open_trades:
                    if trade.paper_trade:
                        # Paper trade: just close it at current market price
                        try:
                            from app.services.exchange_service import make_public_client, to_ccxt_symbol
                            pub = make_public_client(exchange)
                            ticker = pub.fetch_ticker(to_ccxt_symbol(trade.symbol))
                            exit_price = float(ticker["last"])
                        except Exception:
                            exit_price = trade.entry_price
                    else:
                        # Real trade: market sell
                        try:
                            result = svc.market_sell(trade.symbol, trade.qty)
                            exit_price = float(
                                result.get("average") or result.get("price") or trade.entry_price
                            )
                            # Cancel outstanding TP/SL orders
                            for oid in [trade.tp_order_id, trade.sl_order_id]:
                                if oid:
                                    try: svc.cancel_order(trade.symbol, oid)
                                    except Exception: pass
                        except Exception as e:
                            errors.append(f"Sell failed {trade.symbol}: {e}")
                            exit_price = trade.entry_price

                    trade.exit_price = exit_price
                    trade.status = "CLOSED_MANUAL"
                    trade.closed_at = datetime.utcnow()
                    trade.pnl = round((exit_price - trade.entry_price) * trade.qty, 6)
                    trade.pnl_percent = round(
                        ((exit_price - trade.entry_price) / trade.entry_price) * 100, 4
                    ) if trade.entry_price else 0
                    db.add(Log(user_id=user.id, level="INFO",
                               message=f"🔄 AutoConvert CLOSED {trade.symbol} @ {exit_price:.4f} | PnL={trade.pnl:+.4f}"))
            except Exception as e:
                log.error(f"deactivate_with_convert error: {e}")
                errors.append(str(e))
        else:
            # No API key — just mark as closed
            for trade in open_trades:
                trade.status = "CLOSED_MANUAL"
                trade.closed_at = datetime.utcnow()
                trade.exit_price = trade.entry_price
                trade.pnl = 0
                trade.pnl_percent = 0

    s.is_active = False
    db.commit()

    return {
        "ok": True,
        "closed_trades": len(open_trades),
        "errors": errors,
    }


@router.post("/{strategy_id}/regenerate-webhook")
def regenerate_webhook(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Generate a new webhook token for a strategy."""
    s = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Strategiya tapılmadı")
    s.webhook_token = secrets.token_urlsafe(32)
    db.commit()
    return {"webhook_token": s.webhook_token}


# ── Marketplace ─────────────────────────────────────────────────────────────

@router.get("/marketplace", response_model=List[dict])
def marketplace(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """List all public strategies (marketplace)."""
    public = db.query(Strategy).filter(Strategy.is_public == True).order_by(Strategy.id.desc()).all()
    result = []
    for s in public:
        is_mine = s.user_id == user.id
        author = db.query(User).filter(User.id == s.user_id).first()
        result.append({
            "id": s.id,
            "name": s.name,
            "description": s.public_description or "",
            "exchange": s.config.get("exchange", "binance"),
            "timeframe": s.config.get("timeframe", "15m"),
            "tp_percent": s.config.get("tp_percent"),
            "sl_percent": s.config.get("sl_percent"),
            "entry_conditions_count": len(s.config.get("entry_conditions", [])),
            "trailing_sl": s.config.get("trailing_sl"),
            "dca_enabled": s.config.get("dca_enabled", False),
            "author": f"{author.first_name or ''} {author.last_name or ''}".strip() or "Anonim",
            "is_mine": is_mine,
            "created_at": s.created_at.isoformat(),
        })
    return result


@router.post("/marketplace/{strategy_id}/copy")
def copy_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Copy a public strategy to the current user's strategies."""
    original = db.query(Strategy).filter(
        Strategy.id == strategy_id, Strategy.is_public == True
    ).first()
    if not original:
        raise HTTPException(404, "Strategiya tapılmadı və ya ictimai deyil")

    copy = Strategy(
        user_id=user.id,
        name=f"{original.name} (kopyası)",
        config=dict(original.config),  # deep copy of JSON
        is_active=False,               # starts inactive
        is_public=False,               # copy is private by default
        webhook_token=secrets.token_urlsafe(32),
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return {"ok": True, "strategy_id": copy.id, "name": copy.name}
