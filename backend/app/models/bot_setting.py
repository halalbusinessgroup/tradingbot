"""Key-value store for runtime-configurable bot settings (overrides .env)."""
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class BotSetting(Base):
    __tablename__ = "bot_settings"

    key        = Column(String(100), primary_key=True)
    value      = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
