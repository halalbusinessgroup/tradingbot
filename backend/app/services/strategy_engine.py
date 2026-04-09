"""Strategy engine: evaluates strategies and executes trades."""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.strategy import Strategy
from app.models.trade import Trade
from app.models.log import Log
from app.core.security import decrypt_str
from app.services.exchange_service import ExchangeService, to_ccxt_symbol
from app.services.indicators import evaluate_condition
from app.services import telegram_service as tg
from app.services.email_service import send_trade_opened, send_trade_closed, send_bot_error

log = logging.getLogger("strategy_engine")


# ─── DB Logger ──────────────────────────────────────────────────────────────
def _log(db: Session, user_id: int | None, level: str, msg: str):
    try:
        db.add(Log(user_id=user_id, level=level, message=msg))
        db.commit()
    except Exception:
        db.rollback()


# ─── Paper Trading Service ───────────────────────────────────────────────────
class _PaperSvc:
    """Minimal service wrapper for paper trading (uses public client for prices only)."""
    exchange_name: str

    def __init__(self, exchange_name: str, pub_client):
        self.exchange_name = exchange_name
        self.client = pub_client

    def get_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 200):
        return self.client.fetch_ohlcv(to_ccxt_symbol(symbol), timeframe=timeframe, limit=limit)

    def get_price(self, symbol: str) -> float:
        ticker = self.client.fetch_ticker(to_ccxt_symbol(symbol))
        return float(ticker["last"])


# ─── Exchange service factory ───────────────────────────────────────────────
def _make_svc(db: Session, user: User, exchange: str) -> ExchangeService | None:
    key = db.query(ApiKey).filter(
        ApiKey.user_id == user.id,
        ApiKey.exchange == exchange,
        ApiKey.is_active == True,
    ).first()
    if not key:
        return None
    return ExchangeService(
        exchange,
        decrypt_str(key.api_key_enc),
        decrypt_str(key.api_secret_enc),
    )


# ─── Main entry point ────────────────────────────────────────────────────────
def run_user_cycle(db: Session, user: User):
    """One scan cycle for one user — checks all active strategies."""
    if not user.bot_enabled or not user.is_active or not user.is_approved:
        return
    if not user.can_trade:
        return

    strategies = db.query(Strategy).filter(
        Strategy.user_id == user.id, Strategy.is_active == True
    ).all()

    if not strategies:
        return

    for strat in strategies:
        exchange = strat.config.get("exchange", "binance")
        paper_mode = bool(strat.config.get("paper_mode", False))

        if not paper_mode:
            try:
                svc = _make_svc(db, user, exchange)
                if not svc:
                    _log(db, user.id, "WARN",
                         f"Strategy '{strat.name}': {exchange} API key tapılmadı")
                    continue
            except Exception as e:
                _log(db, user.id, "ERROR", f"Exchange init xəta ({exchange}): {e}")
                continue
        else:
            from app.services.exchange_service import make_public_client
            try:
                svc = _PaperSvc(exchange, make_public_client(exchange))
            except Exception as e:
                _log(db, user.id, "ERROR", f"Paper mode public client xəta: {e}")
                continue

        try:
            _evaluate_strategy(db, user, svc, strat, paper_mode)
        except Exception as e:
            log.exception(f"Strategy {strat.id} unhandled error")
            _log(db, user.id, "ERROR", f"Strategy '{strat.name}' xəta: {e}")
            if user.email_notifications:
                send_bot_error(user.email, str(e), f"strategy '{strat.name}'")

    # Check open trades for TP/SL fills, trailing SL, DCA
    _check_open_trades(db, user)


# ─── Strategy evaluation ─────────────────────────────────────────────────────
def _evaluate_strategy(db: Session, user: User, svc, strat: Strategy, paper_mode: bool):
    cfg = strat.config
    open_count = db.query(Trade).filter(
        Trade.user_id == user.id, Trade.status == "OPEN"
    ).count()
    max_trades = int(cfg.get("max_open_trades", 1))

    if open_count >= max_trades:
        return

    timeframe = cfg.get("timeframe", "15m")
    entry_conditions = cfg.get("entry_conditions", [])
    no_conditions = not entry_conditions or bool(cfg.get("no_conditions", False))

    for symbol in cfg.get("symbols", []):
        exists = db.query(Trade).filter(
            Trade.user_id == user.id,
            Trade.symbol == symbol,
            Trade.status == "OPEN",
        ).first()
        if exists:
            continue

        try:
            ohlcv = svc.get_ohlcv(symbol, timeframe=timeframe, limit=200)
        except Exception as e:
            _log(db, user.id, "ERROR", f"OHLCV xəta {symbol}: {e}")
            continue

        if not ohlcv:
            continue

        if no_conditions:
            all_ok = True
        else:
            all_ok = all(evaluate_condition(ohlcv, c) for c in entry_conditions)

        if not all_ok:
            continue

        log.info(f"✅ Giriş şərtləri ödəndi: {symbol} — alış icra edilir")
        _execute_buy(db, user, svc, strat, symbol, cfg, paper_mode)
        open_count += 1
        if open_count >= max_trades:
            break


