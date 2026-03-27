# Aissa's Kitchenette Management System

## 1. Project Overview

**Aissa's Kitchenette Management System** is a standalone desktop Point-of-Sale (POS) and inventory management application built entirely with **Python 3** and **Tkinter**. It is designed for a small food service business (kitchenette), covering the full sales cycle from item selection through payment, receipt printing, and inventory tracking — all in a single offline package. No internet connection is required.

All data is stored locally using **SQLite**; no server or external service is needed.

---

## 2. Key Features

| Module | Description |
|--------|-------------|
| **User Auth & RBAC** | Login system with three roles: ADMIN, MANAGER, CLERK. Per-role permissions are configurable by admin at runtime. |
| **Point of Sale** | Product grid with category filter, live search, clickable product cards, cart management (add / remove / quantity adjust). |
| **Discounts** | Apply a peso-amount or percentage discount to the entire order before checkout. |
| **Checkout** | Cash or Bank/E-Wallet payment. Cash: change is calculated live as the cashier types. Bank: order is saved as Pending until resolved. |
| **Draft Orders** | Save an in-progress cart as a named draft (e.g. "Table 3"). Reload it later from the same POS screen. |
| **Receipts** | PDF thermal receipt via `reportlab`; falls back to plain-text `.txt` if `reportlab` is unavailable. |
| **Inventory** | Products CRUD (create / edit / delete), category management, stock tracking, low-stock alerts. |
| **Transactions** | Full order history with search by ID, filter by status / payment / date range. View line items, reprint receipt, resolve pending orders, cancel orders. |
| **Reports** | Sales charts, best-seller lists, inventory summaries. Export to CSV, PDF, or Excel (`matplotlib` + `openpyxl`). |
| **ML Suggestions** | Offline co-purchase recommender (pure Python, no external ML libraries) suggests items to upsell based on past sales history. |
| **Settings** | Password change (12-char policy enforced), DB export/import backup, user management, role permission toggles. |
| **Offline-first** | Zero network calls. Works completely without internet. |

---

## 3. Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| GUI | Tkinter (built-in) |
| Database | SQLite 3 via `sqlite3` module |
| Architecture | DAO / Services / Views pattern |
| PDF receipts | `reportlab` |
| Charts & exports | `matplotlib`, `openpyxl` |
| Images | `Pillow` (PIL) |

---

## 4. Requirements

### Python version
- **Python 3.10 or newer** (uses `X | Y` union type syntax)

### Required libraries
```
Pillow>=9.0.0
matplotlib>=3.5.0
reportlab>=3.5.0
openpyxl>=3.0.0
```

### OS compatibility
- **Windows 10/11** — primary development platform (Segoe UI fonts)
- **macOS** — works; system font substitution is automatic
- **Linux** — requires `python3-tk` package installed via OS package manager

---

## 5. Installation

### Step 1 — Clone the repository
```bash
git clone <repo-url>
cd AissasKitchenette-Management-System
```

### Step 2 — Create a virtual environment
```bash
# Windows
python -m venv .venv

# macOS / Linux
python3 -m venv .venv
```

