import secrets
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import relationship
from app.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    config = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=False)

    # Marketplace
    is_public = Column(Boolean, default=False)
    public_description = Column(String(500), nullable=True)

    # TradingView webhook token (unique per strategy)
    webhook_token = Column(String(64), nullable=True, unique=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="strategies")
    trades = relationship("Trade", back_populates="strategy")

    def generate_webhook_token(self):
        self.webhook_token = secrets.token_urlsafe(32)
