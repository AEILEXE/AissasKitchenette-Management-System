# Aissa's Kitchenette Management System

A standalone desktop **Point-of-Sale and Inventory Management System** for a small food service business. Built entirely with **Python 3 + Tkinter**. No internet connection required. All data is stored locally with SQLite.

> **Current release: v1.0.0-beta.2**

---

## What's Updated — v1.0.0-beta.2

### POS UI — Resize & Layout
- Fixed product grid breaking when the window is maximized or restored (wrong width was used for column calculation).
- Layout now recomputes only after the window has fully settled, preventing unstable intermediate states.
- Debounce delay increased to prevent re-layout on every intermediate `<Configure>` event during maximize/restore.
- `_prod_canvas_w` is now set unconditionally from the real event width — no longer skips updates on small values.

### POS UI — Flicker on Screen Open
- Removed forced `update_idletasks()` calls inside the per-batch card render path.
- Product cards now render in one clean pass instead of repainting after every 6 items.
- `update_idletasks()` retained only in the resize path (`_relayout_products`) where a single forced commit is correct.

### POS UI — Resize Width Measurement
- Replaced `winfo_width()` with `_prod_canvas_w` (event-sourced) inside `_calc_product_cols()` to prevent reading stale pre-resize geometry.
- Added `< 300` guard to skip layout when canvas width is not yet valid.

---

## 1. Project Overview

Aissa's Kitchenette Management System is an offline-first POS desktop application covering the full sales cycle: product selection, cart management, checkout, receipt generation, inventory tracking, sales reporting, and user management — packaged as a single Windows EXE that requires no Python installation on the target machine.

### Key Features

| Module | Description |
|--------|-------------|
| **User Auth & RBAC** | Login system with three roles: ADMIN, MANAGER, CLERK. Per-role permissions are configurable by admin at runtime. |
| **Point of Sale** | Product grid with category filter and live search. Clickable product cards with stock indicators. Cart with quantity controls. |
| **Discounts** | Apply a peso-amount or percentage discount to the entire order before checkout. |
| **Checkout** | Cash (live change calculation) or Bank/E-Wallet (saved as Pending). Atomic DB write — stock deducted and order saved in one transaction. |
| **Draft Orders** | Save an in-progress cart as a named draft (e.g. "Table 3"). Reload and resume later. Drafts do not affect stock. |
| **Receipts** | PDF thermal receipt via `reportlab`. Receipts are saved to the `receipts/` folder automatically on every checkout. |
| **Inventory** | Products CRUD, category management, stock tracking, low-stock indicators. Product image upload and preview. |
| **Transactions** | Full order history with search by ID, filter by status / payment / date range. View line items, reprint receipt, resolve pending orders, cancel orders. |
| **Sales Reports** | Bar charts (Daily / Monthly / Yearly), KPI summary cards. Export to PDF or Excel. |
| **ML Suggestions** | Offline co-purchase recommender suggests upsell items based on past order history. Pure Python — no external ML libraries. |
| **Settings** | Password change (12-char policy), DB backup/restore, user management, role permission toggles, demo sales seeder. |
| **Offline-first** | Zero network calls. Works completely without internet. |

---

## 2. Requirements

### For end users (EXE / installer)

- **Windows 10 or Windows 11** (64-bit)
- No Python installation required — everything is bundled in the EXE.

### For developers (source / dev mode)

- **Python 3.10 or newer** (uses `X | Y` union type syntax)
- **Windows 10/11** recommended (primary development platform, Segoe UI fonts)
- macOS and Linux work; system font substitution is automatic. Linux requires `python3-tk` from the OS package manager.

### Python dependencies

Install all at once:
```bash
pip install -r aissas_pos_system/requirements.txt
```

