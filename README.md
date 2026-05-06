# Aissa's Kitchenette Management System

A standalone desktop **Point-of-Sale and Inventory Management System** built for a small food service business. Developed with **Python 3 + Tkinter + SQLite**. Fully offline — no internet connection required.

> **Current release: v2.0-beta** — Feature-complete beta, stable for daily use

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [Modules Overview](#3-modules-overview)
4. [Installation — End Users](#4-installation--end-users)
5. [Developer Setup](#5-developer-setup)
6. [How to Run](#6-how-to-run)
7. [How to Build the EXE](#7-how-to-build-the-exe)
8. [How to Build the Installer](#8-how-to-build-the-installer)
9. [Data Storage](#9-data-storage)
10. [Roles & Permissions](#10-roles--permissions)
11. [Raw Materials Module](#11-raw-materials-module)
12. [Reports & Dashboard](#12-reports--dashboard)
13. [Troubleshooting](#13-troubleshooting)
14. [Version History](#14-version-history)
15. [Project Structure](#15-project-structure)

---

## 1. Project Overview

Aissa's Kitchenette Management System is an offline-first POS desktop application covering the full operations cycle of a small food service business: product management, sales, cash handling, inventory control, raw materials tracking, and reporting — packaged as a single Windows EXE with no Python installation required on the target machine.

All data is stored locally using SQLite. The application runs entirely without network access and is designed to be used by non-technical staff.

---

## 2. Key Features

| Category | Feature |
|----------|---------|
| **POS** | Product grid, live search, category filter, cart, discounts, checkout |
| **Payments** | Cash (live change calculation), Bank/E-Wallet (saved as Pending) |
| **Receipts** | PDF receipt generated and saved automatically on every checkout |
| **Inventory** | Products CRUD, category management, image upload, stock tracking |
| **Raw Materials** | Ingredient tracking with expiry dates, FIFO, stock movements, audit logs |
| **Dashboard** | KPI cards, top sellers, recent transactions — auto-refreshing |
| **Reports** | Daily/Monthly/Yearly charts, export to PDF and Excel |
| **Roles** | ADMIN, MANAGER, CASHIER, INVENTORY — scoped access per role |
| **Settings** | User management, database backup/restore, ZIP data import |
| **Offline-first** | Zero network calls — works entirely without internet |
| **Windows EXE** | Single-file EXE with Inno Setup installer, no Python needed |

---

## 3. Modules Overview

### Point of Sale

- Products displayed as cards with image thumbnails
- Live search and category filter
- Cart with quantity controls and item removal
- Order-level discount (peso or percentage)
- **Draft orders** — save and reload a cart in progress without affecting stock
- Checkout: choose payment method, confirm order
- Cash payments show live change; Bank/E-Wallet orders saved as Pending
- PDF receipt saved automatically on every completed order
- **Co-purchase suggestions** — offline ML engine suggests frequently bought-together items

### Inventory — Products

- Add, edit, and delete products
- Category management
- Upload and preview product images
- Manual stock adjustment
- Low-stock visual indicators

### Inventory — Raw Materials

See [Section 11](#11-raw-materials-module).

### Transactions

- Full order history with search by ID
- Filter by status, payment method, and date range
- View line items per order
- Reprint receipt, resolve pending orders, void orders

### Dashboard

- KPI cards: today's sales, monthly sales, order counts
- Top Selling Products ranked by quantity sold
- Recent Transactions (latest 10 orders)
- Auto-refreshing with manual Refresh button

### Reports

See [Section 12](#12-reports--dashboard).

### Settings

- **Account** — change password
- **Users** — create and manage user accounts (ADMIN only)
- **Database** — export, import, and ZIP data restore

---

## 4. Installation — End Users

> No Python or development tools required.

1. Double-click `AissasKitchenette_POS_v2.0-beta_Setup.exe` and follow the wizard.
2. Launch via the **desktop shortcut** or **Start Menu → Aissa's Kitchenette**.
3. Log in with the default credentials:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `Admin123@` | ADMIN |

> **Change the default password immediately** after first login via Settings → Account → Change Password.

### Fresh / Production Install

The production installer starts with a completely empty database. No demo products, categories, or transactions are pre-loaded.

**After first login the admin must:**

1. Go to **Inventory → Products** and create at least one category.
2. Add products (name, price, stock) to each category.
3. Optionally upload a product image for each item.
4. Products marked **Available** will appear immediately in the POS product grid.

**Dashboard and Reports** display zero/empty states until real transactions exist — this is normal and expected on a fresh install.

**Product images** can be uploaded at any time from the product edit dialog. The upload folder is `%APPDATA%\AissasPOS\product_images\`.

### Uninstalling

Settings → Apps (Windows 11) or Control Panel → Programs and Features → find "Aissa's Kitchenette" → Uninstall.

---

## 5. Developer Setup

### Requirements

- **Python 3.10 or newer**
- **Windows 10 or 11** recommended (Segoe UI font required for full visual fidelity)
- macOS and Linux work in dev mode — `python3-tk` required on Linux

### Install dependencies

```bash
pip install -r aissas_pos_system/requirements.txt
```

| Library | Purpose |
|---------|---------|
| **Pillow** | Product thumbnails, login images, logo rendering |
| **matplotlib** | Sales charts in Reports and Inventory views |
| **reportlab** | PDF receipt generation |
| **openpyxl** | Excel export from Reports |
| **scikit-learn** | Co-purchase recommendation engine |

---

## 6. How to Run

```bash
# Clone
git clone 
cd AissasKitchenette-Management-System

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate.bat        # Windows
# source .venv/bin/activate         # macOS / Linux

# Install dependencies
pip install -r aissas_pos_system/requirements.txt

# Run
cd aissas_pos_system
python main.py
```

On first run the app automatically creates the database and seeds the default admin user. No demo products or sample data are added — the menu starts empty and must be populated by an admin.

---

## 7. How to Build the EXE

### Prerequisites

```bash
pip install pyinstaller pyinstaller-hooks-contrib
```

### One-command build

```bash
cd aissas_pos_system
build.bat
```

| Step | Output |
|------|--------|
| Generate icon | `assets/logo.ico` |
| PyInstaller | `dist/AissasKitchenette.exe` |
| Rename copy | `dist/AissasKitchenette_POS_v2.0-beta.exe` |
| Inno Setup | `dist/AissasKitchenette_POS_v2.0-beta_Setup.exe` |

### Manual build

```bash
cd aissas_pos_system
python make_icon.py
pyinstaller --clean main.spec
```

---

## 8. How to Build the Installer

Requires **Inno Setup 6**: [https://jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php)

```powershell
# PowerShell — note the & operator required when path has spaces
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Output: `dist/AissasKitchenette_POS_v2.0-beta_Setup.exe`

---

## 9. Data Storage

All user data is stored in AppData — separate from the install directory and preserved across reinstalls.
```
%APPDATA%\AissasPOS
├── data
│   └── pos.db              ← SQLite database
├── receipts\               ← PDF receipts
├── exports\                ← PDF / Excel exports
└── product_images\         ← User-uploaded product images
```

Open this folder: press `Win + R` → type `%APPDATA%\AissasPOS`

### Backup and restore

- **Export:** Settings → Database → Export Database
- **Import:** Settings → Database → Import Database

### ZIP data import (database + images together)

**Create the ZIP:**
```powershell
Compress-Archive -Path data, product_images -DestinationPath backup.zip
```

**Import:** Settings → Database → Import Data (ZIP)

A timestamped backup of the current database is created automatically before any replacement.

---

## 10. Roles & Permissions

| Role | POS | Transactions | Inventory | Raw Materials | Reports | Dashboard | Settings |
|------|-----|-------------|-----------|---------------|---------|-----------|----------|
| **ADMIN** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **MANAGER** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Partial |
| **CASHIER** | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **INVENTORY** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |

### Password Policy

- Minimum 12 characters
- At least one uppercase, one lowercase, one number, one special character
- Must not contain the username
- Must not be a known weak password

---

## 11. Raw Materials Module

Tracks ingredients and kitchen supplies separately from finished products.

| Feature | Description |
|---------|-------------|
| **Fields** | Name, Type, Unit, Quantity, Low Stock Alert threshold |
| **Dates** | Delivered Date, Expiration Date |
| **Expiry Status** | Active / Expiring Soon (≤7 days) / Expired — auto-calculated |
| **Row Highlights** | Expired, expiring-soon, and low-stock rows are color-coded |
| **Add Stock** | Record new deliveries with quantity and dates |
| **Deduct Stock** | Record consumption with reason |
| **Movement History** | Full log per material |
| **Audit Logs** | All changes logged with timestamp and user |
| **FIFO Sort** | Sort by earliest expiry to minimize waste |

---

## 12. Reports & Dashboard

### Dashboard

- KPI Cards — today's and this month's sales and order counts
- Top Selling Products — ranked by quantity sold today
- Recent Transactions — latest 10 orders
- Auto-refresh + manual Refresh button

### Sales Reports

| Report | Description |
|--------|-------------|
| **Daily** | Bar chart of sales per day for the selected month |
| **Monthly** | Bar chart of sales per month for the selected year |
| **Yearly** | Total sales per year |
| **KPI Summary** | Total Sales, Total Orders, Average Order Value |

### Exports

| Format | Contents |
|--------|---------|
| **PDF** | Chart image + KPI summary |
| **Excel** | Raw sales data rows |

Saved to `%APPDATA%\AissasPOS\exports\`

---

## 13. Troubleshooting

**EXE crashes silently** — check `app.log` in the install folder or `%LocalAppData%\Programs\AissasKitchenette\`.

**App opens then immediately closes** — check `app.log`. If the database is corrupted, delete `%APPDATA%\AissasPOS\data\pos.db` and relaunch.

**Product images not showing** — images live in `%APPDATA%\AissasPOS\product_images\`. Use Settings → Database → Import Data (ZIP) to restore images together with the database.

**Receipts or exports not saving** — ensure no other app has the file open. Folders are created automatically on first launch.

**Database locked error** — close all other running instances. Only one instance should be open at a time.

**`ModuleNotFoundError` in dev mode** — activate the virtual environment and run `pip install -r aissas_pos_system/requirements.txt`.

**ML suggestions not appearing** — the recommender requires existing sales history. Use Settings → Demo Data → Seed Demo Sales, then return to POS.

**Tkinter not found (Linux):**
```bash
sudo apt install python3-tk       # Debian / Ubuntu
sudo dnf install python3-tkinter  # Fedora
```

---

## 14. Version History

### v2.0-beta — Current Release

**Payment & Order Validation**
- Cash payments only: no reference number required
- Bank/E-Wallet payments: reference number is mandatory (validated on checkout)
- Dine In orders: Table No. must be a whole number between 1 and 20
- Take Out orders: Order No. must be a whole number between 1 and 30

**Product & Inventory**
- Product availability is controlled by the Available toggle — not derived from stock levels
- Inventory low-stock alerts apply to raw materials only; finished products are excluded from alert logic

**Receipts & Pending Payments**
- Bank/E-Wallet orders are saved as Pending and a receipt is generated immediately on checkout
- Pending receipts are marked clearly and updated automatically when the order is resolved

**Dashboard & Reports**
- KPI cards and top-sellers use stabilized aggregation — consistent between daily/monthly views
- Charts no longer overlap or break on window resize or maximize/restore
- Dashboard polling interval tuned to avoid excessive DB reads on multi-device setups

**UX & Notifications**
- Confirmation and success popups are positioned relative to the active window
- Auto-dismiss notifications disappear after a fixed timeout without user action
- Void and payment dialogs enforce focus so they cannot be dismissed accidentally

**Multi-device & Sync**
- Database polling detects external changes (e.g., from a second cashier device) and refreshes affected views automatically
- Transaction list and dashboard refresh without requiring a manual reload

**Build**
- Installer renamed to `AissasKitchenette_POS_v{version}_Setup.exe`
- Standalone EXE renamed to `AissasKitchenette_POS_v{version}.exe`
- Build script backs up previous dist outputs before each clean build

---

### v2.0.0

- Raw Materials module — expiry tracking, FIFO, stock movements, audit logs
- INVENTORY role — stock management without POS access
- CASHIER role — POS and transactions only
- Keypad now works on all numeric fields (Table No., Amount Paid)
- Product cards simplified — description removed for cleaner UI
- Window starts fullscreen immediately on launch
- Improved layout stability during resize and maximize/restore
- Reports charts stable — no overlap or layout breaking on resize
- Matplotlib data bundled in EXE — charts work correctly in installed version
- AppData storage — data preserved across reinstalls

### v1.0.0 — Initial Release

- Core POS: product grid, cart, checkout, cash/bank payments
- Draft orders, inventory CRUD, transaction history
- Sales reports with PDF and Excel export
- Role-based login (ADMIN, MANAGER, CLERK)
- PDF receipt generation, DB backup/restore
- Co-purchase ML suggestion engine
- Windows EXE with Inno Setup installer

---

## 15. Project Structure

```
AissasKitchenette-Management-System/
├── README.md
└── aissas_pos_system/
    ├── main.py                              ← entry point
    ├── main.spec                            ← PyInstaller build spec
    ├── build.bat                            ← one-command build script
    ├── make_icon.py                         ← generates assets/logo.ico
    ├── installer.iss                        ← Inno Setup 6 installer script
    ├── requirements.txt                     ← Python dependencies
    ├── assets/
    │   ├── logo.jpg / logo.ico / logo.png   ← app logo
    │   ├── icons/                           ← UI icons
    │   └── login/                           ← login screen images
    ├── product_images/                      ← default product photos
    └── app/
        ├── config.py                        ← paths, theme, EXE resolution
        ├── constants.py                     ← roles, permissions, messages
        ├── utils.py                         ← password hashing, formatters
        ├── validators.py                    ← input validation
        ├── db/
        │   ├── database.py                  ← SQLite connection, WAL mode
        │   ├── dao.py                       ← data access objects
        │   ├── schema.py                    ← CREATE TABLE statements
        │   ├── schema_stable.py             ← versioned schema for migrations
        │   ├── seed_menu.py                 ← default product seed
        │   ├── seed_sales.py                ← demo sales seeder
        │   └── seed_users.py                ← default admin seed
        ├── ml/
        │   └── recommender.py               ← co-purchase recommendation engine
        ├── models/
        │   ├── order.py / order_item.py
        │   ├── product.py / user.py
        ├── services/
        │   ├── auth_service.py              ← login, RBAC, password policy
        │   ├── pos_service.py               ← orders, stock, drafts
        │   ├── receipt_service.py           ← PDF receipt generation
        │   ├── inventory_service.py         ← raw materials business logic
        │   ├── backup_service.py            ← backup and ZIP import/export
        │   ├── export_service.py            ← CSV / Excel export
        │   ├── report_service.py            ← sales report aggregation
        │   └── seed_sales_service.py        ← demo data generation
        └── ui/
            ├── app_window.py                ← main window + navigation
            ├── login_view.py                ← login screen
            ├── pos_view.py                  ← POS, cart, checkout
            ├── dashboard_view.py            ← KPIs and top sellers
            ├── transactions_view.py         ← order history
            ├── inventory_shell_view.py      ← inventory navigation
            ├── inventory_products_view.py   ← products CRUD
            ├── inventory_raw_materials_view.py ← raw materials
            ├── inventory_sales_view.py      ← embedded sales chart
            ├── reports_view.py              ← reports + export
            ├── backup_view.py               ← backup and restore UI
            ├── account_settings_view.py     ← account settings
            ├── user_mgmt_view.py            ← user management
            ├── theme.py                     ← colour palette
            ├── ui_scale.py                  ← DPI scaling helpers
            ├── ui_styles.py                 ← shared widget styles
            └── dialogs.py                   ← shared dialogs
```

---

*Aissa's Kitchenette Management System — v2.0-beta — Python 3 + Tkinter + SQLite — Offline-first, Windows-ready.*
