import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet(secret: str) -> Fernet:
    if not secret:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY nie jest ustawiony")
    derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_token(token: str, secret: str) -> str:
    return _fernet(secret).encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(token: str, secret: str) -> str:
    return _fernet(secret).decrypt(token.encode("utf-8")).decode("utf-8")
