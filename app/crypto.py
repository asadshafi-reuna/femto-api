"""Encrypt third-party tokens before they touch the database.

A GitHub token with `repo` scope can read a user's private source. Storing it in
plaintext means a database leak hands over their code. Fernet-encrypt at rest and
decrypt only in memory when making a GitHub call.
"""
from .config import settings

try:
    from cryptography.fernet import Fernet
    _OK = True
except Exception:
    _OK = False


def _f():
    if not _OK or not settings.token_encryption_key:
        return None
    return Fernet(settings.token_encryption_key.encode())


def encrypt(plain: str) -> str:
    f = _f()
    if f is None:
        # Never silently store a plaintext secret.
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not configured.")
    return f.encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    f = _f()
    if f is None:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not configured.")
    return f.decrypt(token.encode()).decode()


def configured() -> bool:
    return _f() is not None
