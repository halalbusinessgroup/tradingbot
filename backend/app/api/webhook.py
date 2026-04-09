"""TradingView webhook — receive buy/sell signals and execute trades."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.strategy import Strategy
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.trade import Trade
from app.models.log import Log
from app.schemas.schemas import WebhookSignal
from app.core.security import decrypt_str
from app.services.exchange_service import ExchangeService

log = logging.getLogger("webhook")

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


@router.post("/{token}")
async def tradingview_signal(token: str, payload: WebhookSignal, db: Session = Depends(get_db)):
    """
    TradingView Alert webhook endpoint.
    URL to use in TradingView: https://yourdomain.com/api/webhook/{webhook_token}

    Expected JSON body:
      {"action": "buy", "symbol": "SOLUSDT"}
      {"action": "sell", "symbol": "SOLUSDT"}
      {"action": "buy", "symbol": "SOLUSDT", "amount_usdt": 25}
    """
    # Find strategy by webhook token
    strategy = db.query(Strategy).filter(Strategy.webhook_token == token).first()
    if not strategy:
        raise HTTPException(404, "Webhook token tapılmadı")

    user = db.query(User).filter(User.id == strategy.user_id).first()
    if not user or not user.is_active or not user.is_approved:
        raise HTTPException(403, "İstifadəçi aktiv deyil")

    if not user.can_trade:
        raise HTTPException(403, "Bu istifadəçi üçün trading deaktivdir")

    cfg = strategy.config
    exchange = cfg.get("exchange", "binance")
    symbol = payload.symbol.upper().replace("/", "").replace("-", "")
    amount = payload.amount_usdt or cfg.get("amount_usdt", 10)
    action = payload.action.lower()

    log.info(f"Webhook: strategy={strategy.id} action={action} symbol={symbol} amount={amount}")

    # Get API key
    key = db.query(ApiKey).filter(
        ApiKey.user_id == user.id, ApiKey.exchange == exchange, ApiKey.is_active == True
    ).first()
    if not key:
        raise HTTPException(400, f"{exchange} API key tapılmadı")

    try:
        svc = ExchangeService(exchange, decrypt_str(key.api_key_enc), decrypt_str(key.api_secret_enc))
    except Exception as e:
        raise HTTPException(500, f"Exchange bağlantı xətası: {e}")

    if action == "buy":
        # Check if already have open trade on this symbol
        existing = db.query(Trade).filter(
            Trade.user_id == user.id, Trade.symbol == symbol, Trade.status == "OPEN"
        ).first()
        if existing:
            return {"ok": False, "message": f"{symbol} üçün artıq açıq trade var"}

        tp_pct = float(cfg.get("tp_percent", 3))
        sl_pct = float(cfg.get("sl_percent", 1.5))
        paper_mode = bool(cfg.get("paper_mode", False))

        tp_id = sl_id = None
        try:
            if paper_mode:
                price = svc.get_price(symbol)
                qty = amount / price
                entry = price
            else:
                result = svc.market_buy_quote(symbol, amount)
                qty = result["qty"]
                entry = result["entry_price"]

            tp_price = entry * (1 + tp_pct / 100)
            sl_price = entry * (1 - sl_pct / 100)

            if not paper_mode:
                orders = svc.place_tp_sl(symbol, qty, tp_price, sl_price)
                tp_id = orders.get("tp_order_id")
                sl_id = orders.get("sl_order_id")

            trade = Trade(
                user_id=user.id, strategy_id=strategy.id,
                symbol=symbol, side="BUY", qty=qty,
                entry_price=entry, tp_price=tp_price, sl_price=sl_price,
                tp_order_id=tp_id, sl_order_id=sl_id,
                status="OPEN", paper_trade=paper_mode,
            )
            db.add(trade)
            db.add(Log(user_id=user.id, level="INFO",
                       message=f"📡 Webhook BUY {symbol} qty={qty:.6f} @ {entry:.4f} | Strategy: {strategy.name}"))
            db.commit()

            from app.services import telegram_service as tg
            tg.send_message(user.telegram_chat_id,
                            f"📡 Webhook siqnalı: BUY {symbol}\n@ {entry:.4f}\nTP={tp_price:.4f} SL={sl_price:.4f}")
            return {"ok": True, "action": "buy", "symbol": symbol, "entry": entry, "qty": qty}

        except Exception as e:
            db.add(Log(user_id=user.id, level="ERROR",
                       message=f"Webhook BUY xəta {symbol}: {e}"))
            db.commit()
            raise HTTPException(500, f"Buy xəta: {e}")

    elif action == "sell":
        # Close existing open trade on this symbol
        trade = db.query(Trade).filter(
            Trade.user_id == user.id, Trade.symbol == symbol, Trade.status == "OPEN"
        ).first()
        if not trade:
            return {"ok": False, "message": f"{symbol} üçün açıq trade tapılmadı"}

        try:
            exit_price = None
            if trade.paper_trade:
                exit_price = svc.get_price(symbol)
            else:
                if trade.tp_order_id:
                    svc.cancel_order(symbol, trade.tp_order_id)
                if trade.sl_order_id:
                    svc.cancel_order(symbol, trade.sl_order_id)
                svc.market_sell(symbol, trade.qty)
                exit_price = svc.get_price(symbol)

            from datetime import datetime
            trade.exit_price = exit_price
            trade.status = "CLOSED_MANUAL"
            trade.closed_at = datetime.utcnow()
            trade.pnl = round((exit_price - trade.entry_price) * trade.qty, 6)
            trade.pnl_percent = round(
                ((exit_price - trade.entry_price) / trade.entry_price) * 100, 4
            )
            db.add(Log(user_id=user.id, level="INFO",
                       message=f"📡 Webhook SELL {symbol} @ {exit_price:.4f} | PnL={trade.pnl:+.4f} USDT"))
            db.commit()

            from app.services import telegram_service as tg
            tg.send_message(user.telegram_chat_id,
                            f"📡 Webhook siqnalı: SELL {symbol}\n@ {exit_price:.4f}\nPnL: {trade.pnl:+.4f} USDT")
            return {"ok": True, "action": "sell", "symbol": symbol, "exit": exit_price, "pnl": trade.pnl}

        except Exception as e:
            db.add(Log(user_id=user.id, level="ERROR",
                       message=f"Webhook SELL xəta {symbol}: {e}"))
            db.commit()
            raise HTTPException(500, f"Sell xəta: {e}")

    else:
        raise HTTPException(400, f"Naməlum action: {action}. 'buy' və ya 'sell' istifadə edin.")
