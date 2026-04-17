from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id         = Column(Integer, primary_key=True, index=True)

    symbol     = Column(String(20), nullable=False, index=True)
    exchange   = Column(String(20), nullable=False, default="binance")
    timeframe  = Column(String(10), nullable=False, default="1h")

    signal     = Column(String(20), nullable=False, index=True)  # STRONG_BUY | WEAK_BUY | NEUTRAL | WEAK_SELL | STRONG_SELL
    score      = Column(Float, nullable=False, default=0.0)
    price      = Column(Float, nullable=False)
    atr        = Column(Float, nullable=True)

    sl         = Column(Float, nullable=True)
    tp1        = Column(Float, nullable=True)
    tp2        = Column(Float, nullable=True)
    rr_ratio   = Column(Float, nullable=True)

    support    = Column(Float, nullable=True)
    resistance = Column(Float, nullable=True)

    # Full JSON details stored as text
    details_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
