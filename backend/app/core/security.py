from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
fernet = Fernet(settings.AES_KEY.encode())


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def encrypt_str(plain: str) -> str:
    return fernet.encrypt(plain.encode()).decode()


def decrypt_str(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()
