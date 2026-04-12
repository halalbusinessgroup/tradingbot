from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


# ---------- Auth ----------
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=6, max_length=30)
    address: str = Field(min_length=3, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None  # 6-digit 2FA code if 2FA enabled


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str
    requires_2fa: bool = False  # True if 2FA needed but not provided


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    is_approved: bool
    can_trade: bool
    bot_enabled: bool
    totp_enabled: bool
    email_notifications: bool
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    telegram_chat_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Profile ----------
class ProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=255)
    email_notifications: Optional[bool] = None


class EmailChangeRequest(BaseModel):
    new_email: EmailStr


class EmailChangeConfirm(BaseModel):
    code: str


# ---------- API Key ----------
class ApiKeyIn(BaseModel):
    exchange: str = "binance"  # binance | bybit
    api_key: str
    api_secret: str


class ApiKeyOut(BaseModel):
    id: int
    exchange: str
    is_active: bool
    masked_key: str

    class Config:
        from_attributes = True


# ---------- Strategy ----------
class StrategyConfig(BaseModel):
    symbols: List[str]
    amount_usdt: float = Field(gt=0)
    tp_percent: Optional[float] = None        # percent mode TP
    sl_percent: Optional[float] = None        # percent mode SL
    # TP/SL mode: 'percent' (default) | 'price'
    tp_sl_mode: str = "percent"
    tp_price: Optional[float] = None          # price mode TP (absolute USDT price)
    sl_price: Optional[float] = None          # price mode SL (absolute USDT price)
    max_open_trades: int = Field(ge=1, le=20)
    entry_conditions: List[dict] = []
    timeframe: str = "15m"
    exchange: str = "binance"
    # Order type: market | limit | stop_market | stop_limit
    order_type: str = "market"
    limit_price: Optional[float] = None       # for limit/stop_limit orders
    stop_trigger_price: Optional[float] = None  # for stop_market/stop_limit orders
    # Advanced options
    trailing_sl: Optional[float] = None       # e.g. 1.5 = 1.5% trailing stop
    trailing_tp: Optional[float] = None       # trailing take profit %
    trailing_tp_activation: Optional[float] = 3.0  # activate trailing TP at this profit %
    paper_mode: bool = False                   # simulate trades without real orders
    dca_enabled: bool = False                  # Dollar Cost Averaging
    dca_percent: float = 2.0                   # DCA trigger: price drops this % below entry
    dca_amount: float = 10.0                   # USDT to add on DCA
    no_conditions: bool = False                # Buy every cycle (no indicator check)
    auto_convert: bool = False                 # Market sell all coins to USDT on deactivation


class StrategyIn(BaseModel):
    name: str
    config: StrategyConfig
    is_active: bool = False
    is_public: bool = False
    public_description: Optional[str] = None


class StrategyOut(BaseModel):
    id: int
    name: str
    config: dict
    is_active: bool
    is_public: bool
    public_description: Optional[str]
    webhook_token: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Trade ----------
class TradeOut(BaseModel):
    id: int
    symbol: str
    side: str
    qty: float
    entry_price: float
    exit_price: Optional[float]
    tp_price: Optional[float]
    sl_price: Optional[float]
    status: str
    paper_trade: bool
    pnl: float
    pnl_percent: float
    opened_at: datetime
    closed_at: Optional[datetime]
    strategy_id: Optional[int]

    class Config:
        from_attributes = True


# ---------- Bot ----------
class BotToggle(BaseModel):
    enabled: bool


# ---------- 2FA ----------
class TotpVerify(BaseModel):
    code: str


# ---------- Webhook ----------
class WebhookSignal(BaseModel):
    action: str              # "buy" | "sell"
    symbol: str              # e.g. "SOLUSDT"
    amount_usdt: Optional[float] = None  # override strategy amount


# ---------- Admin ----------
class AdminUserOut(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    role: str
    is_active: bool
    is_approved: bool
    can_trade: bool
    bot_enabled: bool
    has_binance_key: bool
    has_bybit_key: bool
    has_telegram: bool
    open_trades: int
    closed_trades: int
    total_pnl: float
    created_at: datetime

    class Config:
        from_attributes = True


class SetRoleReq(BaseModel):
    role: str  # "user" | "admin"


class AdminApproveReq(BaseModel):
    approved: bool
