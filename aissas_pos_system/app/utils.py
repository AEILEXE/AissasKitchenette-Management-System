from __future__ import annotations

import hashlib
import hmac
from typing import Any

# ---------------- Password hashing ----------------
# We keep this simple and consistent for your project.
# If you later want bcrypt, we can upgrade without breaking users.

_SALT = b"alissas-kitchenette-salt"  # stable salt for this school project

def hash_password(password: str) -> str:
    data = _SALT + password.encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)

# Backwards-compat aliases (your errors show imports expecting these)
hash_pass = hash_password
check_password = verify_password


# ---------------- Money formatting ----------------
def money(value: Any) -> str:
    try:
        v = float(value)
    except Exception:
        v = 0.0
    return f"₱{v:,.2f}"
