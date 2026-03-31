from __future__ import annotations

import sys
from pathlib import Path

# ── App Info ───────────────────────────────────────────────────────────────
APP_NAME = "Aissa's Kitchenette"
APP_VERSION = "1.0"

# Backwards-compat aliases (some modules import these)
APP_VER = APP_VERSION


# ── EXE-aware path resolution ──────────────────────────────────────────────
# When packaged as a one-file PyInstaller EXE:
#   sys.frozen = True
#   sys._MEIPASS = read-only temp extraction dir (deleted on exit)
#   sys.executable = path to the .exe itself
#
# Bundled READ-ONLY assets  →  sys._MEIPASS  (fonts, icons, logo, product_images)
# Writable user data        →  dir of sys.executable  (database, exports, receipts)
#
# In normal Python (dev) run:
#   _BUNDLE_DIR   = aissas_pos_system/  (where assets/ lives next to main.py)
#   _WRITABLE_ROOT = project root  (where data/ and exports/ live)

def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


if _is_frozen():
    # Packaged EXE
    _BUNDLE_DIR    = Path(sys._MEIPASS)           # type: ignore[attr-defined]
    _WRITABLE_ROOT = Path(sys.executable).parent  # next to the .exe
else:
    # Normal dev run  (this file lives at  aissas_pos_system/app/config.py)
    _BUNDLE_DIR    = Path(__file__).resolve().parent.parent   # aissas_pos_system/
    _WRITABLE_ROOT = _BUNDLE_DIR.parent                       # project root


# ── Read-only bundled assets (safe in both modes) ─────────────────────────
ASSETS_DIR = _BUNDLE_DIR / "assets"
ICONS_DIR  = ASSETS_DIR / "icons"
LOGO_PATH  = ASSETS_DIR / "logo.png"

# ── Writable directories (persistent; never in the temp bundle dir) ────────
DATA_DIR         = _WRITABLE_ROOT / "data"
DB_PATH          = DATA_DIR / "pos.db"
EXPORTS_DIR      = _WRITABLE_ROOT / "exports"
RECEIPTS_DIR     = _WRITABLE_ROOT / "receipts"

# Product images the user may place next to the EXE (or in the dev tree)
PRODUCT_IMAGES_DIR = _WRITABLE_ROOT / "product_images"

# ── Backwards-compat aliases kept so existing imports don't break ──────────
BASE_DIR    = _BUNDLE_DIR    # receipt_service uses this for font lookup
PROJECT_DIR = _WRITABLE_ROOT


# ── Theme (Brown / Beige / White) ─────────────────────────────────────────
THEME = {
    # main colors
    "bg": "#F5EFE6",            # beige background
    "panel": "#FFFFFF",         # white panels

    # primary browns
    "brown": "#6B4B3A",
    "brown_dark": "#3E2A22",

    # neutrals
    "beige": "#EADFD2",
    "border": "#D5C7B8",
    "text": "#1F1F1F",
    "muted": "#6E6E6E",

    # buttons / states
    "accent": "#8B5E3C",
    "danger": "#C04B45",
    "success": "#2E7D32",
    "warning": "#D49B28",

    # selection highlight
    "select_bg": "#8B5E3C",
    "select_fg": "#FFFFFF",
}

# Backwards / UI aliases
THEME["primary"]       = THEME["brown"]
THEME["primary_dark"]  = THEME["brown_dark"]
THEME["primary_light"] = THEME["accent"]

THEME.setdefault("header_bg", THEME["primary_dark"])
THEME.setdefault("nav_bg",    THEME["primary"])
THEME.setdefault("input_bg",  THEME["beige"])
THEME.setdefault("card_bg",   THEME["panel"])
THEME.setdefault("panel2",    THEME["beige"])   # login_view / pos_view
THEME.setdefault("brown2",    THEME["accent"])  # login sign-in button
THEME.setdefault("primary",   THEME["brown"])
THEME.setdefault("secondary", THEME["beige"])

THEME["text_on_primary"] = "#FFFFFF"
THEME["text_on_accent"]  = "#FFFFFF"
THEME["text_on_danger"]  = "#FFFFFF"
THEME["text_on_success"] = "#FFFFFF"
THEME["text_on_warning"] = "#FFFFFF"


# ── Defaults / Seeding ─────────────────────────────────────────────────────
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

DEFAULT_ADMIN_USER          = DEFAULT_ADMIN_USERNAME
DEFAULT_ADMIN_PASS          = DEFAULT_ADMIN_PASSWORD
DEFAULT_ADMIN_USER_NAME     = DEFAULT_ADMIN_USERNAME
DEFAULT_ADMIN_USER_PASSWORD = DEFAULT_ADMIN_PASSWORD


# ── Auto-create writable directories at startup ───────────────────────────
# These calls are safe (exist_ok=True) and run once when config is imported.
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
PRODUCT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# ── Image path resolver (used by pos_view to find product images) ──────────
def resolve_image_path(rel_path: str) -> Path | None:
    """
    Resolve a relative product-image path to an absolute Path that exists.

    Search order:
    1. Absolute path that already exists — used as-is.
    2. PRODUCT_IMAGES_DIR / filename  (next to EXE, or project root in dev).
    3. _BUNDLE_DIR / rel_path         (bundled inside the EXE).

    Returns None if the image cannot be found anywhere.
    """
    if not rel_path:
        return None

    p = Path(rel_path)

    # Already absolute and present
    if p.is_absolute() and p.exists():
        return p

    # Writable location (user-placed images next to EXE, or dev tree)
    candidate = _WRITABLE_ROOT / rel_path
    if candidate.exists():
        return candidate

    # Bundled inside the EXE (read-only)
    candidate = _BUNDLE_DIR / rel_path
    if candidate.exists():
        return candidate

    return None


# ── Debug Mode ────────────────────────────────────────────────────────────
DEBUG = False  # Set True to enable ML recommendation debug output