| Library | Version | What it does in this project |
|---------|---------|-------------------------------|
| **Pillow** | `>=9.0.0` | Image loading and resizing for product card thumbnails, login slideshow images, and logo rendering. Also generates the multi-size `.ico` file via `make_icon.py`. |
| **matplotlib** | `>=3.5.0` | Renders the bar charts on the Sales Reports tab (Daily / Monthly / Yearly). The chart is embedded directly in the Tkinter window using `FigureCanvasTkAgg`. |
| **reportlab** | `>=3.5.0` | Generates PDF thermal receipts after each successful checkout. Uses DejaVuSans font (bundled in `assets/fonts/`) for correct ₱ peso sign rendering. |
| **openpyxl** | `>=3.0.0` | Exports sales report data to `.xlsx` Excel files from the Reports tab. |

**For building the EXE only** (not required to run in dev mode):

| Library | What it does |
|---------|-------------|
| **pyinstaller** | Packages the entire Python application — source, interpreter, and dependencies — into a single `AissasKitchenette.exe` that runs on Windows without Python installed. |
| **pyinstaller-hooks-contrib** | Provides ready-made hook scripts that tell PyInstaller which hidden files Pillow, matplotlib, and reportlab need at runtime (fonts, backends, plugins) so nothing is accidentally excluded from the bundle. |

```bash
pip install pyinstaller pyinstaller-hooks-contrib
```

---

## 3. Installation (For End Users)

This is the recommended way to install the application on a Windows PC. No Python or technical knowledge required.

### Step 1 — Run the installer

Double-click `AissasKitchenette_Setup.exe`.

The setup wizard will guide you through:
- Choosing whether to create a desktop shortcut (checked by default)
- Installing to `C:\Users\<YourName>\AppData\Local\Programs\AissasKitchenette` (no admin rights required)

### Step 2 — Launch the app

After installation, launch via:
- The **desktop shortcut** (if created during setup), or
- **Start Menu → Aissa's Kitchenette → Aissa's Kitchenette**

### Step 3 — Log in

Use the default credentials on first launch:

| Username | Password |
|----------|----------|
| `admin` | `admin123` |

**Change the default password immediately** via Settings → Security.

### Uninstalling

Go to **Settings → Apps** (Windows) or **Control Panel → Programs and Features**, find "Aissa's Kitchenette", and uninstall. The uninstaller also removes the data, receipts, exports, and product image folders from the install directory.

---

## 4. How to Run (Dev Mode)

### Step 1 — Clone the repository

```bash
git clone <repo-url>
cd AissasKitchenette-Management-System
```

### Step 2 — Create and activate a virtual environment

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate.bat

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install --upgrade pip
pip install -r aissas_pos_system/requirements.txt
```

### Step 4 — Run

From the project root with the venv active:

```bash
cd aissas_pos_system
python main.py
```

On first run the system will:
1. Create the `data/pos.db` SQLite database
2. Seed the default admin user (`admin` / `admin123`)
3. Seed the default product menu (categories + sample items)

---

## 5. Building the EXE

### Prerequisites

```bash
pip install pyinstaller pyinstaller-hooks-contrib
```

Inno Setup 6 must be installed for the installer step (see Section 6).

### One-command build (recommended)

From inside `aissas_pos_system/`:

```bash
build.bat
```

`build.bat` performs three steps in order:

1. **Generate icon** — runs `python make_icon.py` to convert `assets/logo.jpg` → `assets/logo.ico` (multi-size ICO file required by Windows).
2. **Build EXE** — runs `pyinstaller --clean main.spec`, producing `dist/AissasKitchenette.exe` (single self-contained file, no Python needed).
3. **Build installer** — runs Inno Setup to produce `dist/AissasKitchenette_Setup.exe`. If Inno Setup is not found, this step is skipped with a warning.

### Manual build (step by step)

```bash
cd aissas_pos_system

# Step 1: generate the icon
python make_icon.py

# Step 2: build the EXE
pyinstaller --clean main.spec

# The EXE is at: dist/AissasKitchenette.exe
```

### Notes on the spec file (`main.spec`)

- Bundles `assets/` and `product_images/` as read-only data inside the EXE.
- Comprehensive `hiddenimports` for Pillow, reportlab, matplotlib, openpyxl.
- `console=False` — no terminal window.
- `icon='assets/logo.ico'` — sets the EXE and taskbar icon.

---

## 6. Installer Creation

The installer is built with **Inno Setup 6** using `installer.iss`.

### Install Inno Setup 6

Download from: https://jrsoftware.org/isdl.php

### Build the installer

```bash
# From aissas_pos_system/ — if Inno Setup is in the default location:
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