# ─── Buy execution ───────────────────────────────────────────────────────────
def _execute_buy(
    db: Session, user: User, svc, strat: Strategy,
    symbol: str, cfg: dict, paper_mode: bool
):
    amount = float(cfg["amount_usdt"])
    tp_pct = float(cfg["tp_percent"])
    sl_pct = float(cfg["sl_percent"])
    trailing_sl_pct = cfg.get("trailing_sl")

    qty = entry = order_id = None

    try:
        if paper_mode:
            price = svc.get_price(symbol)
            qty = amount / price
            entry = price
            _log(db, user.id, "INFO",
                 f"📄 PAPER BUY {symbol} qty={qty:.6f} @ {entry:.4f}")
        else:
            result = svc.market_buy_quote(symbol, amount)
            qty = result["qty"]
            entry = result["entry_price"]
            order_id = result.get("order_id")
            _log(db, user.id, "INFO",
                 f"✅ BUY {symbol} qty={qty:.6f} @ {entry:.4f} | order_id={order_id}")
    except Exception as e:
        _log(db, user.id, "ERROR", f"BUY xəta {symbol}: {e}")
        tg.send_message(user.telegram_chat_id, tg.msg_error(f"BUY xəta {symbol}: {e}"))
        if user.email_notifications:
            send_bot_error(user.email, f"BUY xəta {symbol}: {e}", symbol)
        return

    tp_price = entry * (1 + tp_pct / 100)
    sl_price = entry * (1 - sl_pct / 100)

    tp_id = sl_id = None
    if not paper_mode:
        try:
            orders = svc.place_tp_sl(symbol, qty, tp_price, sl_price)
            tp_id = orders.get("tp_order_id")
            sl_id = orders.get("sl_order_id")

            # Write every error to bot logs — user sees them immediately
            for err_msg in orders.get("errors", []):
                _log(db, user.id, "ERROR", f"⚠️ {err_msg}")

            if tp_id:
                _log(db, user.id, "INFO",
                     f"📌 TP {symbol}: id={tp_id} @ {tp_price:.4f}")
            if sl_id:
                _log(db, user.id, "INFO",
                     f"🛡 SL {symbol}: id={sl_id} @ {sl_price:.4f}")

            if not tp_id and not sl_id:
                _log(db, user.id, "ERROR",
                     f"⛔ TP VƏ SL HƏR İKİSİ UĞURSUZ OLDU {symbol}! "
                     f"Binance API key-inin Spot Trading icazəsini yoxlayın. "
                     f"Bot qiymət izləməsinə keçəcək (real order olmadan).")
                if user.email_notifications:
                    send_bot_error(
                        user.email,
                        f"TP/SL order-ları qoyula bilmədi {symbol}. "
                        f"Binance API key icazəsini yoxlayın.",
                        symbol
                    )
        except Exception as e:
            _log(db, user.id, "ERROR", f"TP/SL xəta {symbol}: {e}")

    trade = Trade(
        user_id=user.id,
        strategy_id=strat.id,
        symbol=symbol,
        side="BUY",
        qty=qty,
        entry_price=entry,
        tp_price=tp_price,
        sl_price=sl_price,
        trailing_sl=float(trailing_sl_pct) if trailing_sl_pct else None,
        binance_order_id=order_id,
        tp_order_id=tp_id,
        sl_order_id=sl_id,
        status="OPEN",
        paper_trade=paper_mode,
    )
    db.add(trade)
    db.commit()

    tg.send_message(
        user.telegram_chat_id,
        tg.msg_trade_opened(symbol, entry, qty, tp_price, sl_price)
    )
    if user.email_notifications:
        send_trade_opened(user.email, symbol, qty, entry, tp_price, sl_price, paper=paper_mode)


