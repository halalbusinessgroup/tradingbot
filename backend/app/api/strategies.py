"""Strategy API — CRUD + webhook token + marketplace."""
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.strategy import Strategy
from app.schemas.schemas import StrategyIn, StrategyOut
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=List[StrategyOut])
def list_strategies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Strategy).filter(Strategy.user_id == user.id).order_by(Strategy.id.desc()).all()


@router.post("", response_model=StrategyOut)
def create_strategy(payload: StrategyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.can_trade:
        raise HTTPException(403, "Admin trading icazənizi deaktiv etmişdir")
    cfg = payload.config.model_dump()
    s = Strategy(
        user_id=user.id,
        name=payload.name,
        config=cfg,
        is_active=payload.is_active,
        is_public=payload.is_public,
        public_description=payload.public_description,
        webhook_token=secrets.token_urlsafe(32),  # auto-generate webhook token
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, payload: StrategyIn,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Strategiya tapılmadı")
    s.name = payload.name
    s.config = payload.config.model_dump()
    s.is_active = payload.is_active
    s.is_public = payload.is_public
    s.public_description = payload.public_description
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Strategiya tapılmadı")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/{strategy_id}/regenerate-webhook")
def regenerate_webhook(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Generate a new webhook token for a strategy."""
    s = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Strategiya tapılmadı")
    s.webhook_token = secrets.token_urlsafe(32)
    db.commit()
    return {"webhook_token": s.webhook_token}


# ── Marketplace ─────────────────────────────────────────────────────────────

@router.get("/marketplace", response_model=List[dict])
def marketplace(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """List all public strategies (marketplace)."""
    public = db.query(Strategy).filter(Strategy.is_public == True).order_by(Strategy.id.desc()).all()
    result = []
    for s in public:
        is_mine = s.user_id == user.id
        author = db.query(User).filter(User.id == s.user_id).first()
        result.append({
            "id": s.id,
            "name": s.name,
            "description": s.public_description or "",
            "exchange": s.config.get("exchange", "binance"),
            "timeframe": s.config.get("timeframe", "15m"),
            "tp_percent": s.config.get("tp_percent"),
            "sl_percent": s.config.get("sl_percent"),
            "entry_conditions_count": len(s.config.get("entry_conditions", [])),
            "trailing_sl": s.config.get("trailing_sl"),
            "dca_enabled": s.config.get("dca_enabled", False),
            "author": f"{author.first_name or ''} {author.last_name or ''}".strip() or "Anonim",
            "is_mine": is_mine,
            "created_at": s.created_at.isoformat(),
        })
    return result


@router.post("/marketplace/{strategy_id}/copy")
def copy_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Copy a public strategy to the current user's strategies."""
    original = db.query(Strategy).filter(
        Strategy.id == strategy_id, Strategy.is_public == True
    ).first()
    if not original:
        raise HTTPException(404, "Strategiya tapılmadı və ya ictimai deyil")

    copy = Strategy(
        user_id=user.id,
        name=f"{original.name} (kopyası)",
        config=dict(original.config),  # deep copy of JSON
        is_active=False,               # starts inactive
        is_public=False,               # copy is private by default
        webhook_token=secrets.token_urlsafe(32),
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return {"ok": True, "strategy_id": copy.id, "name": copy.name}