# Or just run the full build script which does this automatically:
build.bat
```

Output: `dist/AissasKitchenette_Setup.exe`

### Installer features

- Installs to `{localappdata}\Programs\AissasKitchenette` — **no admin rights required**
- Creates Start Menu shortcuts and optional desktop shortcut
- Offers to launch the app immediately after install
- Uninstaller removes all app data folders from the install directory

---

## 7. Project Structure

```
AissasKitchenette-Management-System/
├── README.md                        ← this file
└── aissas_pos_system/               ← main application package
    ├── main.py                      ← entry point; EXE bootstrap + window init
    ├── main.spec                    ← PyInstaller spec (use this to build EXE)
    ├── build.bat                    ← one-command build: icon → EXE → installer
    ├── make_icon.py                 ← converts assets/logo.jpg → assets/logo.ico
    ├── installer.iss                ← Inno Setup 6 installer script
    ├── requirements.txt             ← Python dependencies
    ├── assets/                      ← read-only bundled assets (inside EXE)
    │   ├── logo.jpg                 ← source logo (used for branding)
    │   ├── logo.ico                 ← generated icon (run make_icon.py first)
    │   ├── fonts/                   ← TTF fonts for PDF receipts (DejaVuSans)
    │   └── icons/                   ← UI icon images
    ├── product_images/              ← default/placeholder product images
    └── app/                         ← application source code
        ├── config.py                ← paths, theme colours, EXE path resolution
        ├── constants.py             ← roles, permission keys, messages
        ├── utils.py                 ← password hashing, money formatter
        ├── validators.py            ← input validation helpers
        ├── db/                      ← data layer
        │   ├── database.py          ← SQLite connection, schema init, WAL mode
        │   ├── dao.py               ← DAO classes for each table
        │   ├── schema.py            ← CREATE TABLE / INDEX statements
        │   ├── seed_menu.py         ← initial product + category seed
        │   ├── seed_sales.py        ← demo sales data seeder
        │   └── seed_users.py        ← default admin user seed
        ├── ml/                      ← offline ML recommender
        │   └── recommender.py       ← co-purchase pair-frequency engine
        ├── models/                  ← lightweight data model classes
        ├── services/                ← business logic layer
        │   ├── auth_service.py      ← login, logout, RBAC, password policy
        │   ├── pos_service.py       ← order creation, stock deduction, drafts
        │   ├── receipt_service.py   ← PDF receipt generation (reportlab)
        │   ├── export_service.py    ← CSV / Excel export
        │   └── report_service.py    ← report data aggregation
        └── ui/                      ← Tkinter views and dialogs
            ├── app_window.py        ← main window shell + sidebar navigation
            ├── login_view.py        ← login screen
            ├── pos_view.py          ← POS screen, cart, checkout dialog
            ├── transactions_view.py ← transaction history + details dialog
            ├── inventory_products_view.py ← products CRUD table
            ├── inventory_sales_view.py    ← sales charts (matplotlib)
            ├── account_settings_view.py   ← settings (profile, security, users, RBAC)
            └── dialogs.py           ← shared dialogs (discount, draft, text input)
