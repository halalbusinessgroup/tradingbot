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
