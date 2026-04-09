from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True)

    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), default="BUY")  # BUY / SELL
    qty = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    tp_price = Column(Float, nullable=True)
    sl_price = Column(Float, nullable=True)
    trailing_sl = Column(Float, nullable=True)  # trailing SL % (if active)

    binance_order_id = Column(String(64), nullable=True)
    tp_order_id = Column(String(64), nullable=True)
    sl_order_id = Column(String(64), nullable=True)

    status = Column(String(20), default="OPEN", index=True)  # OPEN | CLOSED_TP | CLOSED_SL | CLOSED_MANUAL | ERROR
    paper_trade = Column(Boolean, default=False)   # True = simulated trade (paper trading)
    pnl = Column(Float, default=0.0)
    pnl_percent = Column(Float, default=0.0)

    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="trades")
    strategy = relationship("Strategy", back_populates="trades")
