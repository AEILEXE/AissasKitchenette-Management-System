from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

_SALT = b"alissas-kitchenette-salt"  # stable salt for this school project

def hash_password(password: str) -> str:
    data = _SALT + password.encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)

hash_pass = hash_password
check_password = verify_password

def money(value: Any) -> str:
    try:
        v = float(value)
    except Exception:
        v = 0.0
    return f"₱{v:,.2f}"


def log_error(context: str, exc: BaseException) -> None:
    """
    Record a technical error to the internal app log file. Friendly UI
    messages should be shown separately — this only writes the stack trace
    so the dev / admin can diagnose later. Never raises.
    """
    try:
        logging.error("%s: %s", context, exc, exc_info=True)
    except Exception:
        pass


def friendly_error(context: str, exc: BaseException,
                   default: str = "Something went wrong. Please try again.") -> str:
    """
    Log the technical exception internally and return a short, user-safe
    message. Hides stack traces and SQL details from end-users.
    """
    log_error(context, exc)
    return default
