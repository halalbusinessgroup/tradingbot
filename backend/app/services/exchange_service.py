"""Unified exchange service supporting Binance and Bybit via ccxt."""
import ccxt
import logging
from typing import List
from app.config import settings

log = logging.getLogger(__name__)


def to_ccxt_symbol(symbol: str) -> str:
    """Convert 'BTCUSDT' → 'BTC/USDT'"""
    for quote in ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB', 'TRY', 'EUR']:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            base = symbol[:-len(quote)]
            return f"{base}/{quote}"
    return symbol


def from_ccxt_symbol(symbol: str) -> str:
    """Convert 'BTC/USDT' → 'BTCUSDT'"""
    return symbol.replace('/', '')


def make_public_client(exchange: str):
    """Create a public (no API key) ccxt client for market data — bypasses IP restrictions."""
    opts = {"enableRateLimit": True}
    if exchange == "binance":
        return ccxt.binance(opts)
    elif exchange == "bybit":
        opts["options"] = {"defaultType": "spot"}
        return ccxt.bybit(opts)
    raise ValueError(f"Unsupported exchange: {exchange}")


class ExchangeService:
    def __init__(self, exchange: str, api_key: str, api_secret: str):
        self.exchange_name = exchange.lower()
        opts = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        }

        if self.exchange_name == "binance":
            # recvWindow: gives Binance 10s tolerance for clock skew (Docker clocks can drift)
            opts["options"] = {
                "recvWindow": 10000,
                "adjustForTimeDifference": True,
            }
            self.client = ccxt.binance(opts)
            if settings.BINANCE_TESTNET:
                self.client.set_sandbox_mode(True)
                log.info("Binance: TESTNET mode ⚠️")
            else:
                log.info("Binance: LIVE mode ✅")

        elif self.exchange_name == "bybit":
            opts["options"] = {"defaultType": "spot"}
            self.client = ccxt.bybit(opts)
            if settings.BYBIT_TESTNET:
                self.client.set_sandbox_mode(True)
                log.info("Bybit: TESTNET mode")
            else:
                log.info("Bybit: LIVE mode")
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    # ─── Account ────────────────────────────────────────────────────
    def fetch_balance(self) -> dict:
        bal = self.client.fetch_balance()
        result = {}
        for asset, total in bal["total"].items():
            if total and total > 0:
                free = bal["free"].get(asset) or 0
                result[asset] = {"free": round(free, 8), "locked": round(total - free, 8)}
        return result

    def validate_key(self) -> bool:
        self.fetch_balance()
        return True

    def check_withdrawal_enabled(self) -> bool:
        if self.exchange_name == "binance":
            try:
                perms = self.client.sapi_get_account_apirestrictions()
                return bool(perms.get("enableWithdrawals", False))
            except Exception as e:
                log.warning(f"Withdrawal check failed (skipping): {e}")
                return False
        return False

    # ─── Market data ────────────────────────────────────────────────
    def get_price(self, symbol: str) -> float:
        ticker = self.client.fetch_ticker(to_ccxt_symbol(symbol))
        return float(ticker["last"])

    def get_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 200) -> List[list]:
        return self.client.fetch_ohlcv(to_ccxt_symbol(symbol), timeframe=timeframe, limit=limit)

    def fetch_usdt_tickers(self) -> dict:
        try:
            pub = make_public_client(self.exchange_name)
            all_tickers = pub.fetch_tickers()
            result = {}
            for sym, t in all_tickers.items():
                if not sym.endswith("/USDT"):
                    continue
                raw_symbol = from_ccxt_symbol(sym)
                result[raw_symbol] = {
                    "price": float(t.get("last") or 0),
                    "change24h": round(float(t.get("percentage") or 0), 2),
                    "volume24h": round(float(t.get("quoteVolume") or 0), 0),
                    "high24h": float(t.get("high") or 0),
                    "low24h": float(t.get("low") or 0),
                }
            return result
        except Exception as e:
            log.error(f"fetch_usdt_tickers error: {e}")
            return {}

    # ─── Orders ─────────────────────────────────────────────────────
    def market_buy_quote(self, symbol: str, quote_amount: float) -> dict:
        """
        Buy `symbol` for `quote_amount` USDT via market order.
        Returns: {"order_id": str, "qty": float, "entry_price": float}
        qty is already net of trading fee (safe to use for TP/SL).
        """
        ccxt_sym = to_ccxt_symbol(symbol)
        self._ensure_markets()

        # Estimate price for qty calculation fallback
        price_estimate = self.get_price(symbol)
        raw_qty = quote_amount / price_estimate

        log.info(f"market_buy_quote: {symbol} quote={quote_amount} USDT, ~price={price_estimate:.6f}")

        # ── Place the market buy ─────────────────────────────────────────
        if self.exchange_name == "binance":
            # quoteOrderQty: buy exactly `quote_amount` USDT worth — most reliable on Binance
            order = self.client.create_order(
                ccxt_sym, "market", "buy", None,
                params={"quoteOrderQty": round(quote_amount, 2)}
            )
        else:
            # Bybit: use base quantity
            qty = self._safe_amount(ccxt_sym, raw_qty)
            if qty <= 0:
                raise ValueError(
                    f"Qty rounded to 0 for {symbol} (raw={raw_qty:.8f}). "
                    f"Increase amount_usdt or check minimum lot size."
                )
            order = self.client.create_order(ccxt_sym, "market", "buy", qty)

        # ── Parse filled quantity ────────────────────────────────────────
        filled_qty = float(order.get("filled") or 0)
        avg_price = float(order.get("average") or 0)

        # If ccxt didn't populate filled, try raw Binance info
        if filled_qty <= 0:
            info = order.get("info", {})
            filled_qty = float(info.get("executedQty") or info.get("origQty") or raw_qty)

        if avg_price <= 0:
            info = order.get("info", {})
            # Binance returns cummulativeQuoteQty / executedQty
            cum_quote = float(info.get("cummulativeQuoteQty") or 0)
            if cum_quote > 0 and filled_qty > 0:
                avg_price = cum_quote / filled_qty
            else:
                avg_price = price_estimate

        log.info(f"Raw fill: {symbol} filled={filled_qty:.8f} @ avg={avg_price:.6f}")

        # ── Calculate NET qty after trading fee ──────────────────────────
        # Binance deducts 0.1% fee from the received base asset (unless BNB Pay is on).
        # We MUST use net qty for TP/SL, otherwise Binance returns "insufficient balance".
        # Most accurate: parse fills[] from order response.
        if self.exchange_name == "binance":
            info = order.get("info", {})
            fills = info.get("fills", [])
            if fills:
                ccxt_base = ccxt_sym.split("/")[0]  # e.g. "SOL" from "SOL/USDT"
                net_from_fills = 0.0
                for f in fills:
                    fill_qty = float(f.get("qty", 0))
                    commission = float(f.get("commission", 0))
                    commission_asset = f.get("commissionAsset", "")
                    if commission_asset == ccxt_base:
                        # Fee taken from base → subtract commission
                        net_from_fills += fill_qty - commission
                    else:
                        # Fee in BNB or USDT → full qty received
                        net_from_fills += fill_qty
                if net_from_fills > 0:
                    net_qty = net_from_fills
                    log.info(f"Net qty from fills[]: {net_qty:.8f}")
                else:
                    net_qty = filled_qty * 0.999  # conservative fallback
            else:
                # No fills in response — apply conservative 0.1% deduction
                net_qty = filled_qty * 0.999
        else:
            # Bybit: fee usually in USDT, not base asset
            net_qty = filled_qty * 0.999

        log.info(f"BUY COMPLETE: {symbol} net_qty={net_qty:.8f} @ {avg_price:.6f} | order_id={order['id']}")
        return {"order_id": str(order["id"]), "qty": net_qty, "entry_price": avg_price}

    def place_tp_sl(self, symbol: str, qty: float, tp_price: float, sl_price: float) -> dict:
        """
        Place Take-Profit and Stop-Loss orders.

        Binance: uses OCO (One-Cancels-Other) — atomic, Binance manages cancellation.
                 Falls back to separate limit orders if OCO is unsupported (e.g. testnet).
        Bybit:   separate TP limit + SL limit orders.

        Returns: {"tp_order_id": str|None, "sl_order_id": str|None, "errors": [str]}
        Errors are NOT swallowed — caller must check errors[] and log them to DB.
        """
        self._ensure_markets()
        ccxt_sym = to_ccxt_symbol(symbol)

        qty_r = self._safe_amount(ccxt_sym, qty)
        tp_r = self._safe_price(ccxt_sym, tp_price)
        sl_r = self._safe_price(ccxt_sym, sl_price)
        # Limit price for SL order = 0.5% below stop trigger (ensures fill even on fast moves)
        sl_limit = self._safe_price(ccxt_sym, sl_price * 0.995)

        log.info(
            f"place_tp_sl: {symbol} qty={qty_r} "
            f"TP={tp_r} SL_stop={sl_r} SL_limit={sl_limit}"
        )

        if qty_r <= 0:
            return {
                "tp_order_id": None, "sl_order_id": None,
                "errors": [f"qty rounded to 0 for {symbol} — cannot place TP/SL"]
            }

        tp_id = sl_id = None
        errors: list[str] = []

        # ────────────────────────────────────────────────────────────────
        # BINANCE: OCO (One-Cancels-Other)
        # A single API call that places both TP limit sell AND SL stop-limit.
        # When one fills, Binance automatically cancels the other.
        # This is the correct and most reliable approach for Binance spot.
        # ────────────────────────────────────────────────────────────────
        if self.exchange_name == "binance":
            try:
                # Binance wants precision-formatted strings
                qty_str = self.client.amount_to_precision(ccxt_sym, qty_r)
                tp_str = self.client.price_to_precision(ccxt_sym, tp_r)
                sl_str = self.client.price_to_precision(ccxt_sym, sl_r)
                sl_lim_str = self.client.price_to_precision(ccxt_sym, sl_limit)

                resp = self.client.private_post_order_oco({
                    "symbol": symbol.upper(),   # Binance wants raw format e.g. "SOLUSDT"
                    "side": "SELL",
                    "quantity": qty_str,
                    "price": tp_str,            # Limit sell price (TP)
                    "stopPrice": sl_str,        # Trigger price (SL)
                    "stopLimitPrice": sl_lim_str,   # Limit price after SL triggers
                    "stopLimitTimeInForce": "GTC",
                })

                # Parse the two order IDs from the OCO response
                order_reports = resp.get("orderReports", resp.get("orders", []))
                for o in order_reports:
                    o_type = o.get("type", "")
                    o_id = str(o.get("orderId", ""))
                    if "STOP" in o_type.upper():
                        sl_id = o_id
                    else:
                        tp_id = o_id

                oco_list_id = resp.get("orderListId", "?")
                log.info(
                    f"✅ OCO placed {symbol}: listId={oco_list_id} "
                    f"TP_id={tp_id} SL_id={sl_id}"
                )

            except Exception as e:
                oco_err = f"OCO xəta {symbol} (qty={qty_r} TP={tp_r} SL={sl_r}): {e}"
                log.error(oco_err)
                errors.append(f"OCO FAILED: {oco_err}")

                # ── OCO Fallback: try separate limit orders ──────────────
                log.warning(f"Falling back to separate TP/SL orders for {symbol}")

                try:
                    tp_order = self.client.create_order(
                        ccxt_sym, "limit", "sell", qty_r, tp_r,
                        {"timeInForce": "GTC"}
                    )
                    tp_id = str(tp_order["id"])
                    log.info(f"TP (separate) placed {symbol}: id={tp_id} @ {tp_r}")
                except Exception as e2:
                    err = f"TP order FAILED {symbol} (qty={qty_r} @ {tp_r}): {e2}"
                    log.error(err)
                    errors.append(err)

                try:
                    sl_order = self.client.create_order(
                        ccxt_sym, "stop_loss_limit", "sell", qty_r, sl_limit,
                        {"stopPrice": sl_r, "timeInForce": "GTC"}
                    )
                    sl_id = str(sl_order["id"])
                    log.info(f"SL (separate) placed {symbol}: id={sl_id} @ stop={sl_r}")
                except Exception as e2:
                    err = f"SL order FAILED {symbol} (qty={qty_r} stop={sl_r} lim={sl_limit}): {e2}"
                    log.error(err)
                    errors.append(err)

        # ────────────────────────────────────────────────────────────────
        # BYBIT: Separate TP limit + SL stop-limit orders
        # ────────────────────────────────────────────────────────────────
        else:
            try:
                tp_order = self.client.create_order(
                    ccxt_sym, "limit", "sell", qty_r, tp_r,
                    {"timeInForce": "GTC"}
                )
                tp_id = str(tp_order["id"])
                log.info(f"TP placed {symbol}: id={tp_id} @ {tp_r}")
            except Exception as e:
                err = f"TP order FAILED {symbol} (qty={qty_r} @ {tp_r}): {e}"
                log.error(err)
                errors.append(err)

            try:
                # Bybit spot: try stop-limit, fall back to plain limit below SL price
                try:
                    sl_order = self.client.create_order(
                        ccxt_sym, "limit", "sell", qty_r, sl_limit,
                        {
                            "stopPrice": sl_r,
                            "triggerPrice": sl_r,
                            "timeInForce": "GTC",
                        }
                    )
                except Exception:
                    # Plain limit at SL price as last resort
                    sl_order = self.client.create_order(
                        ccxt_sym, "limit", "sell", qty_r, sl_limit,
                        {"timeInForce": "GTC"}
                    )
                sl_id = str(sl_order["id"])
                log.info(f"SL placed {symbol}: id={sl_id} @ {sl_r}")
            except Exception as e:
                err = f"SL order FAILED {symbol} (qty={qty_r} stop={sl_r}): {e}"
                log.error(err)
                errors.append(err)

        return {"tp_order_id": tp_id, "sl_order_id": sl_id, "errors": errors}

    def get_order(self, symbol: str, order_id: str) -> dict:
        return self.client.fetch_order(order_id, to_ccxt_symbol(symbol))

    def cancel_order(self, symbol: str, order_id: str):
        try:
            return self.client.cancel_order(order_id, to_ccxt_symbol(symbol))
        except Exception as e:
            log.warning(f"Cancel order {order_id} ({symbol}): {e}")

    def market_sell(self, symbol: str, qty: float) -> dict:
        """Market sell `qty` of `symbol`. Used for manual close / fallback close."""
        self._ensure_markets()
        ccxt_sym = to_ccxt_symbol(symbol)
        qty_r = self._safe_amount(ccxt_sym, qty)
        log.info(f"market_sell: {symbol} qty={qty_r}")
        return self.client.create_order(ccxt_sym, "market", "sell", qty_r)

    def cancel_all_orders(self, symbol: str) -> list:
        """Cancel all open orders for a symbol. Returns list of cancelled order IDs."""
        cancelled = []
        try:
            open_orders = self.client.fetch_open_orders(to_ccxt_symbol(symbol))
            for o in open_orders:
                try:
                    self.client.cancel_order(o["id"], to_ccxt_symbol(symbol))
                    cancelled.append(str(o["id"]))
                except Exception as e:
                    log.warning(f"cancel_all_orders: could not cancel {o['id']}: {e}")
        except Exception as e:
            log.warning(f"cancel_all_orders fetch error {symbol}: {e}")
        return cancelled

    # ─── Helpers ────────────────────────────────────────────────────
    def _ensure_markets(self):
        if not getattr(self.client, 'markets', None):
            self.client.load_markets()

    def _safe_amount(self, ccxt_symbol: str, qty: float) -> float:
        """Round quantity to exchange step size. Never returns 0."""
        try:
            self._ensure_markets()
            result = float(self.client.amount_to_precision(ccxt_symbol, qty))
            if result <= 0:
                result = round(qty, 6)
            return result
        except Exception:
            return round(qty, 6)

    def _safe_price(self, ccxt_symbol: str, price: float) -> float:
        """Round price to exchange tick size."""
        try:
            self._ensure_markets()
            return float(self.client.price_to_precision(ccxt_symbol, price))
        except Exception:
            return round(price, 6)
