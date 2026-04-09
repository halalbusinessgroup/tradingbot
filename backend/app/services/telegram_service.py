"""Telegram notification service — messages sent in English."""
import asyncio
import logging
from telegram import Bot
from telegram.error import TelegramError
from app.config import settings

log = logging.getLogger(__name__)
_bot: Bot | None = None


def bot() -> Bot | None:
    global _bot
    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    if _bot is None:
        _bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    return _bot


def send_message(chat_id: str | None, text: str) -> bool:
    if not chat_id:
        return False
    b = bot()
    if not b:
        return False
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(b.send_message(chat_id=chat_id, text=text, parse_mode="HTML"))
        loop.close()
        return True
    except TelegramError as e:
        log.error(f"Telegram error: {e}")
        return False


def msg_trade_opened(symbol: str, entry: float, qty: float, tp: float, sl: float) -> str:
    return (
        f"🟢 <b>Trade Opened</b>\n"
        f"Coin: <b>{symbol}</b>\n"
        f"Entry Price: <code>{entry:.6f}</code>\n"
        f"Quantity: <code>{qty}</code>\n"
        f"Take Profit: <code>{tp:.6f}</code> (+{round((tp/entry-1)*100,2)}%)\n"
        f"Stop Loss: <code>{sl:.6f}</code> (-{round((1-sl/entry)*100,2)}%)"
    )


def msg_trade_closed(symbol: str, exit_price: float, pnl: float, pnl_pct: float, reason: str) -> str:
    emoji = "✅" if pnl >= 0 else "🔴"
    label = "Take Profit" if reason == "TP" else "Stop Loss"
    return (
        f"{emoji} <b>Trade Closed — {label}</b>\n"
        f"Coin: <b>{symbol}</b>\n"
        f"Exit Price: <code>{exit_price:.6f}</code>\n"
        f"PnL: <b>{pnl:+.4f} USDT ({pnl_pct:+.2f}%)</b>"
    )


def msg_bot_started() -> str:
    return "▶️ <b>Bot Started</b>\nYour trading bot is now active and monitoring the market."


def msg_bot_stopped() -> str:
    return "⏸ <b>Bot Stopped</b>\nYour trading bot has been paused."


def msg_error(text: str) -> str:
    return f"⚠️ <b>Error</b>\n<code>{text}</code>"
