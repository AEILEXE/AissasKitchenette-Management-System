from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class User:
    user_id: int
    username: str
    password_hash: str
    role: str
    is_active: bool
    full_name: str = ""
