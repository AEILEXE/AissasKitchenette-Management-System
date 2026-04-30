# Aissa's Kitchenette Management System

A standalone desktop **Point-of-Sale and Inventory Management System** built for a small food service business. Developed entirely with **Python 3 + Tkinter + SQLite**. Fully offline — no internet connection required.

> **Current release: v2.0.0** — Stable

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
14. [Future Improvements](#14-future-improvements)
15. [Version History](#15-version-history)

---

## 1. Project Overview

Aissa's Kitchenette Management System is an offline-first POS desktop application that covers the full operations cycle of a small food service business: product management, sales, cash handling, inventory control, raw materials tracking, and reporting — packaged as a single Windows EXE with no Python installation required on the target machine.

All data is stored locally on the device using SQLite. The application runs entirely without network access and is designed to be installed and used by non-technical staff.

---

## 2. Key Features

| Category | Feature |
|----------|---------|
| **POS** | Fast product grid, live search, category filter, cart, discounts, checkout |
| **Payments** | Cash (live change), Bank/E-Wallet (saved as Pending, resolved later) |
| **Receipts** | PDF receipt generated and saved automatically on every checkout |
| **Inventory** | Products CRUD, category management, image upload, stock tracking |
| **Raw Materials** | Dedicated raw materials module with expiry tracking, FIFO, audit logs |
| **Dashboard** | KPI cards, top sellers, recent transactions — auto-refreshing |
| **Reports** | Daily/Monthly/Yearly charts, export to PDF and Excel |
| **Roles** | ADMIN, MANAGER, CASHIER, INVENTORY — scoped access per role |
| **Settings** | User management, database backup/restore, ZIP data import |
| **Offline-first** | Zero network calls — works entirely without internet |
| **Windows EXE** | Single-file EXE with Inno Setup installer, no Python needed |

---

## 3. Modules Overview

### Point of Sale

The POS screen provides a fast, grid-based product selection interface designed for cashier use.

- Products displayed as cards with image thumbnails and stock indicators
- Live search and category filter to quickly find items
- Cart with quantity controls (`+` / `−`) and individual item removal
- Order-level discount (peso amount or percentage)
- **Draft orders** — save a cart in progress (e.g. "Table 3") and reload it later; drafts do not affect stock
- Checkout dialog: enter customer name, choose payment method, confirm
- Cash payments calculate change live; Bank/E-Wallet orders are saved as Pending
- PDF receipt saved automatically on every completed order
- **Co-purchase suggestions** — offline recommender engine suggests items frequently bought together with the current cart (requires existing sales history)

### Inventory — Products

- Add, edit, and delete products
- Category management
- Upload and preview product images
- Manual stock adjustment per product
- Low-stock visual indicators

### Inventory — Raw Materials

See [Section 11](#11-raw-materials-module) for full details.

### Transactions

- Full order history with search by ID
- Filter by status, payment method, and date range
- View line items per order
- Reprint receipt
- Resolve pending (Bank/E-Wallet) orders
- Void / cancel orders

### Dashboard

- KPI summary cards: today's sales, monthly sales, order counts
- Top Selling Products (ranked by quantity sold)
- Recent Transactions (latest 10 orders)
- Auto-refreshing; manual Refresh button available

### Reports

See [Section 12](#12-reports--dashboard) for full details.

### Settings

- **Account** — change password (enforced 12-character policy)
- **Users** — create, manage, and deactivate user accounts (ADMIN only)
- **Database** — export database, import database, import full data via ZIP
- **Demo Data** — seed sample sales for testing and demonstration

---

## 4. Installation — End Users

> Recommended for non-technical users. No Python or development tools required.

### Step 1 — Run the installer

Double-click `AissasKitchenette_Setup.exe` and follow the setup wizard.

The installer will:
- Install the application to `C:\Users\<YourName>\AppData\Local\Programs\AissasKitchenette` (no admin rights required)
- Create a desktop shortcut (checked by default)
- Create Start Menu shortcuts

### Step 2 — Launch the app

After installation, launch via the **desktop shortcut** or **Start Menu → Aissa's Kitchenette**.

### Step 3 — Log in

Default credentials on first launch:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | ADMIN |

> **Change the default password immediately** after first login via Settings → Account → Change Password.

### Uninstalling

Go to **Settings → Apps** (Windows 11) or **Control Panel → Programs and Features**, find "Aissa's Kitchenette", and click Uninstall.

---

## 5. Developer Setup

### System Requirements

- **Python 3.10 or newer** (uses `X | Y` union type syntax)
- **Windows 10 or 11** recommended (primary target platform; Segoe UI font required for full visual fidelity)
- macOS and Linux work in dev mode — system font substitution is automatic; Linux requires `python3-tk`

### Python Dependencies

```bash
pip install -r aissas_pos_system/requirements.txt
```

| Library | Version | Purpose |
|---------|---------|---------|
| **Pillow** | `>=9.0.0` | Product card thumbnails, login images, logo rendering, ICO generation |
| **matplotlib** | `>=3.5.0` | Sales charts (Daily / Monthly / Yearly) embedded in Tkinter |
| **reportlab** | `>=3.5.0` | PDF thermal receipt generation with ₱ peso sign support |
| **openpyxl** | `>=3.0.0` | Excel export from the Reports tab |

### EXE Build Tools (optional, not needed to run in dev mode)

```bash
pip install pyinstaller pyinstaller-hooks-contrib
```

---

## 6. How to Run

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

From the project root with the virtual environment active:

```bash
cd aissas_pos_system
python main.py
```

On first run, the system will automatically:
1. Create the SQLite database at `%APPDATA%\AissasPOS\data\pos.db`
2. Seed the default admin user (`admin` / `admin123`)
3. Seed the default product menu (categories + sample items)

---

## 7. How to Build the EXE

### Prerequisites

```bash
pip install pyinstaller pyinstaller-hooks-contrib
```

Inno Setup 6 must be installed separately for the installer step (see [Section 8](#8-how-to-build-the-installer)).

### One-command build (recommended)

From inside `aissas_pos_system/`:

```bash
build.bat
```

`build.bat` runs three steps in sequence:

| Step | Command | Output |
|------|---------|--------|
| 1. Generate icon | `python make_icon.py` | `assets/logo.ico` (multi-size ICO) |
| 2. Build EXE | `pyinstaller --clean main.spec` | `dist/AissasKitchenette.exe` |
| 3. Build installer | `ISCC.exe installer.iss` | `dist/AissasKitchenette_Setup.exe` |

If Inno Setup is not found, Step 3 is skipped with a warning. Steps 1 and 2 still complete.

### Manual build (step by step)

```bash
cd aissas_pos_system

# Step 1: generate the icon
python make_icon.py

# Step 2: build the EXE
pyinstaller --clean main.spec

# Output: dist/AissasKitchenette.exe
```

### Notes on `main.spec`

- Bundles `assets/` and `product_images/` as read-only data inside the EXE
- Comprehensive `hiddenimports` covering Pillow, reportlab, matplotlib, openpyxl
- `console=False` — no terminal window shown to the user
- `icon='assets/logo.ico'` — sets the EXE and taskbar icon

---

## 8. How to Build the Installer

The installer is built with **Inno Setup 6** using `installer.iss`.

### Install Inno Setup 6

Download from: [https://jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php)

### Build the installer

```bash
# From aissas_pos_system/ — requires Inno Setup in the default path:
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

# Or run the full build script which handles this automatically:
build.bat
```

Output: `dist/AissasKitchenette_Setup.exe`

### Installer behavior

- Installs to `%LocalAppData%\Programs\AissasKitchenette` — no admin rights required
- Creates Start Menu shortcuts and an optional desktop shortcut
- Offers to launch the app immediately after installation
- Uninstaller removes all application files from the install directory

---

## 9. Data Storage

All user data (database, receipts, exports, product images) is stored in the Windows AppData folder — separate from the application install location and preserved across reinstalls.

### Storage path

```
%APPDATA%\AissasPOS\
├── data\
│   └── pos.db              ← SQLite database
├── receipts\               ← PDF receipts (one per checkout)
├── exports\                ← PDF / Excel report exports
└── product_images\         ← User-uploaded product images
```

To open this folder directly, press `Win + R` and type:
```
%APPDATA%\AissasPOS
```

### In dev mode (running `python main.py`)

Data is stored in the same `%APPDATA%\AissasPOS\` path. Dev mode and the installed EXE share the same database location.

### Database backup and restore

**Export:** Settings → Database → Export Database — saves a copy of `pos.db` to any location you choose.

**Import:** Settings → Database → Import Database — replaces the live database with a backup `.db` file. Requires password confirmation. The app reconnects automatically after import.

### ZIP data import (database + product images)

Use **Settings → Database → Import Data (ZIP)** to restore both the database and all product images in one step.

**Expected ZIP structure:**

```
data/
data/pos.db
product_images/
product_images/item1.png
product_images/item2.webp
...
```

**How to create the ZIP (PowerShell):**

```powershell
Compress-Archive -Path data, product_images -DestinationPath app_data_backup.zip
```

**How to import:**

1. Go to **Settings → Database** (admin login required)
2. Click **Import Data (ZIP)**
3. Enter your admin password when prompted
4. Select the `.zip` file
5. Confirm the warning — the current database and product images will be replaced
6. A timestamped backup of the current `pos.db` is created automatically before any file is replaced
7. The app reloads all data immediately — no restart required

**Safety notes:**

- A timestamped `.db` backup is always created before any replacement
- ZIP entries containing `..` (path traversal) are rejected
- Only `data/` and `product_images/` entries are extracted; all other ZIP entries are ignored

---

## 10. Roles & Permissions

The system uses role-based access control (RBAC). Each role has a fixed scope of accessible modules.

| Role | POS | Transactions | Inventory | Raw Materials | Reports | Dashboard | Settings |
|------|-----|-------------|-----------|---------------|---------|-----------|----------|
| **ADMIN** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **MANAGER** | Yes | Yes | Yes | Yes | Yes | Yes | Partial |
| **CASHIER** | Yes | Yes | No | No | No | Yes | No |
| **INVENTORY** | No | No | Yes | Yes | Yes | Yes | No |

**Role summaries:**

- **ADMIN** — Full system access. Manages users, permissions, database, and all operations.
- **MANAGER** — Full operational access. Can manage products, view reports, and handle transactions. Limited settings access.
- **CASHIER** — POS and transaction access only. Cannot access inventory or raw materials.
- **INVENTORY** — Stock and raw materials management, plus reports and dashboard. Cannot access POS.

### Password Policy

All user accounts enforce the following password requirements:

- Minimum **12 characters**
- At least one **uppercase** letter (A–Z)
- At least one **lowercase** letter (a–z)
- At least one **number** (0–9)
- At least one **special character** (`!@#$%^&*` etc.)
- Must not contain the username
- Must not be a known weak password

---

## 11. Raw Materials Module

The Raw Materials module is a dedicated inventory system for tracking the ingredients and supplies used by the kitchen — separate from finished products in the POS.

### Features

| Feature | Description |
|---------|-------------|
| **Fields** | Name, Type, Unit, Quantity, Low Stock Alert threshold |
| **Dates** | Delivered Date, Expiration Date |
| **Expiry Status** | Automatically calculated: Active / Expiring Soon / Expired |
| **Sortable Columns** | Click any column header to sort; FIFO sort by expiry date supported |
| **Row Highlights** | Expired rows, expiring-soon rows, and low-stock rows are color-coded |
| **Add Stock** | Record a new stock delivery with quantity and delivery/expiry dates |
| **Deduct / Use Stock** | Record consumption of stock with a reason |
| **Stock Movement History** | Full log of all additions and deductions per material |
| **Audit Logs** | All changes are logged with timestamp and user |
| **Double-click to Edit** | Double-click any row to open the edit dialog |

### Expiry Status Logic

| Status | Condition |
|--------|-----------|
| **Expired** | Expiration date is in the past |
| **Expiring Soon** | Expiration date is within the next 7 days |
| **Active** | Expiration date is more than 7 days away |
| **No Expiry** | No expiration date set |

### Stock Movement

Every addition and deduction is logged with:
- Date and time
- Quantity change
- Reason / notes
- User who performed the action

Access the movement history by selecting a raw material and clicking **View History**.

### FIFO Sort

Clicking the expiry date column sorts materials by earliest expiration first, supporting FIFO (First In, First Out) stock usage to minimize waste.

---

## 12. Reports & Dashboard

### Dashboard

The Dashboard provides a live operational overview for managers and admins.

- **KPI Cards** — Today's total sales, this month's total sales, today's order count, this month's order count
- **Top Selling Products** — Ranked by quantity sold for the current day
- **Recent Transactions** — Latest 10 orders with status and amount
- **Auto-refresh** — Dashboard data refreshes automatically; manual Refresh button also available

### Sales Reports

The Reports module provides historical sales analysis.

| Report | Description |
|--------|-------------|
| **Daily** | Bar chart of sales per day for the selected month |
| **Monthly** | Bar chart of sales per month for the selected year |
| **Yearly** | Bar chart of total sales per year |
| **KPI Summary** | Total Sales, Total Orders, Average Order Value for the selected period |

### Exports

| Format | Contents |
|--------|---------|
| **PDF** | Chart image + KPI summary table |
| **Excel** | Raw sales data rows, suitable for further analysis |

Exports are saved to `%APPDATA%\AissasPOS\exports\`.

---

## 13. Troubleshooting

### EXE does not open / crashes silently

The application runs without a console window. All errors are written to `app.log` in the same folder as the EXE.

1. Open `%LocalAppData%\Programs\AissasKitchenette\app.log` in Notepad
2. The log contains timestamps and full exception tracebacks for every crash

### App opens but immediately closes

Check `app.log` (see above). Common causes:

- **Corrupted database** — delete `%APPDATA%\AissasPOS\data\pos.db` and relaunch. A fresh database will be created automatically.
- **Permissions issue** — ensure you are running as the same Windows user who installed the application.

### Product images not showing

Images are stored in `%APPDATA%\AissasPOS\product_images\`. If you restored the database without restoring product images, the images will be missing. Use **Settings → Database → Import Data (ZIP)** to restore both together. The POS shows a placeholder image when a product image file is not found — this is expected behavior, not a crash.

### Receipts or exports not saving

- Check that `%APPDATA%\AissasPOS\receipts\` and `exports\` exist (created automatically on first launch)
- Ensure no other application (e.g. a PDF viewer) has the file open and locked

### Dashboard or Top Sellers not updating

Click the **Refresh** button on the Dashboard. If the issue persists, close and reopen the dashboard tab.

### Database locked error

Close all other running instances of the application. Only one instance should be open at a time.

### `ModuleNotFoundError` in dev mode

Ensure the virtual environment is active and all dependencies are installed:

```bash
pip install -r aissas_pos_system/requirements.txt
```

### Icon not showing on taskbar or EXE file

Regenerate the icon before building:

```bash
cd aissas_pos_system
python make_icon.py
pyinstaller --clean main.spec
```

### Tkinter not found (Linux)

```bash
sudo apt install python3-tk      # Debian / Ubuntu
sudo dnf install python3-tkinter # Fedora
```

### ML suggestions not appearing

The co-purchase recommender requires existing completed sales history to produce suggestions. Go to **Settings → Demo Data → Seed Demo Sales** to generate test data, then return to the POS.

---

## 14. Future Improvements

- **Stock restore on order cancellation** — automatically restore product stock when an order is cancelled from the Transactions screen
- **Receipt preview dialog** — show a print-preview before the PDF is saved
- **Barcode scanning** — map hardware barcode scanner input to the POS search field
- **Day-close / shift report** — summarise all sales for a cashier shift with a printable end-of-day summary
- **Reactivate deactivated users** — UI option to reactivate users that have been deactivated
- **Raw materials–to–product linkage** — automatically deduct raw materials when a product is sold
- **Multi-terminal support** — replace SQLite with a networked database backend for multi-cashier deployments

---

## 15. Version History

### v2.0.0 — Current Stable Release

**Major additions:**
- Raw Materials module — full ingredient/supply tracking with expiry, FIFO, stock movements, and audit logs
- INVENTORY role — dedicated role for stock and raw materials management without POS access
- CASHIER role replaces CLERK — scoped to POS and transactions only, no inventory access

**Improvements:**
- Dashboard auto-refresh and Top Sellers display fixed
- Smoother POS UI — reduced stutter and flicker during product grid rendering
- Improved product grid layout stability on window resize and maximize/restore
- Better database migration system for smoother upgrades
- AppData storage (`%APPDATA%\AissasPOS\`) — data is now decoupled from the install directory and preserved across reinstalls
- Cleaner EXE builds with improved Windows compatibility

### v1.0.0 — Initial Release

- Core POS: product grid, cart, checkout, cash/bank payments
- Draft orders
- Inventory: products CRUD, categories, images, stock tracking
- Transactions history with pending resolution
- Sales reports (Daily / Monthly / Yearly) with PDF and Excel export
- Role-based login (ADMIN, MANAGER, CLERK)
- PDF receipt generation
- DB backup/restore and ZIP data import
- Co-purchase suggestion engine (offline ML)
- Packaged as Windows EXE with Inno Setup installer

---

## Project Structure

```
AissasKitchenette-Management-System/
├── README.md
└── aissas_pos_system/
    ├── main.py                           ← entry point; EXE bootstrap + window init
    ├── main.spec                         ← PyInstaller spec (use this to build EXE)
    ├── build.bat                         ← one-command build: icon → EXE → installer
    ├── make_icon.py                      ← converts assets/logo.jpg → assets/logo.ico
    ├── installer.iss                     ← Inno Setup 6 installer script
    ├── requirements.txt                  ← Python dependencies
    ├── assets/
    │   ├── logo.jpg                      ← source logo
    │   ├── logo.ico                      ← generated icon (run make_icon.py first)
    │   ├── fonts/                        ← TTF fonts for PDF receipts (DejaVuSans)
    │   └── icons/                        ← UI icon images
    ├── product_images/                   ← default/placeholder product images
    └── app/
        ├── config.py                     ← paths, theme colours, EXE path resolution
        ├── constants.py                  ← roles, permission keys, messages
        ├── utils.py                      ← password hashing, money formatter
        ├── validators.py                 ← input validation helpers
        ├── db/
        │   ├── database.py               ← SQLite connection, schema init, WAL mode
        │   ├── dao.py                    ← DAO classes for every table
        │   ├── schema.py                 ← CREATE TABLE / INDEX statements
        │   ├── schema_stable.py          ← versioned stable schema for migrations
        │   ├── seed_menu.py              ← initial product + category seed data
        │   ├── seed_sales.py             ← demo sales data seeder
        │   └── seed_users.py             ← default admin user seed
        ├── ml/
        │   └── recommender.py            ← co-purchase pair-frequency engine
        ├── models/
        │   ├── order.py
        │   ├── order_item.py
        │   ├── product.py
        │   └── user.py
        ├── services/
        │   ├── auth_service.py           ← login, logout, RBAC, password policy
        │   ├── pos_service.py            ← order creation, stock deduction, drafts
        │   ├── receipt_service.py        ← PDF receipt generation (reportlab)
        │   ├── inventory_service.py      ← raw materials and stock business logic
        │   ├── backup_service.py         ← database backup and ZIP import/export
        │   ├── export_service.py         ← CSV / Excel export
        │   ├── report_service.py         ← sales report data aggregation
        │   └── seed_sales_service.py     ← demo sales data generation
        └── ui/
            ├── app_window.py             ← main window shell + sidebar navigation
            ├── login_view.py             ← login screen
            ├── pos_view.py               ← POS screen, cart, checkout dialog
            ├── dashboard_view.py         ← overview dashboard (KPIs, top sellers)
            ├── transactions_view.py      ← transaction history + details
            ├── inventory_shell_view.py   ← inventory section navigation shell
            ├── inventory_products_view.py ← products CRUD table
            ├── inventory_raw_materials_view.py ← raw materials CRUD + history
            ├── inventory_sales_view.py   ← embedded sales chart (matplotlib)
            ├── reports_view.py           ← sales reports + export
            ├── backup_view.py            ← database backup and restore UI
            ├── account_settings_view.py  ← account settings (profile, security)
            ├── user_mgmt_view.py         ← user management (ADMIN only)
            ├── theme.py                  ← colour palette and theme definitions
            ├── ui_scale.py               ← DPI-aware scaling helpers
            ├── ui_styles.py              ← shared widget style definitions
            └── dialogs.py                ← shared dialogs (discount, draft, input)
```

---

*Aissa's Kitchenette Management System — v2.0.0 — Python 3 + Tkinter + SQLite — Offline-first, Windows-ready.*
