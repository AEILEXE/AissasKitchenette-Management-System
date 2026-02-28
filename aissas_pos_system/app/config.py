from __future__ import annotations

from pathlib import Path

# ---------------- App Info ----------------
APP_NAME = "Aissas Kitchenette"
APP_VERSION = "1.0"

# Backwards-compat aliases (some modules import these)
APP_VER = APP_VERSION


# ---------------- Paths ----------------
BASE_DIR = Path(__file__).resolve().parent.parent  # .../app
PROJECT_DIR = BASE_DIR.parent  # project root

DATA_DIR = PROJECT_DIR / "data"
DB_PATH = DATA_DIR / "pos.db"

ASSETS_DIR = PROJECT_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
EXPORTS_DIR = PROJECT_DIR / "exports"

# Logo file (user said they will upload "logo.jpg")
LOGO_PATH = ASSETS_DIR / "logo.jpg"


# ---------------- Theme (Brown / Beige / White) ----------------
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

# ---------- Backwards / UI aliases ----------
# app_window.py expects primary / primary_dark etc.
THEME["primary"] = THEME["brown"]
THEME["primary_dark"] = THEME["brown_dark"]
THEME["primary_light"] = THEME["accent"]

# some UI files might expect these names too
THEME.setdefault("header_bg", THEME["primary_dark"])
THEME.setdefault("nav_bg", THEME["primary"])
THEME.setdefault("input_bg", THEME["beige"])
THEME.setdefault("card_bg", THEME["panel"])

# ✅ FIXES FOR YOUR UI FILES:
# login_view.py uses THEME["panel2"] and THEME["brown2"]
THEME.setdefault("panel2", THEME["beige"])     # input row background
THEME.setdefault("brown2", THEME["accent"])    # sign-in button color

# Backwards-compat: some code might do THEME["primary"] etc.
THEME.setdefault("primary", THEME["brown"])
THEME.setdefault("secondary", THEME["beige"])


# ---------------- Defaults / Seeding ----------------
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

# Backwards-compat aliases (your errors show modules importing these)
DEFAULT_ADMIN_USER = DEFAULT_ADMIN_USERNAME
DEFAULT_ADMIN_PASS = DEFAULT_ADMIN_PASSWORD
DEFAULT_ADMIN_USER_NAME = DEFAULT_ADMIN_USERNAME
DEFAULT_ADMIN_USER_PASSWORD = DEFAULT_ADMIN_PASSWORD

# ---------- Text colors on colored backgrounds ----------
THEME["text_on_primary"] = "#FFFFFF"
THEME["text_on_accent"] = "#FFFFFF"
THEME["text_on_danger"] = "#FFFFFF"
THEME["text_on_success"] = "#FFFFFF"
THEME["text_on_warning"] = "#FFFFFF"


# ---------------- Exports / Reports ----------------
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- Debug Mode ----------------
# Set to True to enable ML recommendation debug output in the terminal.
# Prints: cart_ids, suggested_ids, ML rows count, top scores.
DEBUG = False
