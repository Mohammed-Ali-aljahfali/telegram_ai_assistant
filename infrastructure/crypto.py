"""infrastructure/crypto.py — تشفير وفك تشفير البيانات الحساسة"""
import base64
import hashlib
import secrets
from cryptography.fernet import Fernet
from config import config


def _get_fernet() -> Fernet:
    key = config.ENCRYPTION_KEY
    if not key:
        raise ValueError("ENCRYPTION_KEY غير محدد في .env")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_text(text: str) -> str:
    """تشفير نص"""
    if not text:
        return ""
    f = _get_fernet()
    return f.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_text(encrypted: str) -> str:
    """فك تشفير نص"""
    if not encrypted:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def hash_password(password: str) -> str:
    """تشفير كلمة مرور باستخدام SHA-256 مع salt"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, hashed: str) -> bool:
    """التحقق من كلمة المرور"""
    try:
        salt, stored_hash = hashed.split(":", 1)
        computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(computed, stored_hash)
    except Exception:
        return False


def generate_key() -> str:
    """توليد مفتاح Fernet جديد"""
    return Fernet.generate_key().decode()
