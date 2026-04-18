"""Watchlist & Telegram groups API."""
import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.watchlist import UserWatchlist
from app.models.telegram_group import UserTelegramGroup
from app.config import settings

router = APIRouter(prefix="/api/users", tags=["watchlist"])


# ─── Watchlist ────────────────────────────────────────────────────────────────

class WatchlistItem(BaseModel):
    symbol: str
    exchange: str = "binance"


@router.get("/watchlist")
def get_watchlist(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(UserWatchlist).filter(UserWatchlist.user_id == user.id).all()
    return [{"id": r.id, "symbol": r.symbol, "exchange": r.exchange} for r in rows]


@router.post("/watchlist")
def add_to_watchlist(
    item: WatchlistItem,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    symbol = item.symbol.strip().upper()
    exchange = item.exchange.lower()
    existing = db.query(UserWatchlist).filter(
        UserWatchlist.user_id == user.id,
        UserWatchlist.symbol == symbol,
        UserWatchlist.exchange == exchange,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"{symbol} already in watchlist")
    row = UserWatchlist(user_id=user.id, symbol=symbol, exchange=exchange)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "symbol": row.symbol, "exchange": row.exchange}


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(
    symbol: str,
    exchange: str = "binance",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.query(UserWatchlist).filter(
        UserWatchlist.user_id == user.id,
        UserWatchlist.symbol == symbol.upper(),
        UserWatchlist.exchange == exchange.lower(),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ─── Telegram Groups ──────────────────────────────────────────────────────────

@router.get("/telegram-groups")
def get_telegram_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(UserTelegramGroup).filter(UserTelegramGroup.user_id == user.id).all()
    return [{"id": r.id, "chat_id": r.chat_id, "title": r.title, "is_active": r.is_active} for r in rows]


@router.post("/telegram-groups/link-token")
def get_group_link_token(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a one-time token the user forwards to their Telegram group.
    In the group they type: /addgroup <token>
    """
    token = secrets.token_urlsafe(16)
    # Store token temporarily in user record (reuse telegram_link_token field with prefix)
    user.telegram_link_token = f"grp:{token}"
    db.commit()
    bot_username = settings.TELEGRAM_BOT_USERNAME or "your_bot"
    return {
        "token": token,
        "command": f"/addgroup {token}",
        "instruction": f"Add @{bot_username} to your group, then send this command in the group: /addgroup {token}",
    }


@router.delete("/telegram-groups/{group_id}")
def remove_telegram_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.query(UserTelegramGroup).filter(
        UserTelegramGroup.id == group_id,
        UserTelegramGroup.user_id == user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.put("/telegram-groups/{group_id}/toggle")
def toggle_telegram_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.query(UserTelegramGroup).filter(
        UserTelegramGroup.id == group_id,
        UserTelegramGroup.user_id == user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    row.is_active = not row.is_active
    db.commit()
    return {"ok": True, "is_active": row.is_active}
