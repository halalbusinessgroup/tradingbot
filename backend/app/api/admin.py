"""Admin API — user management, approval, role control, platform stats."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.models.trade import Trade
from app.models.log import Log
from app.schemas.schemas import AdminUserOut, SetRoleReq, AdminApproveReq
from app.core.deps import get_current_admin, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_row(u: User, db: Session) -> AdminUserOut:
    has_binance = db.query(ApiKey).filter(ApiKey.user_id == u.id, ApiKey.exchange == "binance").count() > 0
    has_bybit = db.query(ApiKey).filter(ApiKey.user_id == u.id, ApiKey.exchange == "bybit").count() > 0
    open_t = db.query(Trade).filter(Trade.user_id == u.id, Trade.status == "OPEN").count()
    closed = db.query(Trade).filter(Trade.user_id == u.id, Trade.status != "OPEN").all()
    return AdminUserOut(
        id=u.id, email=u.email, role=u.role,
        is_active=u.is_active, is_approved=u.is_approved, can_trade=u.can_trade,
        first_name=u.first_name, last_name=u.last_name, phone=u.phone,
        bot_enabled=u.bot_enabled, has_binance_key=has_binance,
        has_bybit_key=has_bybit, has_telegram=bool(u.telegram_chat_id),
        open_trades=open_t, closed_trades=len(closed),
        total_pnl=round(sum(t.pnl or 0 for t in closed), 4),
        created_at=u.created_at,
    )


@router.get("/users", response_model=List[AdminUserOut])
def all_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    users = db.query(User).order_by(User.id.desc()).all()
    return [_user_row(u, db) for u in users]


@router.get("/users/pending", response_model=List[AdminUserOut])
def pending_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Return users awaiting approval."""
    users = db.query(User).filter(User.is_approved == False).order_by(User.id.desc()).all()
    return [_user_row(u, db) for u in users]