```

**Runtime directories created automatically on first launch:**

| Directory | Contents |
|-----------|----------|
| `data/` | SQLite database (`pos.db`) |
| `receipts/` | Generated PDF receipts |
| `exports/` | CSV / Excel / PDF exports |
| `product_images/` | User-uploaded product images |
| `mpl_config/` | matplotlib cache (EXE mode only) |

---

## 8. How the System Works

### Login

1. User enters username + password → `AuthService.login()` verifies against the hashed password in the DB.
2. Role is loaded; the sidebar shows only modules the role is permitted to access.

### POS flow

1. Cashier selects a category filter or types in the live search box.
2. Clicking a product card adds it to the cart. Out-of-stock products show "Not Available" and cannot be added.
3. Adjust quantities with `+` / `−` in the cart, or remove items individually.
4. Optionally apply an order-level discount (peso amount or percentage).
5. Optionally save the current cart as a named **Draft** for later.
6. Click **Checkout** → the confirmation dialog opens:
   - Enter customer name (required).
   - Choose payment: **Cash** (enter amount paid; change is calculated live) or **Bank/E-Wallet** (saved as Pending).
   - Click **Confirm Checkout** → order + all stock deductions are saved atomically in a single DB transaction. Receipt PDF is generated immediately.

### Checkout atomicity

The entire checkout — order record, all line items, and all stock deductions — is written in a single SQLite transaction. If anything fails (e.g. a product goes out of stock between cart load and confirm), the whole transaction is rolled back and the DB is left unchanged.

### Draft orders

- **Save:** cart items + discount are serialised to JSON in the `drafts` table.
- **Load:** stored cart is restored and the draft record is deleted.
- Drafts do **not** affect stock — only actual checkouts deduct stock.

### Payment states

| Payment | Order status | What happens |
|---------|-------------|--------------|
| Cash | `Completed` | Change calculated; stock deducted; receipt saved. |
| Bank/E-Wallet | `Pending` | Order recorded; stock deducted; cashier resolves later from Transactions. |

### Resolving pending orders

**Transactions → select order → View Details → Resolve** — enter the reference number and amount received. Order status moves to `Completed`.

### Stock management

- Each product has a `stock` quantity tracked in the DB.
- Both Cash and Bank/E-Wallet checkouts deduct stock immediately.
- Products reaching `stock = 0` appear as "Not Available" on the POS.
- Stock is manually adjusted via **Inventory → Products → Edit**.
- Cancelling an order via the Transactions screen does **not** automatically restore stock — adjust manually in Inventory if needed.

### Receipts

- Generated immediately after every successful checkout.
- Saved as PDF using `reportlab`. If `reportlab` is unavailable a `.txt` fallback is created.
- Font: DejaVuSans (bundled in `assets/fonts/`) for proper Philippine Peso sign (₱). Falls back to Helvetica with "PHP" prefix if the font cannot be loaded.

### Dashboard

- Opens at the **Overview** tab inside the Inventory/Dashboard module.
- Displays KPI summary cards (today + month totals), then **Top Sellers — Today** (ranked by qty sold), then **Recent Transactions** (latest 10 orders), then Quick Actions.
- Click **Refresh** to reload all data from the DB.

### Sales reports

- Daily / Monthly / Yearly bar charts built with matplotlib.
- KPI cards: Total Sales, Total Orders, Average Order Value.
- Export to PDF (chart + summary) or Excel (raw data).

### ML suggestions

- Offline co-purchase recommender trained on completed orders.
- Suggests up to 5 items frequently bought together with the current cart, displayed in rows of up to 3.
- Out-of-stock suggestions are automatically hidden.
- No external libraries; pure Python frequency-pair counting.
- Requires existing sales history to produce suggestions. Use **Settings → Seed Demo Sales** to generate test data.

---

## 9. Data & File Storage

### In dev mode (running `python main.py`)

All writable data is stored in the **project root** (the folder containing `aissas_pos_system/`):

| Path | Contents |
|------|----------|
| `data/pos.db` | SQLite database |
| `receipts/` | PDF receipts |
| `exports/` | Exported files |
| `product_images/` | Uploaded product images |

### In EXE mode (installed or running `AissasKitchenette.exe` directly)

All writable data is stored **next to the EXE**, which in the installed version is:

```
C:\Users\<YourName>\AppData\Local\Programs\AissasKitchenette\
├── AissasKitchenette.exe
├── data\
│   └── pos.db              ← database
├── receipts\               ← PDF receipts
├── exports\                ← exported files
├── product_images\         ← uploaded product images
├── mpl_config\             ← matplotlib cache (auto-created)
└── app.log                 ← crash/error log (auto-created on error)
```

The bundled read-only assets (fonts, icons, logo) are extracted to a temporary directory by PyInstaller when the EXE runs, and cleaned up on exit. Your data is never stored in that temporary location.

### Database backup and restore

- **Export:** Settings → Database → Export Database — saves a copy of `pos.db` anywhere you choose.
- **Import:** Settings → Database → Import Database — replaces the live DB with a backup file. Requires password confirmation. The app keeps working after import without requiring a restart.

---

## 10. Troubleshooting

### EXE does not open / crashes silently

The EXE runs without a console window. Errors are written to `app.log` in the same folder as the EXE.

1. Open `C:\Users\<YourName>\AppData\Local\Programs\AissasKitchenette\app.log` in Notepad.
2. The log contains timestamps and full exception tracebacks for any crash.

### App opens but immediately closes

Check `app.log` (see above). Common causes:
- Corrupted database — delete `data\pos.db` and relaunch. A fresh DB will be created.
- Permissions issue writing to the install directory — this should not happen with the user-level install, but try running as the same user who installed.

### Product images not showing

- Images are stored in the `product_images\` folder next to the EXE.
- If you moved or restored the EXE without copying the `product_images\` folder, images will be missing. Copy the folder back.
- The POS shows a placeholder image when a product image cannot be found — this is expected behaviour, not a crash.

### Receipts or exports not saving

- Check that the `receipts\` and `exports\` folders exist next to the EXE (they are created automatically on first launch).
- Ensure nothing else has the file open (e.g. another PDF viewer locking the file).

### Sales chart tab is slow on first open

- The first time the Sales tab opens in the session, matplotlib is loaded. This may take 1–3 seconds on slower machines. Subsequent opens in the same session are instant.

### Icon not showing on taskbar or EXE

- Run `python make_icon.py` inside `aissas_pos_system/` to regenerate `assets/logo.ico` before building.
- The EXE must be rebuilt with `build.bat` (or `pyinstaller --clean main.spec`) after icon regeneration.

### Database locked error

Close all other running instances of the app. Only one instance should be open at a time.

### `ModuleNotFoundError` in dev mode

Ensure the virtual environment is active and all dependencies are installed:
```bash
pip install -r aissas_pos_system/requirements.txt
```

### Tkinter not found (Linux)

```bash
sudo apt install python3-tk      # Debian/Ubuntu
sudo dnf install python3-tkinter # Fedora
```

---

## 11. Notes

### Default credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | ADMIN |

**Change the default password immediately after first login** via Settings → Security.

### Password policy

When changing a password or creating a new user:
- Minimum **12 characters**
- At least one **uppercase** letter (A–Z)
- At least one **lowercase** letter (a–z)
- At least one **number** (0–9)
- At least one **special character** (`!@#$%^&*` etc.)
- Must not contain the username
- Must not be a known weak password

