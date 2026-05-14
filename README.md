# Aissa's Kitchenette — POS & Management System

> A full-featured Point of Sale, Inventory, and Business Management
> System built for **Aissa's Kitchenette** — a local Filipino food
> business. Designed for real-world daily operations with a clean,
> role-based desktop interface.

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![Tkinter](https://img.shields.io/badge/UI-Tkinter-lightgrey)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite)
![PyInstaller](https://img.shields.io/badge/Build-PyInstaller-purple)
![Version](https://img.shields.io/badge/Version-3.0-orange)

---

## Features

- **Point of Sale (POS)** — Fast order taking with category/subcategory
  product browsing, discount support, and receipt generation (PDF)
- **Inventory Management** — Track products, raw materials, stock
  levels, and low-stock alerts
- **Sales Transactions** — Full transaction history with void support
  and audit logging
- **Reports & Analytics** — Sales charts, revenue by category,
  top sellers, payment breakdowns, and exportable reports (PDF/Excel)
- **User Management** — Role-based access control (Admin, Manager,
  Cashier, Viewer) with account settings
- **Dashboard** — Real-time KPIs, best sellers, and low-stock summary
- **ML Recommender** — Co-purchase product recommendations at checkout
- **Backup & Restore** — One-click database backup and restore

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| UI Framework | Tkinter + ttk |
| Database | SQLite 3 |
| Charts | Matplotlib |
| PDF Generation | ReportLab |
| Excel Export | OpenPyXL |
| ML | Scikit-learn (co-purchase recommender) |
| Build | PyInstaller + Inno Setup 6 |

---

## Screenshots

> *(Add screenshots here)*

---

## Installation

### Option A — Installer (recommended)
1. Download `AissasKitchenette_POS_v3.0_Setup.exe` from
   [Releases](../../releases)
2. Run the installer and follow the steps
3. Launch from the desktop shortcut or Start Menu

### Option B — Standalone EXE
1. Download `AissasKitchenette_POS_v3.0.exe` from
   [Releases](../../releases)
2. Run directly — no installation needed

### Option C — Run from source
```bash
git clone https://github.com/AEILEXE/aissas-kitchenette-pos.git
cd aissas-kitchenette-pos/aissas_pos_system
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Default Login

| Role | Username | Password |
|------|----------|----------|
| Administrator | admin | admin123 |

> Change the default password after first login.

---

## Building from Source

```bash
cd aissas_pos_system
python _run_build.py
```

Output files will be in `dist/`:
- `AissasKitchenette_POS_v3.0.exe` — versioned standalone
- `AissasKitchenette_POS_v3.0_Setup.exe` — installer

---

## Project Structure

```
aissas-kitchenette-pos/
├── aissas_pos_system/
│   ├── main.py                    # Entry point
│   ├── app/
│   │   ├── ui/                    # All Tkinter views
│   │   ├── db/                    # DAO, schema, seeding
│   │   ├── services/              # Business logic
│   │   ├── models/                # Data models
│   │   └── ml/                    # Recommender engine
│   ├── assets/                    # Icons, logo, images
│   └── product_images/            # Product photos
├── dist/                          # Built executables (git-ignored)
├── installer.iss                  # Inno Setup script
├── LICENSE
└── README.md
```

---

## Author

Developed by **[AEILEXE](https://github.com/AEILEXE)**
Built as a real-world desktop application for a local Filipino
food business.

---

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for details.

---

*Aissa's Kitchenette POS & Management System v3.0*
