from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False)   # Admin must approve new users
    can_trade = Column(Boolean, default=True)       # Admin can disable trading
    bot_enabled = Column(Boolean, default=False)

    # Profile fields
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    address = Column(String(255), nullable=True)

    # Telegram
    telegram_chat_id = Column(String(64), nullable=True)
    telegram_link_token = Column(String(64), nullable=True)

    # Email verification (for profile changes)
    verify_code = Column(String(10), nullable=True)
    verify_code_expires = Column(DateTime(timezone=True), nullable=True)
    verify_pending_email = Column(String(255), nullable=True)

    # Password reset
    reset_token = Column(String(128), nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)

    # 2FA (Google Authenticator)
    totp_secret = Column(String(64), nullable=True)
    totp_enabled = Column(Boolean, default=False)

    # Notification preferences
    email_notifications = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