### Limitations

- **Single-user** — SQLite WAL mode is used, but the app is not designed for concurrent multi-user access from different machines.
- **Windows only for EXE** — the packaged EXE targets Windows 10/11. Source code runs on macOS and Linux in dev mode.
- **No network** — all data is local. No cloud sync, no remote backup.
- **Cancel does not restore stock** — cancelling an order via Transactions does not automatically restore the deducted stock. Adjust manually in Inventory → Products.
- **Draft prices are frozen** — if a product's price changes after a draft is saved, the draft uses the price at save time when loaded.
- **ML suggestions need history** — the recommender requires completed sales data. Use Settings → Seed Demo Sales to generate test data before demonstrating suggestions.

---

## 12. Future Improvements

- **Stock restore on cancel** — automatically restore product stock when an order is cancelled from the Transactions screen.
- **Receipt preview dialog** — show a print-preview before saving/printing the receipt.
- **Barcode scanning** — map hardware barcode scanner input to the POS search field.
- **Day-close / shift report** — summarise all sales for a shift with a printable end-of-day summary.
- **Reactivate users** — currently deactivated users cannot be reactivated via the UI; requires direct DB edit.
- **Multi-machine sync** — replace SQLite with a networked database backend for multi-terminal use.

---

*Aissa's Kitchenette Management System — v1.0.0-beta.2 — Python 3 + Tkinter, offline-first, Windows-ready.*
