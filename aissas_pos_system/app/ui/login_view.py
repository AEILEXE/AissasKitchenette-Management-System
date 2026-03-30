from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from app.config import THEME, LOGO_PATH, ICONS_DIR, ASSETS_DIR
from app.services.auth_service import AuthService

# Pillow is required for proper image handling
try:
    from PIL import Image, ImageTk  # type: ignore
    _HAS_PIL = True
except Exception:
    Image = None
    ImageTk = None
    _HAS_PIL = False

# Slideshow timing
_SLIDE_INTERVAL_MS = 10_000   # 10 seconds between slides
_BOUNCE_AMPLITUDE  = 6        # pixels up/down for bounce
_BOUNCE_STEP_MS    = 40       # animation frame interval (~25 fps)


class LoginView(tk.Frame):
    def __init__(self, parent: tk.Widget, auth: AuthService, on_success: Callable[[], None]):
        super().__init__(parent, bg=THEME["bg"])
        self.auth       = auth
        self.on_success = on_success

        self._show_password = False
        self._img_refs: list[tk.PhotoImage] = []  # prevent GC

        # Slideshow state
        self._slide_images: list[tk.PhotoImage] = []
        self._slide_idx    = 0
        self._slide_after: Optional[int] = None

        # Bounce state
        self._bounce_after: Optional[int]  = None
        self._bounce_y     = 0
        self._bounce_dir   = -1  # -1 = up, +1 = down

        self._build()
        # Start slideshow after window is mapped
        self.after(100, self._start_slideshow)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        # Center container
        outer = tk.Frame(self, bg=THEME["bg"])
        outer.pack(expand=True)

        card = tk.Frame(outer, bg=THEME["panel"], bd=1, relief=tk.FLAT)
        card.grid(row=0, column=0, padx=20, pady=20)

        # ── Left panel — slideshow background ────────────────────────────────
        self._left = tk.Frame(card, bg=THEME["brown"], width=440, height=480)
        self._left.grid(row=0, column=0, sticky="nsew")
        self._left.grid_propagate(False)

        # Background label (fills left panel)
        self._bg_lbl = tk.Label(self._left, bg=THEME["brown"])
        self._bg_lbl.place(x=0, y=0, relwidth=1, relheight=1)

        # Overlay — brand text centred, always visible on top of background
        overlay = tk.Frame(self._left, bg="")
        overlay.place(relx=0.5, rely=0.5, anchor="center")

        # Logo with bounce
        self._logo_lbl: Optional[tk.Label] = None
        logo_img = self._load_logo(90)
        if logo_img:
            self._logo_lbl = tk.Label(
                overlay, image=logo_img, bg=THEME["brown"],
            )
            self._logo_lbl.pack(pady=(0, 10))
            self._img_refs.append(logo_img)
        else:
            tk.Label(overlay, text="🍽", bg=THEME["brown"],
                     font=("Segoe UI", 36)).pack(pady=(0, 10))

        tk.Label(
            overlay,
            text="Aissa's Kitchenette",
            bg=THEME["brown"],
            fg="white",
            font=("Segoe UI", 20, "bold"),
        ).pack()

        tk.Label(
            overlay,
            text="Management System",
            bg=THEME["brown"],
            fg="#F2E9E0",
            font=("Segoe UI", 10),
        ).pack(pady=(4, 0))

        # Slide indicator dots
        self._dot_frame = tk.Frame(self._left, bg="")
        self._dot_frame.place(relx=0.5, rely=0.92, anchor="center")
        self._dot_labels: list[tk.Label] = []

        # ── Right panel — login form ──────────────────────────────────────────
        right = tk.Frame(card, bg=THEME["panel"], width=480, height=480)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)

        tk.Label(
            right,
            text="Welcome Back",
            bg=THEME["panel"],
            fg=THEME["text"],
            font=("Segoe UI", 22, "bold"),
        ).place(x=52, y=70)

        tk.Label(
            right,
            text="Sign in to your account",
            bg=THEME["panel"],
            fg=THEME["muted"],
            font=("Segoe UI", 10),
        ).place(x=54, y=110)

        # Icons
        self.icon_user    = self._load_icon("user.png",    18)
        self.icon_lock    = self._load_icon("lock.png",    18)
        self.icon_eye     = self._load_icon("eye.png",     18)
        self.icon_eye_off = self._load_icon("eye_off.png", 18)

        # Username
        tk.Label(right, text="USERNAME", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 9, "bold")).place(x=54, y=160)

        self.username_var = tk.StringVar()
        user_row = tk.Frame(right, bg=THEME["panel2"])
        user_row.place(x=54, y=184, width=370, height=42)

        if self.icon_user:
            tk.Label(user_row, image=self.icon_user, bg=THEME["panel2"]).pack(side=tk.LEFT, padx=10)
            self._img_refs.append(self.icon_user)
        else:
            tk.Label(user_row, text="👤", bg=THEME["panel2"], fg=THEME["muted"],
                     font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=10)

        self.username_entry = tk.Entry(
            user_row, textvariable=self.username_var,
            bd=0, bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 11),
        )
        self.username_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Password
        tk.Label(right, text="PASSWORD", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 9, "bold")).place(x=54, y=244)

        self.password_var = tk.StringVar()
        pass_row = tk.Frame(right, bg=THEME["panel2"])
        pass_row.place(x=54, y=268, width=370, height=42)

        if self.icon_lock:
            tk.Label(pass_row, image=self.icon_lock, bg=THEME["panel2"]).pack(side=tk.LEFT, padx=10)
            self._img_refs.append(self.icon_lock)
        else:
            tk.Label(pass_row, text="🔒", bg=THEME["panel2"], fg=THEME["muted"],
                     font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=10)

        self.password_entry = tk.Entry(
            pass_row, textvariable=self.password_var,
            bd=0, bg=THEME["panel2"], fg=THEME["text"],
            font=("Segoe UI", 11), show="•",
        )
        self.password_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        eye_img = self.icon_eye_off if self.icon_eye_off else None
        self.eye_btn = tk.Button(
            pass_row, image=eye_img, text="" if eye_img else "👁",
            bd=0, bg=THEME["panel2"], activebackground=THEME["panel2"],
            cursor="hand2", command=self._toggle_password,
        )
        self.eye_btn.pack(side=tk.RIGHT, padx=10)
        if self.icon_eye_off:
            self._img_refs.append(self.icon_eye_off)
        if self.icon_eye:
            self._img_refs.append(self.icon_eye)

        # Sign In button
        tk.Button(
            right, text="SIGN IN  ➜",
            command=self._do_login,
            bg=THEME["brown2"], fg="white",
            activebackground=THEME["brown"], activeforeground="white",
            bd=0, font=("Segoe UI", 11, "bold"), cursor="hand2",
        ).place(x=54, y=336, width=370, height=46)

        # Enter key
        self.username_entry.bind("<Return>", lambda e: self._do_login())
        self.password_entry.bind("<Return>", lambda e: self._do_login())
        self.after(50, self.username_entry.focus_set)

    # ── Slideshow ─────────────────────────────────────────────────────────────

    def _load_slide_images(self) -> list[tk.PhotoImage]:
        """Load all login/ images, resized to 440×480 for the left panel."""
        login_dir = ASSETS_DIR / "login"
        images: list[tk.PhotoImage] = []
        if not _HAS_PIL or not login_dir.exists():
            return images

        for i in range(1, 10):   # try 1.png … 9.png
            p = login_dir / f"{i}.png"
            if not p.exists():
                break
            try:
                img = Image.open(p).convert("RGB")
                img = img.resize((440, 480), Image.Resampling.LANCZOS)
                images.append(ImageTk.PhotoImage(img))
            except Exception:
                continue
        return images

    def _build_dots(self, count: int) -> None:
        for w in self._dot_frame.winfo_children():
            w.destroy()
        self._dot_labels.clear()
        for i in range(count):
            lbl = tk.Label(
                self._dot_frame, text="●",
                bg="", fg="white" if i == 0 else "#ffffff66",
                font=("Segoe UI", 8),
            )
            lbl.pack(side="left", padx=2)
            self._dot_labels.append(lbl)

    def _update_dots(self, idx: int) -> None:
        for i, lbl in enumerate(self._dot_labels):
            lbl.configure(fg="white" if i == idx else "#ffffff66")

    def _start_slideshow(self) -> None:
        self._slide_images = self._load_slide_images()
        if not self._slide_images:
            # No images — keep solid brown background and start bounce only
            self._start_bounce()
            return

        self._build_dots(len(self._slide_images))
        self._show_slide(0)
        self._start_bounce()

    def _show_slide(self, idx: int) -> None:
        if not self._slide_images:
            return
        idx = idx % len(self._slide_images)
        self._slide_idx = idx
        self._bg_lbl.configure(image=self._slide_images[idx])
        self._update_dots(idx)
        # Reschedule next slide
        if self._slide_after is not None:
            try:
                self.after_cancel(self._slide_after)
            except Exception:
                pass
        self._slide_after = self.after(
            _SLIDE_INTERVAL_MS,
            lambda: self._show_slide(self._slide_idx + 1),
        )

    # ── Bounce animation ──────────────────────────────────────────────────────

    def _start_bounce(self) -> None:
        if self._logo_lbl is None:
            return
        self._bounce_y   = 0
        self._bounce_dir = -1
        self._bounce_step()

    def _bounce_step(self) -> None:
        if self._logo_lbl is None or not self._logo_lbl.winfo_exists():
            return
        self._bounce_y += self._bounce_dir
        if abs(self._bounce_y) >= _BOUNCE_AMPLITUDE:
            self._bounce_dir *= -1
        # Move logo label by adjusting its y via place — it's inside an `overlay` Frame
        # which is packed. We nudge it using a padx trick via pack pady instead.
        # Safest approach: use the label's own pady to simulate vertical shift.
        try:
            top_pad = max(0, _BOUNCE_AMPLITUDE + self._bounce_y)
            bot_pad = max(0, _BOUNCE_AMPLITUDE - self._bounce_y)
            self._logo_lbl.pack_configure(pady=(top_pad, bot_pad))
        except Exception:
            return
        self._bounce_after = self.after(_BOUNCE_STEP_MS, self._bounce_step)

    # ── Auth helpers ──────────────────────────────────────────────────────────

    def _toggle_password(self) -> None:
        self._show_password = not self._show_password
        self.password_entry.config(show="" if self._show_password else "•")
        if self.icon_eye and self.icon_eye_off:
            self.eye_btn.config(
                image=self.icon_eye if self._show_password else self.icon_eye_off,
            )

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
            messagebox.showerror("Login failed", self.auth.get_last_error() or "Login failed.")

    def _stop_animations(self) -> None:
        """Cancel all pending after() callbacks before navigating away."""
        for attr in ("_slide_after", "_bounce_after"):
            aid = getattr(self, attr, None)
            if aid is not None:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
            setattr(self, attr, None)

    # ── Asset loaders ─────────────────────────────────────────────────────────

    def _load_icon(self, filename: str, size: int) -> Optional[tk.PhotoImage]:
        path = ICONS_DIR / filename
        if not path.exists():
            return None
        if _HAS_PIL:
            try:
                img = Image.open(path).convert("RGBA")
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception:
                return None
        return None

    def _load_logo(self, size: int) -> Optional[tk.PhotoImage]:
        try:
            if _HAS_PIL and LOGO_PATH.exists():
                img = Image.open(LOGO_PATH)
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception:
            pass
        return None
