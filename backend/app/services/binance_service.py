"""Binance Spot service: thin wrapper around python-binance."""
from typing import List, Dict, Optional
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT
from app.config import settings


class BinanceService:
    def __init__(self, api_key: str, api_secret: str):
        self.client = Client(api_key, api_secret, testnet=settings.BINANCE_TESTNET)

    # ---------- Account ----------
    def account_info(self) -> dict:
        return self.client.get_account()

    def api_key_permissions(self) -> dict:
        """Returns the actual permissions of THIS API key (not the account)."""
        return self.client.get_account_api_permissions()

    def usdt_balances(self) -> dict:
        info = self.client.get_account()
        balances = {}
        for b in info["balances"]:
            free = float(b["free"])
            locked = float(b["locked"])
            if free + locked > 0:
                balances[b["asset"]] = {"free": free, "locked": locked}
        return balances

    # ---------- Market ----------
    def get_price(self, symbol: str) -> float:
        return float(self.client.get_symbol_ticker(symbol=symbol)["price"])

    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> List[List]:
        return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)

    def get_symbol_info(self, symbol: str) -> dict:
        return self.client.get_symbol_info(symbol)

    def _round_qty(self, symbol: str, qty: float) -> float:
        info = self.get_symbol_info(symbol)
        step = 0.000001
        for f in info["filters"]:
            if f["filterType"] == "LOT_SIZE":
                step = float(f["stepSize"])
        # truncate to step
        precision = max(0, str(step).rstrip("0")[::-1].find(".") )
        from math import floor
        return floor(qty / step) * step

    def _round_price(self, symbol: str, price: float) -> float:
        info = self.get_symbol_info(symbol)
        tick = 0.01
        for f in info["filters"]:
            if f["filterType"] == "PRICE_FILTER":
                tick = float(f["tickSize"])
        from math import floor
        return floor(price / tick) * tick

    # ---------- Orders ----------
    def market_buy_quote(self, symbol: str, quote_amount_usdt: float) -> dict:
        """Buy `symbol` worth `quote_amount_usdt` USDT using a market order."""
        return self.client.create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quoteOrderQty=round(quote_amount_usdt, 2),
        )

    def place_oco_sell(self, symbol: str, qty: float, tp_price: float, sl_price: float) -> dict:
        """Place OCO (One-Cancels-Other) to manage TP+SL after a buy."""
        qty_r = self._round_qty(symbol, qty)
        tp_r = self._round_price(symbol, tp_price)
        sl_r = self._round_price(symbol, sl_price)
        # stop limit slightly below stop trigger to ensure execution
        stop_limit = self._round_price(symbol, sl_price * 0.998)
        return self.client.create_oco_order(
            symbol=symbol,
            side=SIDE_SELL,
            quantity=qty_r,
            price=str(tp_r),
            stopPrice=str(sl_r),
            stopLimitPrice=str(stop_limit),
            stopLimitTimeInForce="GTC",
        )

    def market_sell(self, symbol: str, qty: float) -> dict:
        return self.client.create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=self._round_qty(symbol, qty),
        )

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        return self.client.cancel_order(symbol=symbol, orderId=order_id)

    def get_order(self, symbol: str, order_id: int) -> dict:
        return self.client.get_order(symbol=symbol, orderId=order_id)
