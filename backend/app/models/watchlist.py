"""User per-coin watchlist model."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from app.database import Base


class UserWatchlist(Base):
    __tablename__ = "user_watchlist"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol     = Column(String(20), nullable=False)
    exchange   = Column(String(20), nullable=False, default="binance")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", "exchange", name="uq_watchlist_user_symbol_exchange"),
    )
