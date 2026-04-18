"""User-linked Telegram groups / channels."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, UniqueConstraint
from app.database import Base


class UserTelegramGroup(Base):
    __tablename__ = "user_telegram_groups"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id    = Column(String(64), nullable=False)
    title      = Column(String(255), nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "chat_id", name="uq_tg_group_user_chat"),
    )
