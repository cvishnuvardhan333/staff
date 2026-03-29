from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash


PASSWORD_METHOD = "pbkdf2:sha256"


def generate_password_hash_compat(password: str) -> str:
    return generate_password_hash(password, method=PASSWORD_METHOD)


def check_password_hash_compat(password_hash: str, password: str) -> bool:
    try:
        return check_password_hash(password_hash, password)
    except AttributeError:
        # Some Python builds do not provide hashlib.scrypt, so legacy scrypt
        # hashes cannot be verified on that runtime.
        return False
