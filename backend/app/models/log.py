from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func
from app.database import Base


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    level = Column(String(10), default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
