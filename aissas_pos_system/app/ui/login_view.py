from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from app.config import THEME, ICONS_DIR, ASSETS_DIR
from app.services.auth_service import AuthService

try:
    from PIL import Image, ImageTk, ImageFilter  # type: ignore
    _HAS_PIL = True
except Exception:
    Image       = None
    ImageTk     = None
    ImageFilter = None
    _HAS_PIL    = False

# ── Animation ─────────────────────────────────────────────────────────────────
_FOOD_FILES       = ["4.png", "5.png", "6.png"]
_FOOD_INTERVAL_MS = 8_000
_BOUNCE_AMPLITUDE = 6       # subtle — was 8
_BOUNCE_STEP_MS   = 55

# ── Landscape card ────────────────────────────────────────────────────────────
_CARD_W    = 820    # total card width  (landscape)
_CARD_H    = 460    # total card height
_LEFT_FRAC = 0.54   # left hero = 54 % of card width  → ~443 px
_FORM_PADX = 36     # horizontal padding inside form content area

# ── Gradient palettes ─────────────────────────────────────────────────────────
_BG_TOP   = (44,  24, 12)   # background behind card
_BG_MID   = (82,  54, 34)
_BG_BOT   = (58,  36, 20)
_HERO_TOP = (52,  28, 14)   # hero canvas inside card (richer)
_HERO_MID = (100, 66, 42)
_HERO_BOT = (74,  48, 28)

# ── Colour tokens ─────────────────────────────────────────────────────────────
_TITLE_FG    = "#FFFFFF"
_TITLE_SH    = "#1A0A04"    # 1 px drop-shadow
_SUBTITLE_FG = "#D4AA82"    # warm cream
_DIVIDER_CLR = "#B89872"    # accent line under subtitle
_DOT_ACTIVE  = "#EADBC8"
_DOT_IDLE    = "#5A3820"
_CARD_BG     = "#FFFFFF"
_SEPARATOR   = "#E0CEB8"    # vertical rule between hero and form
_FIELD_BG    = THEME["beige"]      # "#EADFD2"
_BTN_BG      = THEME["accent"]     # "#8B5E3C"
_BTN_HOVER   = THEME["brown"]      # "#6B4B3A"


