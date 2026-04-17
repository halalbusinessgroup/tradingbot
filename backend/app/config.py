from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    AES_KEY: str

    BINANCE_TESTNET: bool = True
    BYBIT_TESTNET: bool = True

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = ""

    ADMIN_EMAIL: str = "admin@mytradingbot.com"
    ADMIN_PASSWORD: str = "ChangeMe123!"

    FRONTEND_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"

    # Anthropic AI Analysis
    ANTHROPIC_API_KEY: str = ""

    # TA Signal Engine
    SIGNAL_SYMBOLS: str = "BTCUSDT,ETHUSDT,BNBUSDT"   # comma-separated
    SIGNAL_EXCHANGE: str = "binance"
    SIGNAL_TIMEFRAME: str = "1h"
    SIGNAL_INTERVAL_MINUTES: int = 30          # how often to scan
    SIGNAL_COOLDOWN_HOURS: int = 3             # min gap between same signal
    SIGNAL_THRESHOLD_STRONG: float = 7.0
    SIGNAL_THRESHOLD_WEAK: float = 4.0
    SIGNAL_RISK_MULT: float = 1.5
    SIGNAL_TP1_MULT: float = 2.0
    SIGNAL_TP2_MULT: float = 3.5
    SIGNAL_TELEGRAM_CHAT_ID: str = ""          # Telegram chat/channel ID for signals

    # SMTP (email verification)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
