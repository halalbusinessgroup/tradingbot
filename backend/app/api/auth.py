import secrets
import pyotp
import qrcode
import io
import base64
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.schemas import UserRegister, UserLogin, TokenOut, UserOut, TotpVerify
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ForgotPasswordReq(BaseModel):
    email: EmailStr


class ResetPasswordReq(BaseModel):
    token: str
    new_password: str


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Helper to send HTML email."""
    if not settings.SMTP_USER or not settings.SMTP_PASS:
        return False
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as srv:
            srv.starttls()
            srv.login(settings.SMTP_USER, settings.SMTP_PASS)
            srv.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception:
        return False


def _email_template(title: str, content: str) -> str:
    return f"""
    <html><body style="font-family:sans-serif;background:#0b0e14;color:#e6edf3;padding:40px">
      <div style="max-width:480px;margin:auto;background:#11151d;border-radius:12px;padding:32px">
        <h2 style="color:#22c55e;margin-top:0">⚡ TradingBot</h2>
        <h3 style="color:#e6edf3">{title}</h3>
        {content}
        <p style="color:#666;font-size:12px;margin-top:24px">
          Bu email TradingBot platformasından göndərilmişdir. Sual varsa admin ilə əlaqə saxlayın.
        </p>
      </div>
    </body></html>
    """


@router.post("/register")
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "Bu email artıq qeydiyyatdadır")

    # First user in system becomes auto-approved admin (or if no admin exists yet)
    user_count = db.query(User).count()
    is_auto_approved = (user_count == 0)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="admin" if is_auto_approved else "user",
        is_active=True,
        is_approved=is_auto_approved,  # New users need admin approval
        can_trade=True,
        email_notifications=True,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        address=payload.address,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Notify admin about new registration (if not first user)
    if not is_auto_approved:
        admin = db.query(User).filter(User.role == "admin", User.is_active == True).first()
        if admin and admin.email:
            body = _email_template(
                "Yeni istifadəçi qeydiyyatı",
                f"""
                <p>Yeni istifadəçi qeydiyyatdan keçdi:</p>
                <table style="border-collapse:collapse;width:100%">
                  <tr><td style="color:#888;padding:4px 0">Ad:</td>
                      <td style="padding:4px 0">{payload.first_name} {payload.last_name}</td></tr>
                  <tr><td style="color:#888;padding:4px 0">Email:</td>
                      <td style="padding:4px 0">{payload.email}</td></tr>
                  <tr><td style="color:#888;padding:4px 0">Telefon:</td>
                      <td style="padding:4px 0">{payload.phone}</td></tr>
                </table>
                <p>Admin paneldən icazə verin:</p>
                <a href="{settings.FRONTEND_URL}/admin"
                   style="display:inline-block;margin:12px 0;padding:10px 20px;background:#22c55e;
                          color:#000;border-radius:8px;text-decoration:none;font-weight:bold">
                  Admin Panelə Keç →
                </a>
                """
            )
            _send_email(admin.email, "⚡ Yeni İstifadəçi — Təsdiq Lazımdır", body)

        return {
            "pending": True,
            "message": "Qeydiyyat uğurlu. Admin icazəsi gözlənilir."
        }

    # Auto-approved (first user / admin)
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token, role=user.role, email=user.email)


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email və ya şifrə yanlışdır")
    if not user.is_active:
        raise HTTPException(403, "Hesabınız bloklanmışdır")
    if not user.is_approved:
        raise HTTPException(403, "pending_approval")

    # 2FA check
    if user.totp_enabled:
        if not payload.totp_code:
            # Signal frontend to ask for 2FA code
            return TokenOut(
                access_token="", role=user.role, email=user.email, requires_2fa=True
            )
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(payload.totp_code, valid_window=1):
            raise HTTPException(401, "Yanlış 2FA kodu")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenOut(access_token=token, role=user.role, email=user.email)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ── 2FA ────────────────────────────────────────────────────────────────────

@router.get("/2fa/setup")
def setup_2fa(user: User = Depends(get_current_user)):
    """Generate a new TOTP secret and return QR code (base64 PNG)."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    otp_uri = totp.provisioning_uri(name=user.email, issuer_name="TradingBot")

    # Generate QR code as base64
    qr = qrcode.make(otp_uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_b64}",
        "otp_uri": otp_uri,
    }


@router.post("/2fa/enable")
def enable_2fa(payload: TotpVerify, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Verify the user's TOTP code and save the secret, enabling 2FA."""
    # The secret was returned by /2fa/setup — client sends it back with a code
    # We expect the secret to be passed in a setup call first, stored temporarily
    # Here we store in totp_secret field (user must pass secret back via separate field)
    # Simplified: we store the pending secret in totp_secret before enabling
    if not user.totp_secret:
        raise HTTPException(400, "Əvvəlcə /2fa/setup çağırın")
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(400, "Yanlış kod. Yenidən cəhd edin.")
    user.totp_enabled = True
    db.commit()
    return {"ok": True, "message": "2FA aktivləşdirildi"}


@router.post("/2fa/save-secret")
def save_2fa_secret(body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Temporarily save the generated secret so enable endpoint can verify it."""
    secret = body.get("secret", "")
    if not secret or len(secret) < 16:
        raise HTTPException(400, "Yanlış secret")
    user.totp_secret = secret
    user.totp_enabled = False  # not enabled yet until verified
    db.commit()
    return {"ok": True}


@router.post("/2fa/disable")
def disable_2fa(payload: TotpVerify, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.totp_enabled:
        raise HTTPException(400, "2FA aktiv deyil")
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(400, "Yanlış kod")
    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    return {"ok": True, "message": "2FA deaktivləşdirildi"}


# ── Password Reset ──────────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return {"ok": True, "message": "If this email exists, a reset link has been sent."}

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    body = _email_template(
        "Şifrə Sıfırlama",
        f"""
        <p>Şifrənizi sıfırlamaq üçün aşağıdakı düyməyə basın:</p>
        <a href="{reset_link}"
           style="display:inline-block;margin:20px 0;padding:12px 24px;background:#22c55e;
                  color:#000;border-radius:8px;text-decoration:none;font-weight:bold">
          Şifrəni Sıfırla
        </a>
        <p style="color:#666;font-size:12px">Bu link 1 saat ərzində etibarlıdır.</p>
        """
    )
    sent = _send_email(payload.email, "⚡ TradingBot — Şifrə Sıfırlama", body)
    msg_out = "Sıfırlama linki göndərildi." if sent else f"SMTP konfiqurasiya edilməyib — dev token: {token}"
    return {"ok": True, "message": msg_out}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordReq, db: Session = Depends(get_db)):
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Şifrə ən azı 8 simvol olmalıdır")
    user = db.query(User).filter(User.reset_token == payload.token).first()
    if not user:
        raise HTTPException(400, "Yanlış və ya köhnəlmiş reset token")
    if user.reset_token_expires and datetime.utcnow() > user.reset_token_expires.replace(tzinfo=None):
        raise HTTPException(400, "Reset token müddəti bitib")
    user.password_hash = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return {"ok": True, "message": "Şifrə uğurla yeniləndi"}