# ─── Open trade monitoring ───────────────────────────────────────────────────
def _check_open_trades(db: Session, user: User):
    """Per-cycle: check TP/SL fills, trailing SL, DCA for all open trades."""
    open_trades = db.query(Trade).filter(
        Trade.user_id == user.id, Trade.status == "OPEN"
    ).all()

    for trade in open_trades:
        exchange = "binance"
        cfg = {}
        if trade.strategy_id:
            strat = db.query(Strategy).filter(Strategy.id == trade.strategy_id).first()
            if strat:
                exchange = strat.config.get("exchange", "binance")
                cfg = strat.config

        if trade.paper_trade:
            from app.services.exchange_service import make_public_client
            try:
                svc = _PaperSvc(exchange, make_public_client(exchange))
            except Exception:
                continue
        else:
            try:
                svc = _make_svc(db, user, exchange)
                if not svc:
                    continue
            except Exception as e:
                log.warning(f"Trade {trade.id} exchange init: {e}")
                continue

        try:
            _check_single_trade(db, user, svc, trade, cfg)
        except Exception as e:
            log.warning(f"Trade {trade.id} check xəta: {e}")


def _check_single_trade(db: Session, user: User, svc, trade: Trade, cfg: dict):
    closed = False

    # ── 1. Check TP/SL order fills (real trades with order IDs) ──────────────
    if not trade.paper_trade:

        if trade.tp_order_id and not closed:
            try:
                tp_order = svc.get_order(trade.symbol, trade.tp_order_id)
                status = tp_order.get("status", "")
                if status == "closed":
                    exit_price = float(
                        tp_order.get("average") or tp_order.get("price") or trade.tp_price
                    )
                    _log(db, user.id, "INFO",
                         f"✅ TP order filled {trade.symbol} @ {exit_price:.4f}")
                    _close_trade(db, user, svc, trade, exit_price, "TP")
                    closed = True
                elif status == "canceled":
                    # OCO: TP was canceled because SL triggered — will be caught below
                    pass
            except Exception as e:
                log.debug(f"TP order check {trade.id}: {e}")

        if trade.sl_order_id and not closed:
            try:
                sl_order = svc.get_order(trade.symbol, trade.sl_order_id)
                status = sl_order.get("status", "")
                if status == "closed":
                    exit_price = float(
                        sl_order.get("average") or sl_order.get("price") or trade.sl_price
                    )
                    _log(db, user.id, "INFO",
                         f"🛡 SL order filled {trade.symbol} @ {exit_price:.4f}")
                    _close_trade(db, user, svc, trade, exit_price, "SL")
                    closed = True
                elif status == "canceled":
                    # OCO: SL was canceled because TP triggered — will be caught above
                    pass
            except Exception as e:
                log.debug(f"SL order check {trade.id}: {e}")

    if closed:
        return

    # ── 2. Get current price for price-based logic ────────────────────────────
    try:
        current = svc.get_price(trade.symbol)
    except Exception:
        return

    # ── 3. Paper trade: close at TP/SL by price ──────────────────────────────
    if trade.paper_trade:
        if current >= trade.tp_price:
            _close_trade(db, user, svc, trade, current, "TP")
            return
        elif current <= trade.sl_price:
            _close_trade(db, user, svc, trade, current, "SL")
            return

    # ── 4. Fallback for real trades with MISSING order IDs ───────────────────
    # This means the TP/SL order placement failed. We do price monitoring AND
    # execute a real market sell when price hits the level.
    if not trade.tp_order_id and not trade.sl_order_id and not trade.paper_trade:
        reason = None
        if current >= trade.tp_price:
            reason = "TP"
        elif current <= trade.sl_price:
            reason = "SL"

        if reason:
            _log(db, user.id, "WARN",
                 f"⚡ Fallback {reason} triggered {trade.symbol} @ {current:.4f} "
                 f"(no exchange orders — executing market sell)")
            try:
                # ACTUALLY SELL on exchange since there's no standing SL/TP order
                sell_result = svc.market_sell(trade.symbol, trade.qty)
                exit_price = float(
                    sell_result.get("average") or
                    sell_result.get("price") or
                    current
                )
                _log(db, user.id, "INFO",
                     f"✅ Fallback market sell {trade.symbol}: {exit_price:.4f}")
            except Exception as e:
                _log(db, user.id, "ERROR",
                     f"❌ Fallback market sell FAILED {trade.symbol}: {e}")
                exit_price = current  # Mark closed at current price in DB anyway
            _close_trade(db, user, svc, trade, exit_price, reason)
            return

    # ── 5. Trailing Stop Loss ─────────────────────────────────────────────────
    if trade.trailing_sl and not closed:
        trailing_pct = float(trade.trailing_sl)
        new_sl = current * (1 - trailing_pct / 100)

        if new_sl > trade.sl_price:
            old_sl = trade.sl_price
            trade.sl_price = new_sl
            _log(db, trade.user_id, "INFO",
                 f"📈 Trailing SL {trade.symbol}: {old_sl:.4f} → {new_sl:.4f} (cur={current:.4f})")

            # Update the SL order on exchange (cancel old, place new)
            if not trade.paper_trade and trade.sl_order_id:
                try:
                    svc.cancel_order(trade.symbol, trade.sl_order_id)
                    ccxt_sym = to_ccxt_symbol(trade.symbol)
                    new_sl_limit = svc._safe_price(ccxt_sym, new_sl * 0.995)
                    new_sl_r = svc._safe_price(ccxt_sym, new_sl)
                    qty_r = svc._safe_amount(ccxt_sym, trade.qty)

                    new_sl_order = svc.client.create_order(
                        ccxt_sym, "stop_loss_limit", "sell", qty_r,
                        new_sl_limit,
                        {"stopPrice": new_sl_r, "timeInForce": "GTC"}
                    )
                    trade.sl_order_id = str(new_sl_order["id"])
                    _log(db, trade.user_id, "INFO",
                         f"🛡 Trailing SL order renewed {trade.symbol}: id={trade.sl_order_id}")
                except Exception as e:
                    log.warning(f"Trailing SL order güncəllənə bilmədi {trade.symbol}: {e}")
            db.commit()

    # ── 6. DCA (Dollar Cost Averaging) ───────────────────────────────────────
    if not closed and cfg.get("dca_enabled") and not trade.paper_trade:
        dca_pct = float(cfg.get("dca_percent", 2.0))
        dca_amount = float(cfg.get("dca_amount", 10.0))
        dca_trigger = trade.entry_price * (1 - dca_pct / 100)

        if current <= dca_trigger:
            # Prevent duplicate DCA for same trade
            existing_dca = db.query(Log).filter(
                Log.user_id == user.id,
                Log.message.contains(f"DCA {trade.symbol}"),
                Log.message.contains(f"trade_id={trade.id}"),
            ).first()
            if not existing_dca:
                try:
                    result = svc.market_buy_quote(trade.symbol, dca_amount)
                    dca_qty = result["qty"]
                    dca_price = result["entry_price"]
                    total_qty = trade.qty + dca_qty
                    avg_entry = (trade.entry_price * trade.qty + dca_price * dca_qty) / total_qty
                    trade.qty = total_qty
                    trade.entry_price = avg_entry
                    trade.tp_price = avg_entry * (1 + float(cfg.get("tp_percent", 3)) / 100)
                    trade.sl_price = avg_entry * (1 - float(cfg.get("sl_percent", 1.5)) / 100)
                    db.commit()
                    _log(db, user.id, "INFO",
                         f"📉 DCA {trade.symbol} trade_id={trade.id}: "
                         f"+{dca_qty:.6f} @ {dca_price:.4f} | avg_entry={avg_entry:.4f}")
                except Exception as e:
                    _log(db, user.id, "ERROR", f"DCA xəta {trade.symbol}: {e}")


