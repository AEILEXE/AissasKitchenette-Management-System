from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from app.config import THEME, LOGO_PATH, ICONS_DIR
from app.services.auth_service import AuthService

# Pillow is recommended (proper icon scaling)
try:
    from PIL import Image, ImageTk  # type: ignore
except Exception:
    Image = None
    ImageTk = None


class LoginView(tk.Frame):
    def __init__(self, parent: tk.Widget, auth: AuthService, on_success: Callable[[], None]):
        super().__init__(parent, bg=THEME["bg"])
        self.auth = auth
        self.on_success = on_success

        self._show_password = False
        self._img_refs: list[tk.PhotoImage] = []  # keep references

        # Center container
        outer = tk.Frame(self, bg=THEME["bg"])
        outer.pack(expand=True)

        card = tk.Frame(outer, bg=THEME["panel"], bd=1, relief=tk.FLAT)
        card.grid(row=0, column=0, padx=20, pady=20)

        # Left panel
        left = tk.Frame(card, bg=THEME["brown"], width=420, height=460)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)

        # Right panel
        right = tk.Frame(card, bg=THEME["panel"], width=480, height=460)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)

        # ---- LEFT CONTENT ----
        left_inner = tk.Frame(left, bg=THEME["brown"])
        left_inner.place(relx=0.5, rely=0.5, anchor="center")

        logo = self._load_logo(120)
        if logo:
            tk.Label(left_inner, image=logo, bg=THEME["brown"]).pack(pady=(0, 16))
            self._img_refs.append(logo)
        else:
            tk.Label(left_inner, text="LOGO", bg=THEME["brown"], fg="white",
                     font=("Segoe UI", 18, "bold")).pack(pady=(0, 16))

        tk.Label(
            left_inner,
            text="Alissa's Kitchenette",
            bg=THEME["brown"],
            fg="white",
            font=("Segoe UI", 22, "bold"),
        ).pack()

        tk.Label(
            left_inner,
            text="Management System",
            bg=THEME["brown"],
            fg="#F2E9E0",
            font=("Segoe UI", 11),
        ).pack(pady=(6, 0))

        # ---- RIGHT CONTENT ----
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

        # Load icons (18x18)
        self.icon_user = self._load_icon("user.png", 18)
        self.icon_lock = self._load_icon("lock.png", 18)
        self.icon_eye = self._load_icon("eye.png", 18)
        self.icon_eye_off = self._load_icon("eye_off.png", 18)

        # Username label + field
        tk.Label(right, text="USERNAME", bg=THEME["panel"], fg=THEME["text"],
                 font=("Segoe UI", 9, "bold")).place(x=54, y=160)

        self.username_var = tk.StringVar()
        user_row = tk.Frame(right, bg=THEME["panel2"])
        user_row.place(x=54, y=184, width=370, height=42)

        if self.icon_user:
            tk.Label(user_row, image=self.icon_user, bg=THEME["panel2"]).pack(side=tk.LEFT, padx=10)
            self._img_refs.append(self.icon_user)
        else:
            # Fallback if icon missing
            tk.Label(user_row, text="👤", bg=THEME["panel2"], fg=THEME["muted"],
                     font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=10)

        self.username_entry = tk.Entry(
            user_row,
            textvariable=self.username_var,
            bd=0,
            bg=THEME["panel2"],
            fg=THEME["text"],
            font=("Segoe UI", 11),
        )
        self.username_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Password label + field
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
            pass_row,
            textvariable=self.password_var,
            bd=0,
            bg=THEME["panel2"],
            fg=THEME["text"],
            font=("Segoe UI", 11),
            show="•",
        )
        self.password_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        # Eye toggle button
        eye_img = self.icon_eye_off if self.icon_eye_off else None
        self.eye_btn = tk.Button(
            pass_row,
            image=eye_img,
            text="" if eye_img else "👁",
            bd=0,
            bg=THEME["panel2"],
            activebackground=THEME["panel2"],
            cursor="hand2",
            command=self._toggle_password,
        )
        self.eye_btn.pack(side=tk.RIGHT, padx=10)

        if self.icon_eye_off:
            self._img_refs.append(self.icon_eye_off)
        if self.icon_eye:
            self._img_refs.append(self.icon_eye)

        # Sign in button
        tk.Button(
            right,
            text="SIGN IN  ➜",
            command=self._do_login,
            bg=THEME["brown2"],
            fg="white",
            activebackground=THEME["brown"],
            activeforeground="white",
            bd=0,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        ).place(x=54, y=336, width=370, height=46)

        # Enter key
        self.username_entry.bind("<Return>", lambda e: self._do_login())
        self.password_entry.bind("<Return>", lambda e: self._do_login())

        self.after(50, self.username_entry.focus_set)

    def _toggle_password(self) -> None:
        self._show_password = not self._show_password
        self.password_entry.config(show="" if self._show_password else "•")
        if self.icon_eye and self.icon_eye_off:
            self.eye_btn.config(image=self.icon_eye if self._show_password else self.icon_eye_off)

    def _do_login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()

        if not username or not password:
            messagebox.showerror("Login", "Please enter username and password.")
            return

        if self.auth.login(username, password):
            self.on_success()
        else:
            messagebox.showerror("Login failed", self.auth.get_last_error() or "Login failed.")

    def _load_icon(self, filename: str, size: int) -> Optional[tk.PhotoImage]:
        path = ICONS_DIR / filename
        if not path.exists():
            return None

        # Best: Pillow resize (icons will ALWAYS appear correctly)
        if Image and ImageTk:
            try:
                img = Image.open(path).convert("RGBA")
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception:
                return None

        # If Pillow not installed, Tkinter cannot properly scale big icons.
        # Returning None forces emoji fallback above, instead of “invisible” icons.
        return None

    def _load_logo(self, size: int) -> Optional[tk.PhotoImage]:
        try:
            if Image and ImageTk and LOGO_PATH.exists():
                img = Image.open(LOGO_PATH)
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception:
            return None
        return None
