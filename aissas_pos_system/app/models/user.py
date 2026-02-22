from __future__ import annotations
from dataclasses import dataclass

@dataclass
class User:
    user_id: int
    username: str
    password_hash: str
    role: str
    is_active: bool