### Step 3 — Activate the virtual environment
```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Windows cmd
.\.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

### Step 4 — Install dependencies
```bash
pip install --upgrade pip
pip install -r aissas_pos_system/requirements.txt
```

---

## 6. How to Run

From the **project root** (the folder containing `aissas_pos_system/`) with the venv active:

```bash
cd aissas_pos_system
python main.py
```

On first run the system will:
1. Create the `data/pos.db` SQLite database automatically
2. Seed the default admin user
3. Seed the product menu (categories + sample items)

---

## 7. Project Structure

```
AissasKitchenette-Management-System/
├── README.md                        ← this file
├── data/                            ← runtime SQLite database (auto-created)
│   └── pos.db
├── exports/                         ← generated CSV / PDF / Excel exports
└── aissas_pos_system/               ← main application package
    ├── main.py                      ← application entry point
    ├── requirements.txt
    ├── assets/                      ← logo and icon files
    │   └── icons/
    ├── product_images/              ← raw product image files
    ├── receipts/                    ← generated PDF/text receipts
    └── app/                         ← application source code
        ├── config.py                ← paths, theme colours, app info
        ├── constants.py             ← roles, permission keys, messages
        ├── utils.py                 ← password hashing, money formatter
        ├── validators.py            ← input validation helpers
        ├── db/                      ← data layer
        │   ├── database.py          ← SQLite connection, schema init, migrations
        │   ├── dao.py               ← DAO classes for each table
        │   ├── schema.py            ← CREATE TABLE / INDEX statements
        │   ├── schema_stable.py     ← alternative stable schema definitions
        │   ├── seed_menu.py         ← initial product + category seed
        │   ├── seed_sales.py        ← demo sales data seeder
        │   └── seed_users.py        ← default admin user seed
        ├── ml/                      ← offline ML recommender (pure Python)
        │   └── recommender.py       ← co-purchase pair-frequency engine
        ├── models/                  ← lightweight data model classes
        │   ├── user.py
        │   └── product.py
        ├── services/                ← business logic layer
        │   ├── auth_service.py      ← login, logout, RBAC, password policy
        │   ├── pos_service.py       ← order creation, draft management
        │   ├── inventory_service.py ← inventory helpers
        │   ├── receipt_service.py   ← PDF/text receipt generation
        │   ├── export_service.py    ← CSV/Excel export
        │   ├── report_service.py    ← report data aggregation
        │   └── seed_sales_service.py← demo sales seeding
        └── ui/                      ← Tkinter views and dialogs
            ├── theme.py             ← ttk style helpers
            ├── ui_scale.py          ← DPI-aware scaling utilities
            ├── login_view.py        ← login screen
            ├── app_window.py        ← main window shell + sidebar nav
            ├── pos_view.py          ← POS screen + cart + checkout dialog
            ├── dialogs.py           ← shared dialogs (discount, draft, text prompt)
            ├── transactions_view.py ← transaction history + details dialog
            ├── inventory_view.py    ← inventory dashboard
            ├── inventory_shell_view.py ← inventory tab container
            ├── inventory_products_view.py ← products CRUD table
            ├── inventory_sales_view.py    ← sales/report charts
            ├── account_settings_view.py   ← settings dialog (profile, security, users, RBAC)
            ├── user_mgmt_view.py    ← standalone user list view
            └── reports_view.py      ← reports page
```

---

## 8. How the System Works

### Login flow
1. User enters username + password → `AuthService.login()` verifies against the hashed password in the DB.
2. Role is loaded; the sidebar shows only modules the role has permission to access.

### POS flow
1. Cashier selects a category or searches for a product by name.
2. Clicking a product card (or the **Add** button) adds it to the cart.
3. Quantities can be adjusted with `+` / `−` buttons in the cart panel.
4. Optionally apply an order-level discount (peso amount or percentage).
5. Optionally save the current order as a **Draft** (named, e.g. "Table 5") for later.
6. Click **Checkout** → `ConfirmOrderDialog` opens:
   - Enter the customer name (required).
   - Choose payment method (Cash or Bank/E-Wallet).
   - For Cash: enter amount paid — live change calculation appears immediately.
   - Click **Confirm Checkout** → order is saved to DB, stock is deducted, receipt is generated.

### Draft flow
- **Save as Draft:** cart items + discount are serialised to JSON and stored in the `drafts` table.
- **Load Draft:** the stored cart is restored; the draft record is deleted.
- Draft orders do not affect stock — stock only changes on actual checkout.

### Payment states
| Payment | Status saved | What happens |
|---------|-------------|--------------|
| Cash | `Completed` | Change is calculated; stock deducted; receipt printed. |
| Bank/E-Wallet | `Pending` | Order recorded without change; stock deducted; cashier must resolve later from the Transactions screen. |

### Resolving pending orders
From **Transactions → View → Resolve**: enter the reference number and amount received. The order status moves to `Completed`.

### Stock management
- Each product has a `stock` quantity.
- Selling an item (Cash or Pending) immediately decrements the stock.
- Products with `stock = 0` show **"Not Available"** on the POS and cannot be added to the cart.
- Stock can be manually updated via **Inventory → Products → Edit**.
- Cancelling an order does **not** automatically restore stock (manual adjustment required).

### Receipt generation
- Receipts are saved in `aissas_pos_system/receipts/`.
- PDF is generated by `reportlab` if installed; otherwise a `.txt` file is created.

---

## 9. Usage Guide

### For cashiers (CLERK role)
1. Log in with your assigned username and password.
2. On the POS screen, tap product cards to build an order.
3. Adjust quantities in the cart using `+` / `−`.
4. Apply a discount if needed (button at the bottom of the cart).
5. Click **Checkout**, fill in the customer name and amount paid, then confirm.
6. The receipt is saved automatically.

### For managers / admins
- **Inventory → Products**: create, edit, or deactivate menu items. Set stock levels.
- **Transactions**: review all sales, resolve pending orders, cancel orders.
- **Reports**: view and export sales charts.

### For admins only
- **Settings → Security**: change your password (12-character policy enforced).
- **Settings → Database**: export a full DB backup or restore from a backup file (requires password confirmation).
- **Settings → User Management**: create new users, deactivate or delete inactive users.
- **Settings → Role Permissions**: toggle specific capabilities per role in real time.
- **Settings → Seed Demo Sales**: generate demo historical sales for ML suggestions.

---

## 10. Default Credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | ADMIN |

**Change the default password immediately after first login** via Settings → Security.

---

## 11. Password Policy

When changing a password or creating a new user, the system enforces:
- Minimum **12 characters**
- At least one **uppercase** letter (A–Z)
- At least one **lowercase** letter (a–z)
- At least one **number** (0–9)
- At least one **special character** (`!@#$%^&*` etc.)
- Must not contain the **username**
- Must not be a known **weak password**

