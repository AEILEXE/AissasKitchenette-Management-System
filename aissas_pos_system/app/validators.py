import re as _re

# ── Reference number validation ───────────────────────────────────────────────
_REFERENCE_PATTERN = _re.compile(r'^\d{10,16}$')

REFERENCE_ERROR_MSG = "Reference number must be 10 to 16 digits only."


def validate_reference_no(ref: str) -> bool:
    """Return True if ref is 10–16 ASCII digits with no spaces or letters."""
    return bool(_REFERENCE_PATTERN.match((ref or "").strip()))


# ── General field validators ──────────────────────────────────────────────────

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
