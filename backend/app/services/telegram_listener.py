"""Standalone Telegram bot listener — handles /start <token> to link users."""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from app.config import settings
from app.database import SessionLocal
from app.models.user import User

log = logging.getLogger(__name__)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat_id = str(update.effective_chat.id)
    if not args:
        await update.message.reply_text(
            "👋 Salam! Hesabınızı bağlamaq üçün veb-saytda 'Telegram bağla' düyməsinə basıb verilən linki istifadə edin."
        )
        return
    token = args[0]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_link_token == token).first()
        if not user:
            await update.message.reply_text("❌ Token tapılmadı və ya artıq istifadə olunub.")
            return
        user.telegram_chat_id = chat_id
        user.telegram_link_token = None
        db.commit()
        await update.message.reply_text(f"✅ Hesabınız uğurla bağlandı: {user.email}\nİndi botdan bildirişlər alacaqsınız.")
    finally:
        db.close()


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if not user:
            await update.message.reply_text("Hesabınız bağlanmayıb.")
            return
        await update.message.reply_text(
            f"📊 Status\nEmail: {user.email}\nBot: {'AKTİV ✅' if user.bot_enabled else 'DAYANIB ⏸'}"
        )
    finally:
        db.close()


def main():
    if not settings.TELEGRAM_BOT_TOKEN:
        log.warning("No Telegram token; listener disabled.")
        return
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    log.info("Telegram listener started.")
    app.run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