# ─── Close trade ─────────────────────────────────────────────────────────────
def _close_trade(
    db: Session, user: User, svc, trade: Trade,
    exit_price: float, reason: str
):
    """
    Mark trade as closed in DB. Also cancels the opposite order if present.
    NOTE: actual market sell is handled by the caller for fallback closes.
    For TP/SL fills, the exchange already executed the sell.
    """
    if not trade.paper_trade:
        try:
            opposite_id = trade.sl_order_id if reason == "TP" else trade.tp_order_id
            if opposite_id:
                svc.cancel_order(trade.symbol, opposite_id)
        except Exception:
            pass  # Cancel errors are non-fatal (OCO may have already cancelled it)

    trade.exit_price = exit_price
    trade.status = f"CLOSED_{reason}"
    trade.closed_at = datetime.utcnow()
    trade.pnl = round((exit_price - trade.entry_price) * trade.qty, 6)
    trade.pnl_percent = round(
        ((exit_price - trade.entry_price) / trade.entry_price) * 100, 4
    )
    db.commit()

    paper_prefix = "📄 " if trade.paper_trade else ""
    _log(db, user.id, "INFO",
         f"{paper_prefix}CLOSED {trade.symbol} [{reason}] @ {exit_price:.4f} | "
         f"PnL={trade.pnl:+.4f} USDT ({trade.pnl_percent:+.2f}%)")

    tg.send_message(
        user.telegram_chat_id,
        tg.msg_trade_closed(trade.symbol, exit_price, trade.pnl, trade.pnl_percent, reason)
    )
    if user.email_notifications:
        send_trade_closed(
            user.email, trade.symbol, exit_price,
            trade.pnl, trade.pnl_percent, reason,
            paper=trade.paper_trade
        )
