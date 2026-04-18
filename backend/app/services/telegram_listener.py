"""Standalone Telegram bot listener.

Commands:
  /start <token>     — link personal Telegram to account
  /addgroup <token>  — link this group/channel to the user who generated the token
  /status            — show account status
  /mysymbols         — list current watchlist
"""
import asyncio
import logging
from telegram import Update, Chat
from telegram.ext import Application, CommandHandler, ContextTypes
from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.models.watchlist import UserWatchlist
from app.models.telegram_group import UserTelegramGroup

log = logging.getLogger(__name__)


# ─── /start <token> — personal account link ──────────────────────────────────

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat = update.effective_chat
    chat_id = str(chat.id)

    # Ignore if called in a group (use /addgroup for groups)
    if chat.type in (Chat.GROUP, Chat.SUPERGROUP, Chat.CHANNEL):
        await update.message.reply_text(
            "ℹ️ Qrupda hesab bağlamaq üçün /addgroup <token> istifadə edin."
        )
        return

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
        await update.message.reply_text(
            f"✅ Hesabınız uğurla bağlandı!\n"
            f"📧 {user.email}\n\n"
            f"📊 Siqnallar avtomatik gələcək.\n"
            f"Qrup əlavə etmək üçün saytdakı Ayarlar → Telegram Qrupları bölməsini istifadə edin."
        )
    finally:
        db.close()


# ─── /addgroup <token> — group link ──────────────────────────────────────────

async def addgroup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    chat = update.effective_chat
    chat_id = str(chat.id)
    chat_title = chat.title or chat_id

    if not args:
        await update.message.reply_text(
            "❌ İstifadə: /addgroup <token>\n"
            "Tokeni saytdakı Ayarlar → Telegram Qrupları bölməsindən əldə edin."
        )
        return

    token = args[0]
    db = SessionLocal()
    try:
        # Token format: "grp:<actual_token>"
        full_token = f"grp:{token}"
        user = db.query(User).filter(User.telegram_link_token == full_token).first()
        if not user:
            await update.message.reply_text(
                "❌ Token tapılmadı, artıq istifadə olunub və ya vaxtı keçib.\n"
                "Yeni token üçün sayta qayıdın."
            )
            return

        # Check if already registered
        existing = db.query(UserTelegramGroup).filter(
            UserTelegramGroup.user_id == user.id,
            UserTelegramGroup.chat_id == chat_id,
        ).first()

        if existing:
            existing.is_active = True
            existing.title = chat_title
            db.commit()
            await update.message.reply_text(
                f"✅ Bu qrup artıq hesabınıza bağlıdır: {user.email}\n"
                f"📢 {chat_title} — aktivləşdirildi."
            )
        else:
            grp = UserTelegramGroup(
                user_id   = user.id,
                chat_id   = chat_id,
                title     = chat_title,
                is_active = True,
            )
            db.add(grp)
            user.telegram_link_token = None  # consume token
            db.commit()
            await update.message.reply_text(
                f"✅ Qrup uğurla bağlandı!\n"
                f"👤 Hesab: {user.email}\n"
                f"📢 Qrup: {chat_title}\n\n"
                f"📊 Artıq bu qrupa da siqnallar gələcək."
            )
    finally:
        db.close()


# ─── /status ─────────────────────────────────────────────────────────────────

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if not user:
            await update.message.reply_text(
                "❌ Hesabınız bağlanmayıb.\n"
                "Saytdan /start <token> əldə edin."
            )
            return

        watchlist = db.query(UserWatchlist).filter(UserWatchlist.user_id == user.id).all()
        groups = db.query(UserTelegramGroup).filter(
            UserTelegramGroup.user_id == user.id,
            UserTelegramGroup.is_active == True,
        ).all()

        symbols_txt = ", ".join(f"{r.symbol}" for r in watchlist) or "—"
        groups_txt  = ", ".join(g.title or g.chat_id for g in groups) or "—"

        await update.message.reply_text(
            f"📊 <b>Hesab Statusu</b>\n"
            f"📧 {user.email}\n"
            f"🤖 Bot: {'AKTİV ✅' if user.bot_enabled else 'DAYANIB ⏸'}\n\n"
            f"👁 İzlənilən coinlər:\n{symbols_txt}\n\n"
            f"📢 Bağlı qruplar:\n{groups_txt}",
            parse_mode="HTML",
        )
    finally:
        db.close()


# ─── /mysymbols ──────────────────────────────────────────────────────────────

async def mysymbols_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if not user:
            await update.message.reply_text("❌ Hesabınız bağlanmayıb.")
            return
        watchlist = db.query(UserWatchlist).filter(UserWatchlist.user_id == user.id).all()
        if not watchlist:
            await update.message.reply_text(
                "📭 Watchlist boşdur.\n"
                "Saytdakı Ayarlar → İzlənilən Coinlər bölməsindən əlavə edin."
            )
            return
        lines = [f"• {r.symbol} ({r.exchange})" for r in watchlist]
        await update.message.reply_text(
            f"📊 <b>İzlənilən coinlər ({len(watchlist)}):</b>\n" + "\n".join(lines),
            parse_mode="HTML",
        )
    finally:
        db.close()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not settings.TELEGRAM_BOT_TOKEN:
        log.warning("No Telegram token; listener disabled.")
        return
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start_cmd))
    app.add_handler(CommandHandler("addgroup",  addgroup_cmd))
    app.add_handler(CommandHandler("status",    status_cmd))
    app.add_handler(CommandHandler("mysymbols", mysymbols_cmd))
    log.info("Telegram listener started.")
    app.run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