@router.get("/stats")
def stats(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    all_closed = db.query(Trade).filter(Trade.status != "OPEN", Trade.paper_trade == False).all()
    return {
        "total_users": db.query(User).count(),
        "pending_users": db.query(User).filter(User.is_approved == False).count(),
        "active_bots": db.query(User).filter(User.bot_enabled == True).count(),
        "total_trades": db.query(Trade).filter(Trade.paper_trade == False).count(),
        "open_trades": db.query(Trade).filter(Trade.status == "OPEN", Trade.paper_trade == False).count(),
        "platform_pnl": round(sum(t.pnl or 0 for t in all_closed), 2),
    }


@router.get("/stats/daily")
def daily_stats(days: int = 30, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Return daily trade counts and PnL for the last N days (for chart)."""
    result = []
    today = datetime.utcnow().date()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        closed = db.query(Trade).filter(
            Trade.closed_at >= day_start,
            Trade.closed_at < day_end,
            Trade.paper_trade == False,
        ).all()
        result.append({
            "date": day.isoformat(),
            "trades": len(closed),
            "pnl": round(sum(t.pnl or 0 for t in closed), 4),
            "wins": sum(1 for t in closed if (t.pnl or 0) > 0),
            "losses": sum(1 for t in closed if (t.pnl or 0) <= 0 and t.pnl is not None),
        })
    return result


# ── User Actions ─────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, payload: AdminApproveReq,
                 db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Approve or reject a pending user registration."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "İstifadəçi tapılmadı")
    u.is_approved = payload.approved
    if not payload.approved:
        u.is_active = False  # rejected users also deactivated
    db.commit()

    # Notify the user
    from app.config import settings
    from app.api.auth import _send_email, _email_template
    if payload.approved:
        body = _email_template(
            "Hesabınız Təsdiqləndi! ✅",
            f"""
            <p>Admin hesabınızı təsdiqlədi. İndi daxil ola bilərsiniz:</p>
            <a href="{settings.FRONTEND_URL}/login"
               style="display:inline-block;margin:16px 0;padding:12px 24px;background:#22c55e;
                      color:#000;border-radius:8px;text-decoration:none;font-weight:bold">
              Daxil Ol →
            </a>
            """
        )
        _send_email(u.email, "⚡ TradingBot — Hesabınız Aktivdir", body)
    else:
        body = _email_template(
            "Qeydiyyat Rədd Edildi",
            "<p>Təəssüf ki, qeydiyyat sorğunuz admin tərəfindən rədd edildi.</p>"
        )
        _send_email(u.email, "⚡ TradingBot — Qeydiyyat Rədd", body)

    return {"ok": True, "is_approved": u.is_approved}


@router.post("/users/{user_id}/toggle-active")
def toggle_active(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "İstifadəçi tapılmadı")
    u.is_active = not u.is_active
    db.commit()
    return {"is_active": u.is_active}


@router.post("/users/{user_id}/set-role")
def set_role(user_id: int, payload: SetRoleReq,
             db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Set user role. Only full admins can change roles."""
    # Prevent admin from changing their own role
    if user_id == admin.id:
        raise HTTPException(403, "Öz rolunuzu dəyişə bilməzsiniz")

    allowed_roles = ("user", "admin", "moderator")
    if payload.role not in allowed_roles:
        raise HTTPException(400, f"Yanlış rol. İcazə verilənlər: {', '.join(allowed_roles)}")

    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "İstifadəçi tapılmadı")

    u.role = payload.role
    db.commit()
    return {"ok": True, "role": u.role}


@router.post("/users/{user_id}/toggle-trading")
def toggle_trading(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Enable or disable trading permission for a user."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "İstifadəçi tapılmadı")
    u.can_trade = not u.can_trade
    if not u.can_trade:
        u.bot_enabled = False  # stop bot if trading disabled
    db.commit()
    return {"can_trade": u.can_trade}


@router.post("/users/{user_id}/toggle-bot")
def admin_toggle_bot(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Force-start or force-stop a user's bot."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "İstifadəçi tapılmadı")
    u.bot_enabled = not u.bot_enabled
    db.commit()
    return {"bot_enabled": u.bot_enabled}


@router.get("/users/{user_id}/trades")
def user_trades(user_id: int, limit: int = 50,
                db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    trades = db.query(Trade).filter(Trade.user_id == user_id).order_by(Trade.id.desc()).limit(limit).all()
    return [
        {
            "id": t.id, "symbol": t.symbol, "qty": t.qty,
            "entry_price": t.entry_price, "exit_price": t.exit_price,
            "status": t.status, "pnl": t.pnl, "paper_trade": t.paper_trade,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        }
        for t in trades
    ]


@router.get("/users/financial-overview")
def financial_overview(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Per-user financial overview: PnL breakdown, win rate, best/worst trade, open trade value."""
    users = db.query(User).order_by(User.id.asc()).all()
    result = []
    for u in users:
        closed = db.query(Trade).filter(
            Trade.user_id == u.id,
            Trade.status != "OPEN",
            Trade.paper_trade == False,
        ).all()
        open_trades = db.query(Trade).filter(
            Trade.user_id == u.id,
            Trade.status == "OPEN",
            Trade.paper_trade == False,
        ).all()
        paper_trades = db.query(Trade).filter(
            Trade.user_id == u.id,
            Trade.paper_trade == True,
        ).all()

        pnl_list = [t.pnl or 0.0 for t in closed]
        total_pnl  = round(sum(pnl_list), 4)
        total_profit = round(sum(p for p in pnl_list if p > 0), 4)
        total_loss   = round(sum(p for p in pnl_list if p < 0), 4)
        wins         = sum(1 for p in pnl_list if p > 0)
        losses       = sum(1 for p in pnl_list if p < 0)
        total_closed = len(closed)
        win_rate     = round(wins / total_closed * 100, 1) if total_closed > 0 else 0.0

        best_trade  = round(max(pnl_list), 4) if pnl_list else None
        worst_trade = round(min(pnl_list), 4) if pnl_list else None

        # Open trade estimated value = sum(qty * entry_price)
        open_value = round(
            sum((t.qty or 0) * (t.entry_price or 0) for t in open_trades), 4
        )

        # Paper trading stats
        paper_pnl_list = [t.pnl or 0.0 for t in paper_trades if t.status != "OPEN"]
        paper_pnl = round(sum(paper_pnl_list), 4)

        # Avg trade PnL
        avg_pnl = round(total_pnl / total_closed, 4) if total_closed > 0 else 0.0

        result.append({
            "user_id":      u.id,
            "email":        u.email,
            "first_name":   u.first_name or "",
            "last_name":    u.last_name or "",
            "bot_enabled":  u.bot_enabled,
            "total_pnl":    total_pnl,
            "total_profit": total_profit,
            "total_loss":   total_loss,
            "win_rate":     win_rate,
            "wins":         wins,
            "losses":       losses,
            "total_closed": total_closed,
            "open_trades":  len(open_trades),
            "open_value":   open_value,
            "best_trade":   best_trade,
            "worst_trade":  worst_trade,
            "avg_pnl":      avg_pnl,
            "paper_pnl":    paper_pnl,
            "paper_trades": len(paper_trades),
        })
    return result


@router.get("/logs")
def logs(limit: int = 200, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    rows = db.query(Log).order_by(Log.id.desc()).limit(limit).all()
    return [
        {"id": r.id, "user_id": r.user_id, "level": r.level,
         "message": r.message, "created_at": r.created_at}
        for r in rows
    ]
