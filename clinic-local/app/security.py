import base64
import secrets
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

from .config import get_settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
_settings = get_settings()
session_signer = URLSafeSerializer(_settings.app_secret_key, salt="session")
csrf_signer = URLSafeSerializer(_settings.csrf_secret, salt="csrf")

_key = _settings.fernet_secret.encode("utf-8")
_key = _key.ljust(32, b"0")[:32]
fernet = Fernet(base64.urlsafe_b64encode(_key))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_session(data: dict, expires: Optional[timedelta] = None) -> str:
    payload = {"data": data, "iat": datetime.utcnow().isoformat()}
    if expires:
        payload["exp"] = (datetime.utcnow() + expires).isoformat()
    return session_signer.dumps(payload)


def decode_session(token: str) -> Optional[dict]:
    try:
        payload = session_signer.loads(token)
    except BadSignature:
        return None
    exp = payload.get("exp")
    if exp and datetime.utcnow() > datetime.fromisoformat(exp):
        return None
    return payload.get("data")


def generate_csrf_token(session_id: str) -> str:
    nonce = secrets.token_hex(8)
    return csrf_signer.dumps({"sid": session_id, "nonce": nonce})


def verify_csrf_token(session_id: str, token: str) -> bool:
    try:
        payload = csrf_signer.loads(token)
    except BadSignature:
        return False
    return payload.get("sid") == session_id



def encrypt_text(value: str) -> str:
    if value is None:
        value = ""
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str) -> str:
    if not token:
        return ""
    return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