class LoginView(tk.Frame):
    """
    Landscape login card (820 × 460) centered on a warm brown gradient.

    ┌────────────────────────────┬──────────────────────┐
    │  Hero canvas  (54 %)       │  Login form  (46 %)  │
    │  Aissa's Kitchenette       │  Welcome Back        │
    │  Management System         │  ─────────────────   │
    │                            │  USERNAME            │
    │    [bouncing food image]   │  PASSWORD            │
    │         · · ·              │  SIGN IN ➤           │
    └────────────────────────────┴──────────────────────┘
    """

    def __init__(self, parent: tk.Widget, auth: AuthService,
                 on_success: Callable[[], None]) -> None:
        super().__init__(parent, bg=THEME["brown_dark"])
        self.auth       = auth
        self.on_success = on_success

        self._show_password  = False
        self._img_refs: list  = []    # permanent icon refs
        self._bg_refs:  list  = []    # bg-canvas image refs  (cleared on redraw)
        self._hero_refs: list = []    # hero-canvas image refs (cleared on redraw)

        # Food animation
        self._food_images: list             = []
        self._food_idx                      = 0
        self._food_after: Optional[int]     = None
        self._canvas_food_id: Optional[int] = None

        # Bounce
        self._bounce_after: Optional[int] = None
        self._bounce_y   = 0
        self._bounce_dir = -1
        self._food_cx    = 0
        self._food_cy    = 0

        # Dot indicators
        self._dot_ids: list[int] = []

        # Guard against duplicate hero redraws
        self._hero_rw = 0
        self._hero_rh = 0

        # Background resize debounce
        self._resize_job: Optional[int] = None
        self._last_w = 0
        self._last_h = 0

        self._build()
        self.after(100, self._initial_bg_draw)

    # ─────────────────────────────────────────────────────────────────────────
    # Build UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Full-screen canvas — warm brown gradient background
        self._bg = tk.Canvas(self, bg=THEME["brown_dark"], highlightthickness=0)
        self._bg.pack(fill=tk.BOTH, expand=True)
        self._bg.bind("<Configure>", self._on_bg_resize)

        # Landscape card floats above background, always centered
        self._card = self._build_card()
        self._card.place(relx=0.5, rely=0.5, anchor="center",
                         width=_CARD_W, height=_CARD_H)
        self._card.lift()

    def _build_card(self) -> tk.Frame:
        card = tk.Frame(self, bg=_CARD_BG, highlightthickness=0)

        left_w  = int(_CARD_W * _LEFT_FRAC)   # ~443 px
        right_w = _CARD_W - left_w - 1         # ~376 px

        # Three-column grid: hero | 1 px rule | form
        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=0)
        card.grid_columnconfigure(2, weight=1)
        card.grid_rowconfigure(0, weight=1)

        # ── Left: hero canvas ─────────────────────────────────────────────────
        self._hero = tk.Canvas(card, bg=THEME["brown"], highlightthickness=0,
                               width=left_w, height=_CARD_H)
        self._hero.grid(row=0, column=0, sticky="nsew")
        self._hero.bind("<Configure>", self._on_hero_configure)

        # Vertical separator
        tk.Frame(card, bg=_SEPARATOR, width=1,
                 highlightthickness=0).grid(row=0, column=1, sticky="ns")

        # ── Right: form panel ─────────────────────────────────────────────────
        right_panel = tk.Frame(card, bg=_CARD_BG, highlightthickness=0)
        right_panel.grid(row=0, column=2, sticky="nsew")

        self._build_form(right_panel, right_w)

        return card

    def _build_form(self, parent: tk.Frame, right_w: int) -> None:
        """
        All form widgets live in `inner`, which is placed at the vertical
        and horizontal center of the right panel — no top-heavy stacking.
        """
        form_w = right_w - 2 * _FORM_PADX     # usable content width ~304 px

        inner = tk.Frame(parent, bg=_CARD_BG, highlightthickness=0)
        inner.place(relx=0.5, rely=0.5, anchor="center", width=form_w)

        # ── Header ────────────────────────────────────────────────────────────
        tk.Label(inner, text="Welcome Back",
                 bg=_CARD_BG, fg=THEME["text"],
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(inner, text="Sign in to your account",
                 bg=_CARD_BG, fg=THEME["muted"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 24))

        # Icons
        self.icon_user    = self._load_icon("user.png",    18)
        self.icon_lock    = self._load_icon("lock.png",    18)
        self.icon_eye     = self._load_icon("eye.png",     18)
        self.icon_eye_off = self._load_icon("eye_off.png", 18)
        for ico in (self.icon_user, self.icon_lock, self.icon_eye, self.icon_eye_off):
            if ico:
                self._img_refs.append(ico)

        # ── Username ──────────────────────────────────────────────────────────
        tk.Label(inner, text="USERNAME",
                 bg=_CARD_BG, fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.username_var = tk.StringVar()
        user_row = tk.Frame(inner, bg=_FIELD_BG, highlightthickness=0)
        user_row.pack(fill=tk.X, pady=(5, 16))
        if self.icon_user:
            tk.Label(user_row, image=self.icon_user,
                     bg=_FIELD_BG).pack(side=tk.LEFT, padx=(12, 8), pady=10)
        else:
            tk.Label(user_row, text="\U0001f464",
                     bg=_FIELD_BG, fg=THEME["muted"],
                     font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(12, 8), pady=10)
        self.username_entry = tk.Entry(
            user_row, textvariable=self.username_var,
            bd=0, bg=_FIELD_BG, fg=THEME["text"],
            font=("Segoe UI", 10), insertbackground=THEME["text"])
        self.username_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                                 padx=(0, 12), pady=10)

        # ── Password ──────────────────────────────────────────────────────────
        tk.Label(inner, text="PASSWORD",
                 bg=_CARD_BG, fg=THEME["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.password_var = tk.StringVar()
        pass_row = tk.Frame(inner, bg=_FIELD_BG, highlightthickness=0)
        pass_row.pack(fill=tk.X, pady=(5, 24))
        if self.icon_lock:
            tk.Label(pass_row, image=self.icon_lock,
                     bg=_FIELD_BG).pack(side=tk.LEFT, padx=(12, 8), pady=10)
        else:
            tk.Label(pass_row, text="\U0001f512",
                     bg=_FIELD_BG, fg=THEME["muted"],
                     font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(12, 8), pady=10)
        self.password_entry = tk.Entry(
            pass_row, textvariable=self.password_var,
            bd=0, bg=_FIELD_BG, fg=THEME["text"],
            font=("Segoe UI", 10), show="\u2022",
            insertbackground=THEME["text"])
        self.password_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                                 padx=(0, 6), pady=10)
        self.eye_btn = tk.Button(
            pass_row,
            image=self.icon_eye_off if self.icon_eye_off else None,
            text="" if self.icon_eye_off else "\U0001f441",
            bd=0, bg=_FIELD_BG, activebackground=_FIELD_BG,
            cursor="hand2", command=self._toggle_password)
        self.eye_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # ── Sign In ───────────────────────────────────────────────────────────
        tk.Button(
            inner, text="SIGN IN",
            command=self._do_login,
            bg=_BTN_BG, fg="white",
            activebackground=_BTN_HOVER, activeforeground="white",
            bd=0, font=("Segoe UI", 10, "bold"), cursor="hand2"
        ).pack(fill=tk.X, ipady=11)

        self.username_entry.bind("<Return>", lambda e: self._do_login())
        self.password_entry.bind("<Return>", lambda e: self._do_login())
        self.after(50, self.username_entry.focus_set)

    # ─────────────────────────────────────────────────────────────────────────
    # Background canvas
    # ─────────────────────────────────────────────────────────────────────────

    def _initial_bg_draw(self) -> None:
        w = self._bg.winfo_width()
        h = self._bg.winfo_height()
        if w <= 1 or h <= 1:
            self.after(80, self._initial_bg_draw)
            return
        self._last_w, self._last_h = w, h
        self._paint_bg(w, h)

    def _on_bg_resize(self, event: tk.Event) -> None:
        w, h = event.width, event.height
        if w <= 1 or h <= 1:
            return
        if abs(w - self._last_w) < 4 and abs(h - self._last_h) < 4:
            return
        self._last_w, self._last_h = w, h
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(100, lambda: self._paint_bg(w, h))

    def _paint_bg(self, w: int, h: int) -> None:
        """Warm-brown gradient + soft card shadow on the background canvas."""
        self._bg.delete("all")
        self._bg_refs.clear()

        if not _HAS_PIL:
            return

        # ── Gradient ──────────────────────────────────────────────────────────
        try:
            top, mid, bot = _BG_TOP, _BG_MID, _BG_BOT
            strip = Image.new("RGB", (1, h))
            px    = strip.load()
            for y in range(h):
                t = y / max(h - 1, 1)
                if t <= 0.45:
                    r = t / 0.45
                    c = tuple(int(top[i] + (mid[i] - top[i]) * r) for i in range(3))
                else:
                    r = (t - 0.45) / 0.55
                    c = tuple(int(mid[i] + (bot[i] - mid[i]) * r) for i in range(3))
                px[0, y] = c
            photo = ImageTk.PhotoImage(strip.resize((w, h), Image.Resampling.NEAREST))
            self._bg_refs.append(photo)
            self._bg.create_image(0, 0, anchor="nw", image=photo)
        except Exception:
            pass

        # ── Soft card shadow ──────────────────────────────────────────────────
        self._paint_card_shadow(w, h)

    def _paint_card_shadow(self, w: int, h: int) -> None:
        """
        Gaussian-blurred shadow beneath the card for a subtle lift effect.
        Shadow is offset 5 px down to imply a light source from above.
        """
        if not _HAS_PIL or ImageFilter is None:
            return
        try:
            pad    = 28                           # blur radius + margin
            card_x = (w - _CARD_W) // 2
            card_y = (h - _CARD_H) // 2
            sw     = _CARD_W + pad * 2
            sh     = _CARD_H + pad * 2

            shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            core   = Image.new("RGBA", (_CARD_W, _CARD_H), (8, 3, 1, 155))
            shadow.paste(core, (pad, pad))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))

            photo = ImageTk.PhotoImage(shadow)
            self._bg_refs.append(photo)
            # Offset shadow 5 px downward for natural elevation look
            self._bg.create_image(card_x - pad, card_y - pad + 5,
                                  anchor="nw", image=photo)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Hero canvas  (branding + animated food, left side of card)
    # ─────────────────────────────────────────────────────────────────────────

    def _on_hero_configure(self, event: tk.Event) -> None:
        w, h = event.width, event.height
        if w <= 1 or h <= 1:
            return
        if w == self._hero_rw and h == self._hero_rh:
            return          # no size change — skip redraw
        self._hero_rw, self._hero_rh = w, h
        self._draw_hero(w, h)

    def _draw_hero(self, w: int, h: int) -> None:
        """Full repaint of the hero canvas."""
        self._hero.delete("all")
        self._hero_refs.clear()
        self._dot_ids.clear()
        self._stop_bounce()
        self._stop_food_timer()
        self._canvas_food_id = None

        cx = w // 2

        # ── Typography sizes ──────────────────────────────────────────────────
        title_size = max(18, min(22, int(h * 0.050)))
        sub_size   = max(10, min(13, int(h * 0.030)))
        title_ph   = int(title_size * 1.62)
        sub_ph     = int(sub_size   * 1.62)

        # ── Food image bounds ─────────────────────────────────────────────────
        # Up to 58 % of hero width and 52 % of hero height
        max_food_w = int(w * 0.58)
        max_food_h = int(h * 0.52)
        self._food_images = self._load_food_images(max_food_w, max_food_h)
        food_h = (self._food_images[0].height()
                  if self._food_images else int(h * 0.46))

        # ── Block layout (title → sub → line → food → dots), vertically centered
        GAP_TITLE_SUB = 5
        GAP_SUB_LINE  = 8
        LINE_H        = 1
        GAP_LINE_FOOD = 14
        GAP_FOOD_DOTS = 12
        DOT_H         = 12

        total_h = (title_ph + GAP_TITLE_SUB
                   + sub_ph + GAP_SUB_LINE + LINE_H + GAP_LINE_FOOD
                   + food_h + GAP_FOOD_DOTS + DOT_H)
        block_top = max(16, (h - total_h) // 2)

        y_title = block_top
        y_sub   = y_title + title_ph + GAP_TITLE_SUB
        y_line  = y_sub   + sub_ph   + GAP_SUB_LINE
        y_food  = y_line  + LINE_H   + GAP_LINE_FOOD
        y_dots  = y_food  + food_h   + GAP_FOOD_DOTS

        self._food_cx = cx
        self._food_cy = y_food + food_h // 2

        # ── Draw ──────────────────────────────────────────────────────────────
        self._paint_hero_gradient(w, h)

        # Title (1 px drop shadow)
        title_cy = y_title + title_ph // 2
        self._hero.create_text(cx + 1, title_cy + 1,
            text="Aissa's Kitchenette",
            font=("Segoe UI", title_size, "bold"),
            fill=_TITLE_SH, anchor="center")
        self._hero.create_text(cx, title_cy,
            text="Aissa's Kitchenette",
            font=("Segoe UI", title_size, "bold"),
            fill=_TITLE_FG, anchor="center")

        # Subtitle
        sub_cy = y_sub + sub_ph // 2
        self._hero.create_text(cx, sub_cy,
            text="Management System",
            font=("Segoe UI", sub_size, "italic"),
            fill=_SUBTITLE_FG, anchor="center")

        # Accent divider under subtitle
        line_hw = min(int(sub_size * 8), int(cx * 0.70))
        self._hero.create_line(cx - line_hw, y_line,
                               cx + line_hw, y_line,
                               fill=_DIVIDER_CLR, width=1)

        if self._food_images:
            self._build_dots(len(self._food_images), y_dots)
            self._show_food(self._food_idx)

    def _paint_hero_gradient(self, w: int, h: int) -> None:
        if not _HAS_PIL:
            return
        try:
            top, mid, bot = _HERO_TOP, _HERO_MID, _HERO_BOT
            strip = Image.new("RGB", (1, h))
            px    = strip.load()
            for y in range(h):
                t = y / max(h - 1, 1)
                if t <= 0.45:
                    r = t / 0.45
                    c = tuple(int(top[i] + (mid[i] - top[i]) * r) for i in range(3))
                else:
                    r = (t - 0.45) / 0.55
                    c = tuple(int(mid[i] + (bot[i] - mid[i]) * r) for i in range(3))
                px[0, y] = c
            photo = ImageTk.PhotoImage(strip.resize((w, h), Image.Resampling.NEAREST))
            self._hero_refs.append(photo)
            self._hero.create_image(0, 0, anchor="nw", image=photo)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Dot indicators
    # ─────────────────────────────────────────────────────────────────────────

    def _build_dots(self, count: int, y: int) -> None:
        gap   = 12
        total = (count - 1) * gap
        sx    = self._food_cx - total // 2
        for i in range(count):
            did = self._hero.create_text(
                sx + i * gap, y,
                text="\u25cf", font=("Segoe UI", 6),
                fill=_DOT_IDLE, anchor="center")
            self._dot_ids.append(did)

    def _update_dots(self, idx: int) -> None:
        for i, did in enumerate(self._dot_ids):
            self._hero.itemconfig(did,
                fill=_DOT_ACTIVE if i == idx else _DOT_IDLE)

    # ─────────────────────────────────────────────────────────────────────────
    # Food animation  (runs entirely on _hero canvas)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_food_images(self, max_w: int, max_h: int) -> list:
        login_dir = ASSETS_DIR / "login"
        images    = []
        if not _HAS_PIL or not login_dir.exists():
            return images
        for fname in _FOOD_FILES:
            p = login_dir / fname
            if not p.exists():
                continue
            try:
                img    = Image.open(p).convert("RGBA")
                ow, oh = img.size
                ratio  = min(max_w / max(ow, 1), max_h / max(oh, 1))
                img    = img.resize(
                    (max(1, int(ow * ratio)), max(1, int(oh * ratio))),
                    Image.Resampling.LANCZOS)
                images.append(ImageTk.PhotoImage(img))
            except Exception:
                continue
        return images

    def _show_food(self, idx: int) -> None:
        if not self._food_images:
            return
        idx            = idx % len(self._food_images)
        self._food_idx = idx
        photo          = self._food_images[idx]

        if self._canvas_food_id is None:
            self._canvas_food_id = self._hero.create_image(
                self._food_cx, self._food_cy,
                anchor="center", image=photo)
        else:
            self._hero.itemconfig(self._canvas_food_id, image=photo)
            self._hero.coords(
                self._canvas_food_id, self._food_cx, self._food_cy)

        self._update_dots(idx)

        self._stop_bounce()
        self._bounce_y   = 0
        self._bounce_dir = -1
        self._bounce_step()

        self._food_after = self.after(
            _FOOD_INTERVAL_MS,
            lambda: self._show_food(self._food_idx + 1))

    def _stop_food_timer(self) -> None:
        if self._food_after is not None:
            try:
                self.after_cancel(self._food_after)
            except Exception:
                pass
            self._food_after = None

    def _stop_bounce(self) -> None:
        if self._bounce_after is not None:
            try:
                self.after_cancel(self._bounce_after)
            except Exception:
                pass
            self._bounce_after = None

    def _bounce_step(self) -> None:
        if self._canvas_food_id is None:
            return
        try:
            if not self._hero.winfo_exists():
                return
        except Exception:
            return

        self._bounce_y += self._bounce_dir
        if abs(self._bounce_y) >= _BOUNCE_AMPLITUDE:
            self._bounce_dir *= -1

        try:
            self._hero.coords(
                self._canvas_food_id,
                self._food_cx,
                self._food_cy + self._bounce_y)
        except Exception:
            return

        self._bounce_after = self.after(_BOUNCE_STEP_MS, self._bounce_step)

    # ─────────────────────────────────────────────────────────────────────────
    # Auth
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_password(self) -> None:
        self._show_password = not self._show_password
        self.password_entry.config(show="" if self._show_password else "\u2022")
        if self.icon_eye and self.icon_eye_off:
            self.eye_btn.config(
                image=self.icon_eye if self._show_password else self.icon_eye_off)

    def _do_login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            messagebox.showerror("Login", "Please enter username and password.")
            return
        if self.auth.login(username, password):
            self._stop_animations()
            self.on_success()
        else:
            messagebox.showerror(
                "Login failed", self.auth.get_last_error() or "Login failed.")

    def _stop_animations(self) -> None:
        self._stop_bounce()
        self._stop_food_timer()

    # ─────────────────────────────────────────────────────────────────────────
    # Asset loaders
    # ─────────────────────────────────────────────────────────────────────────

    def _load_icon(self, filename: str, size: int):
        path = ICONS_DIR / filename
        if not path.exists() or not _HAS_PIL:
            return None
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None
