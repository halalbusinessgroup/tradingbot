import secrets
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.schemas.schemas import ApiKeyIn, ApiKeyOut, BotToggle, ProfileUpdate, EmailChangeRequest, EmailChangeConfirm
from app.core.security import encrypt_str, decrypt_str
from app.core.deps import get_current_user
from app.services.exchange_service import ExchangeService, make_public_client
from app.services.email_service import generate_code, send_verification_email, send_feedback_to_admin
from app.config import settings

router = APIRouter(prefix="/api/users", tags=["users"])
log = logging.getLogger("users")


# ---------- Exchange API Key ----------

@router.post("/exchange-key", response_model=ApiKeyOut)
def add_exchange_key(payload: ApiKeyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exchange = payload.exchange.lower()
    if exchange not in ("binance", "bybit"):
        raise HTTPException(400, "Yalnız binance və ya bybit dəstəklənir")

    try:
        svc = ExchangeService(exchange, payload.api_key, payload.api_secret)
        svc.validate_key()
        log.info(f"Exchange key validated OK for user {user.id} ({exchange})")
        # Withdrawal check (non-testnet only)
        is_testnet = settings.BINANCE_TESTNET if exchange == "binance" else settings.BYBIT_TESTNET
        if not is_testnet:
            if svc.check_withdrawal_enabled():
                raise HTTPException(400, "API açarında Withdrawal icazəsi aktivdir. Binance/Bybit-də onu deaktiv edin.")
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Exchange key error: {e}")
        raise HTTPException(400, f"API açarı yoxlanılmadı: {e}")

    # Replace existing key for this exchange
    db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.exchange == exchange).delete()
    rec = ApiKey(
        user_id=user.id,
        exchange=exchange,
        api_key_enc=encrypt_str(payload.api_key),
        api_secret_enc=encrypt_str(payload.api_secret),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return ApiKeyOut(
        id=rec.id, exchange=rec.exchange, is_active=rec.is_active,
        masked_key=payload.api_key[:6] + "..." + payload.api_key[-4:]
    )


@router.get("/exchange-keys")
def get_exchange_keys(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    keys = db.query(ApiKey).filter(ApiKey.user_id == user.id).all()
    result = {}
    for k in keys:
        plain = decrypt_str(k.api_key_enc)
        result[k.exchange] = {
            "id": k.id,
            "exchange": k.exchange,
            "masked_key": plain[:6] + "..." + plain[-4:],
            "is_active": k.is_active,
        }
    return result


@router.delete("/exchange-key/{exchange}")
def delete_exchange_key(exchange: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.exchange == exchange).delete()
    db.commit()
    return {"ok": True}


# ---------- Backward compatibility ----------
@router.post("/binance-key", response_model=ApiKeyOut)
def add_binance_key(payload: ApiKeyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payload.exchange = "binance"
    return add_exchange_key(payload, db, user)


@router.get("/binance-key")
def get_binance_key(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    keys = get_exchange_keys(db, user)
    return keys.get("binance")


@router.delete("/binance-key")
def delete_binance_key(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return delete_exchange_key("binance", db, user)


# ---------- Markets (public — no API key needed, bypasses IP restrictions) ----------
@router.get("/markets")
def markets(exchange: str = "binance", user: User = Depends(get_current_user)):
    try:
        pub = make_public_client(exchange)
        pub.load_markets()
        result = []
        for symbol, market in pub.markets.items():
            if market.get("spot") and market.get("active") and market.get("quote") == "USDT":
                result.append({
                    "symbol": market["id"],     # BTCUSDT
                    "base":   market["base"],   # BTC
                    "quote":  market["quote"],  # USDT
                    "ccxt_symbol": symbol,      # BTC/USDT
                })
        result.sort(key=lambda x: x["base"])
        return result
    except Exception as e:
        raise HTTPException(500, f"Market siyahısı alınamadı: {e}")


# ---------- Validate symbol (public) ----------
@router.get("/validate-symbol")
def validate_symbol(exchange: str = "binance", symbol: str = "", user: User = Depends(get_current_user)):
    """Check if a trading symbol exists on the exchange."""
    symbol = symbol.upper().strip()
    if not symbol:
        raise HTTPException(400, "Symbol boşdur")
    try:
        pub = make_public_client(exchange)
        pub.load_markets()
        # Check by exchange-native symbol (e.g. BTCUSDT) or ccxt symbol (BTC/USDT)
        exists = (symbol in pub.markets or
                  symbol.replace('/', '') in [m.get("id", "") for m in pub.markets.values()])
        return {"symbol": symbol, "exists": exists}
    except Exception as e:
        raise HTTPException(500, f"Yoxlama xətası: {e}")


# ---------- Tickers (public — no API key needed) ----------
@router.get("/tickers")
def tickers(exchange: str = "binance", user: User = Depends(get_current_user)):
    try:
        pub = make_public_client(exchange)
        all_tickers = pub.fetch_tickers()
        result = {}
        for sym, t in all_tickers.items():
            if not sym.endswith("/USDT"):
                continue
            raw = sym.replace("/", "")
            result[raw] = {
                "price":    float(t.get("last") or 0),
                "change24h": round(float(t.get("percentage") or 0), 2),
                "volume24h": round(float(t.get("quoteVolume") or 0), 0),
                "high24h":  float(t.get("high") or 0),
                "low24h":   float(t.get("low") or 0),
            }
        return result
    except Exception as e:
        raise HTTPException(500, f"Ticker xətası: {e}")


# ---------- Bot Logs ----------
@router.get("/bot-logs")
def bot_logs(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.log import Log
    logs = (
        db.query(Log)
        .filter(Log.user_id == user.id)
        .order_by(Log.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": l.id, "level": l.level, "message": l.message,
         "created_at": l.created_at.isoformat() if l.created_at else None}
        for l in logs
    ]


# ---------- Balance ----------
@router.get("/balance")
def balance(exchange: str = "binance", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rec = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.exchange == exchange).first()
    if not rec:
        raise HTTPException(400, f"{exchange} API açarı tapılmadı")
    svc = ExchangeService(exchange, decrypt_str(rec.api_key_enc), decrypt_str(rec.api_secret_enc))
    return svc.fetch_balance()


# ---------- Telegram ----------
@router.post("/telegram-link")
def telegram_link(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    token = secrets.token_urlsafe(16)
    user.telegram_link_token = token
    db.commit()
    deep_link = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}" if settings.TELEGRAM_BOT_USERNAME else None
    return {"token": token, "link": deep_link}


# ---------- Bot toggle ----------
@router.post("/bot/toggle")
def toggle_bot(payload: BotToggle, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.enabled:
        has_key = db.query(ApiKey).filter(ApiKey.user_id == user.id).first()
        if not has_key:
            raise HTTPException(400, "Please add a Binance or Bybit API key first")
    user.bot_enabled = payload.enabled
    db.commit()
    from app.services import telegram_service as tg
    if payload.enabled:
        tg.send_message(user.telegram_chat_id, tg.msg_bot_started())
    else:
        tg.send_message(user.telegram_chat_id, tg.msg_bot_stopped())
    return {"bot_enabled": user.bot_enabled}


# ---------- Profile ----------
@router.put("/profile")
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.address is not None:
        user.address = payload.address
    db.commit()
    db.refresh(user)
    return {"ok": True, "first_name": user.first_name, "last_name": user.last_name,
            "phone": user.phone, "address": user.address}


# ---------- Feedback (bug report / feature request) ----------

class FeedbackIn(BaseModel):
    feedback_type: str  # "bug" | "feature"
    message: str


@router.post("/feedback")
def submit_feedback(payload: FeedbackIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload.message or len(payload.message.strip()) < 10:
        raise HTTPException(400, "Message too short (min 10 characters)")
    if payload.feedback_type not in ("bug", "feature"):
        raise HTTPException(400, "Invalid feedback type")
    # Send to admin email
    admin_email = settings.ADMIN_EMAIL
    if admin_email:
        send_feedback_to_admin(admin_email, user.email, payload.feedback_type, payload.message.strip())
    log.info(f"Feedback from {user.email}: [{payload.feedback_type}] {payload.message[:80]}")
    return {"ok": True}


# ---------- Email change ----------
@router.post("/email-change/request")
def email_change_request(payload: EmailChangeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.query(User).filter(User.email == payload.new_email, User.id != user.id).first():
        raise HTTPException(400, "Bu email artıq başqa hesabda istifadə olunur")
    code = generate_code()
    user.verify_code = code
    user.verify_code_expires = datetime.utcnow() + timedelta(minutes=10)
    user.verify_pending_email = payload.new_email
    db.commit()
    sent = send_verification_email(payload.new_email, code)
    if not sent:
        return {"ok": True, "message": "SMTP konfiqurasiya edilməyib — test kodu: " + code}
    return {"ok": True, "message": f"{payload.new_email} ünvanına kod göndərildi"}


@router.post("/email-change/confirm")
def email_change_confirm(payload: EmailChangeConfirm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.verify_code or not user.verify_pending_email:
        raise HTTPException(400, "Aktiv kod tapılmadı. Yenidən sorğu göndərin.")
    if user.verify_code_expires and datetime.utcnow() > user.verify_code_expires.replace(tzinfo=None):
        raise HTTPException(400, "Kodun müddəti bitib")
    if user.verify_code != payload.code.strip():
        raise HTTPException(400, "Kod yanlışdır")
    user.email = user.verify_pending_email
    user.verify_code = None
    user.verify_pending_email = None
    user.verify_code_expires = None
    db.commit()
    return {"ok": True, "new_email": user.email}
