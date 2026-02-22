def nonempty(s: str) -> bool:
    return bool(s and s.strip())

def nonneg_int(s: str) -> bool:
    try:
        return int(s) >= 0
    except Exception:
        return False

def pos_int(s: str) -> bool:
    try:
        return int(s) > 0
    except Exception:
        return False

def nonneg_float(s: str) -> bool:
    try:
        return float(s) >= 0
    except Exception:
        return False
