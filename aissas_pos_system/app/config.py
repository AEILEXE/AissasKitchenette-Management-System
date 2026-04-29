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


# ── RESTAURANT POS THEME — Balanced Warm Café Palette ───────────────────
THEME = {
    # ── Core Palette ──────────────────────────────────────────────────────
    "bg":           "#F4EFEA",   # warm cream background
    "bg_warm":      "#F4EFEA",   # unified background
    "panel":        "#FFFFFF",   # white card panels

    # Sidebar & Topbar — Rich Warm Brown
    "sidebar":       "#8B5E3C",   # rich warm coffee brown
    "sidebar_active":"#C08A6B",   # terracotta active highlight
    "sidebar_hover": "#7A5030",   # deeper hover brown
    "topbar":        "#8B5E3C",

    # Primary — Warm Wood Brown
    "primary":      "#8B5E3C",   # warm wood brown
    "primary_dark": "#7A5030",   # darker brown (hover)
    "primary_light":"#B8855C",   # lighter warm brown

    # Accent — Warm Terracotta
    "accent":       "#C08A6B",   # warm terracotta accent
    "accent_dark":  "#A67055",   # deeper terracotta for hover

    # Dark Neutral
    "neutral_dark":  "#8B5E3C",

    # Text & Borders
    "text":         "#2B2B2B",   # near-black text
    "text_light":   "#FFFFFF",
    "muted":        "#6A6A6A",   # neutral muted gray
    "border":       "#D9C5B2",   # soft warm border
    "border_focus": "#C08A6B",   # terracotta focus border
    "beige":        "#EDE4D8",   # warm beige for inputs

    # Status colors
    "success":      "#4A7C59",   # muted green
    "success_bg":   "#EEF7F2",
    "danger":       "#B55B52",   # muted warm red
    "danger_bg":    "#FDF0EE",
    "warning":      "#C8903A",   # warm amber warning
    "warning_bg":   "#FDF4E7",

    # Card accent borders
    "card_accent_1": "#C08A6B",
    "card_accent_2": "#8B5E3C",
    "card_accent_3": "#C8903A",
    "card_accent_4": "#4A7C59",

    # Selection
    "select_bg":    "#8B5E3C",
    "select_fg":    "#FFFFFF",

    # Legacy keys — map to new warm palette so existing code works unchanged
    "brown":        "#8B5E3C",   # PRIMARY warm brown
    "brown_dark":   "#7A5030",   # darker brown (hover)
    "brown2":       "#C08A6B",   # terracotta accent
}

THEME["header_bg"]      = THEME["primary_dark"]
THEME["nav_bg"]         = THEME["primary"]
THEME["input_bg"]       = THEME["beige"]
THEME["card_bg"]        = THEME["panel"]
THEME["panel2"]         = THEME["beige"]
THEME["secondary"]      = THEME["beige"]

THEME["text_on_primary"] = "#FFFFFF"
THEME["text_on_accent"]  = "#1C1C1C"
THEME["text_on_danger"]  = "#FFFFFF"
THEME["text_on_success"] = "#FFFFFF"
THEME["text_on_warning"] = "#1C1C1C"
THEME["text_on_sidebar"] = "#FFFFFF"


# ── Defaults / Seeding ─────────────────────────────────────────────────────
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin123@"

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
