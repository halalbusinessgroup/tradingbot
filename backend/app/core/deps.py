from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import decode_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Allows both admin and moderator to access the admin panel.
    Moderators can view stats/users but cannot change other admins' roles.
    Role enforcement for sensitive ops is done per-endpoint."""
    if user.role not in ("admin", "moderator"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Strict admin-only — used for destructive/sensitive operations."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can perform this action")
    return user