---

## 12. Troubleshooting

| Problem | Solution |
|---------|---------|
| `ModuleNotFoundError` | Ensure the venv is active and `pip install -r requirements.txt` completed. |
| `_tkinter` / Tkinter not found | Install `python3-tk` (Linux: `sudo apt install python3-tk`). |
| Database locked | Close all other instances of the app. Delete `data/pos.db` to recreate from scratch. |
| Receipt PDF not generated | Install `reportlab` (`pip install reportlab`). Plain-text fallback is still created. |
| Images not loading | Ensure `Pillow` is installed. Default placeholder image is used on failure. |
| App crashes after failed DB import | Fixed in current version — the DB connection is re-established automatically. |

---

## 13. Important Notes and Limitations

- **Single-user only** — SQLite WAL mode is used, but the app is not designed for concurrent multi-user access.
- **No network** — all data is local. No cloud sync.
- **Cancellation does not restore stock** — if an order is cancelled via the Transactions screen, the stock must be adjusted manually in Inventory → Products.
- **Draft prices** — draft orders preserve prices at the time of saving. If a product price changes after saving a draft, the draft will use the old price when loaded.
- **ML suggestions** — the recommender is trained on completed orders only. Suggestions will not appear until enough real sales history exists (seed demo data from Settings to test it).

---

## 14. Packaging as a Standalone Executable

To build a single-file executable with PyInstaller:

```bash
pip install pyinstaller
cd aissas_pos_system
pyinstaller --onefile --windowed main.py
```

You must include `assets/`, `product_images/`, and `data/` directories via a `.spec` file when distributing, as `--onefile` does not bundle them automatically.

---

## 15. Future Improvements (Suggested)

- **Tabbed Settings dialog** — replace the single long-scroll settings panel with a sidebar category navigator for easier access to admin sections.
- **Stock restore on cancel** — automatically restore product stock when an order is cancelled.
- **Multi-item transaction** — wrap all per-item inserts into a single DB transaction for atomic checkout.
- **Receipt preview** — show a print-preview dialog before saving/printing.
- **Barcode scanning** — map hardware scanner input to the POS search field.
- **Day-close / shift report** — summarise sales for a shift with a printable summary.
- **Reactivate users** — currently users can only be deactivated, not reactivated via UI.

---

*Aissa's Kitchenette Management System — built with Python 3 + Tkinter.*
