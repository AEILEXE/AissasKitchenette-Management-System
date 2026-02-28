# Aissa's Kitchenette Management System

## Overview

Aissa's Kitchenette Management System is a standalone desktop Point‑of‑Sale (POS) and inventory application built entirely with **Python 3** and **Tkinter**. It combines sales processing, inventory management, transaction history, reporting and user authentication into one offline package. All data is stored locally using SQLite; no internet connection is required.

## Key Features

- **User Authentication & Roles** (ADMIN, MANAGER, CLERK)
- **Point‑of‑Sale**: barcode‑style item lookup, search, categories, cart management
- **Draft Orders**: save and recall unfinished sales
- **Discounts**: per‑item or whole‑order, amount/percentage
- **Receipts**: PDF thermal receipts via `reportlab` (fallback to plain‑text)
- **Inventory CRUD**: create/edit/delete products and categories, stock updates
- **Transaction History**: search by ID, filter by status/payment/date
- **Date Picker**: offline calendar built with `tkcalendar`
- **Reporting**: sales/inventory charts with export to CSV, PDF, Excel (`matplotlib` & `openpyxl`)
- **Machine‑learning Suggestions**: offline recommender engine for upsells
- **Settings & User Management**: password changes, database backup/restore, manage users
- **Offline‑first**: works with no network at all

## Technology Stack

- **Language:** Python 3.10+ (tested)
- **GUI:** Tkinter (built‑in; Linux may require `python3-tk`)
- **Database:** SQLite (via `sqlite3` module)
- **Architecture:** DAO/services/views pattern
- **Dependencies:** Pillow, matplotlib, reportlab, openpyxl, tkcalendar (see `requirements.txt`)

## Repository Structure

```
AissasKitchenette-Management-System/
├── aissas_pos_system/           # main application
│   ├── main.py                  # launch script
│   ├── requirements.txt         # Python package list
│   ├── app/                     # application package
│   │   ├── config.py            # paths, theme, defaults
│   │   ├── constants.py         # roles, permissions, messages
│   │   ├── utils.py             # helper functions (hashing, money)
│   │   ├── validators.py        # input validation
│   │   ├── db/                  # data layer
│   │   │   ├── database.py      # SQLite connection & schema
│   │   │   ├── dao.py           # DAOs for each table
│   │   │   ├── schema.py        # incremental schema updates
│   │   │   ├── schema_stable.py # complete table definitions
│   │   │   ├── seed_menu.py     # initial product data
│   │   │   └── seed_users.py    # default admin user
│   │   ├── ml/                  # recommender engine (pure Python)
│   │   ├── models/              # lightweight data models
│   │   ├── services/            # business logic modules
│   │   └── ui/                  # Tkinter view classes and dialogs
│   ├── assets/                  # icons, logo, product images
│   ├── exports/                 # generated CSV/PDF files
│   ├── product_images/          # raw image files for products
│   └── data/                    # runtime database file (`pos.db`)
├── _write_shell.py              # helper script (not part of core app)
├── _write_files.py              # helper script (not part of core app)
└── README.md                    # this file
```

## Installation

1. Clone and `cd` into the repository:
   ```bash
   git clone <repo-url>
   cd AissasKitchenette-Management-System/aissas_pos_system
   ```

2. Create a virtual environment:
   - **Windows:** `python -m venv .venv`
   - **macOS/Linux:** `python3 -m venv .venv`

3. Activate it:
   - **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`
   - **Windows (cmd):** `.\.venv\Scripts\activate.bat`
   - **macOS/Linux:** `source .venv/bin/activate`

4. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Running the Application

From the `aissas_pos_system` directory with the venv activated:

```bash
python main.py
```

A main window appears. Use the seeded admin credentials to log in:

- **Username:** `admin`
- **Password:** `admin123`

These defaults can be changed in `app/config.py` or via the user management screen after logging in.

## Using the System

### Login

- Enter your username/password.
- Only active users may access the system; roles determine available modules.

### POS Screen

1. Search or select a category to find products.
2. Click a product card to add it to the cart.
3. Adjust quantity or remove items in the cart area.
4. Click `Discount` to apply a global or per-item discount.
5. Use `Save as Draft` to store orders that are not yet complete.
6. To complete a sale, click `Checkout`, select payment method, enter amount, and confirm.
7. A PDF receipt is generated and saved under `receipts/`.

### Inventory Module

- **Overview:** key metrics and quick links.
- **Sales:** display historical sales charts, exportable to PDF/Excel.
- **Products:** manage product list; double‑click to edit or delete.
- **Categories:** manage categories indirectly via products or via settings.

### Transactions

- Search by transaction ID.
- Filter by status (Completed, Pending, etc.) or payment method.
- Set a date range using calendar picker or manual `YYYY-MM-DD` entry.
- Open a transaction to view line items and reprint the receipt.
- Resolve outstanding/pending orders with an admin action.

### Reports

- Access from sidebar.
- Generate best‑seller lists, low‑stock reports, etc.
- Export to CSV (visible `exports/`) or PDF/Excel via built‑in options.

### Settings & User Management

- Open via the gear icon or *Settings* menu.
- **Profile:** change your password.
- **Database:** backup or restore the SQLite `.db` file (password protected).
- **Users:** admins may create, deactivate, and assign roles.

### Additional Notes

- **ML Suggestions:** adds likely complementary items to the POS cart based on past orders.
- **Offline Operation:** no external network calls; everything runs locally.

## Troubleshooting

- **Module errors**: ensure the virtual environment is active and `pip install -r requirements.txt` completed successfully.
- **Tkinter not found**: install OS package (`python3-tk` on Debian/Ubuntu).
- **Database locked**: close other instances or delete `data/pos.db` to recreate.
- **Receipt generation fails**: install `reportlab` or fallback text receipts are created.
- **tkcalendar errors**: install it in the same environment; avoid naming conflicts with local files.
- **Permissions**: ensure the program can write to `data/`, `receipts/`, and `exports/`.

## Packaging Suggestion

To build a standalone executable with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile main.py
```

Include asset directories manually via a spec file if distributing.

---

Enjoy using Aissa's Kitchenette Management System! Feel free to modify, extend, or package it for your own business needs.
