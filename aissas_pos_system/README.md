# Aissa's Kitchenette Management System

## Overview

Aissa's Kitchenette Management System is a fully offline desktop **Point-of-Sale (POS)** and **Inventory Management System** built with **Python 3 and Tkinter**.

The system integrates:

- Sales processing (POS)
- Inventory management
- Transaction history
- Reporting & analytics
- Role-based user authentication
- Offline machine-learning product recommendations
- Database backup and restore tools

All data is stored locally using **SQLite**. No internet connection is required.

---

# Core Features

## 1. User Authentication & Roles

- Role-based access control:
  - **Admin**
  - **Manager**
  - **Clerk**
- Secure password hashing
- User activation/deactivation
- Password change functionality
- Admin user management panel

---

## 2. Point-of-Sale (POS)

- Product search and category filtering
- Clickable product cards
- Cart management (add, remove, adjust quantity)
- Per-item and whole-order discounts
- Draft order saving and loading
- Change calculation
- PDF receipt generation via `reportlab`
- Receipt auto-opens after checkout
- Machine-learning upsell suggestions

---

## 3. Inventory Management

- Create, edit, delete products
- Manage product categories
- Stock quantity tracking
- Price management
- Product image support
- Low-stock visibility

---

## 4. Transactions Module

- Search transactions by ID
- Filter by status and payment method
- Date range filtering using calendar picker (`tkcalendar`)
- View full transaction details
- Reprint receipts
- Resolve pending/cancelled transactions

---

## 5. Reporting & Analytics

- Sales analytics dashboard
- Charts powered by `matplotlib`
- Best-selling products
- Revenue tracking
- Export options:
  - CSV
  - PDF
  - Excel (`openpyxl`)

---

## 6. Offline Machine Learning Engine

Located in `app/ml/`.

- Pure Python implementation
- Analyzes historical transactions
- Suggests frequently paired items
- Designed for offline environments
- No external APIs used

---

## 7. Database Tools

- Automatic database initialization
- Seeded default admin user
- Seeded sample menu data
- Database backup tool
- Database restore tool
- Local SQLite file storage

Database file location:

```
aissas_pos_system/data/pos.db
```

---

# Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| GUI | Tkinter |
| Database | SQLite |
| Charts | matplotlib |
| PDF Receipts | reportlab |
| Excel Export | openpyxl |
| Images | Pillow |
| Calendar Picker | tkcalendar |
| Architecture | DAO + Services + Views pattern |

---

# Project Structure

```
AissasKitchenette-Management-System/
├── aissas_pos_system/
│   ├── main.py
│   ├── requirements.txt
│   ├── app/
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── utils.py
│   │   ├── validators.py
│   │   ├── db/
│   │   ├── ml/
│   │   ├── models/
│   │   ├── services/
│   │   └── ui/
│   ├── assets/
│   ├── exports/
│   ├── product_images/
│   └── data/
├── README.md
```

---

# Installation Guide

## 1. Clone Repository

```bash
git clone <repository-url>
cd AissasKitchenette-Management-System/aissas_pos_system
```

---

## 2. Create Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

# Running the Application

```bash
python main.py
```

---

# Default Login Credentials

```
Username: admin
Password: admin123
```

⚠ Change this immediately in production use.

---

# Production Deployment Guide

## Build Standalone Executable

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole main.py
```

Include required folders:

- assets/
- product_images/
- exports/
- data/

---

# System Architecture

```
+----------------------------------------------------+
|                    Tkinter UI Layer                |
|----------------------------------------------------|
|  POS | Inventory | Transactions | Reports | Settings
+----------------------↑-----------------------------+
                       |
+----------------------------------------------------+
|                 Services Layer                     |
|----------------------------------------------------|
| AuthService | ReceiptService | ReportService      |
| RecommendationService | Business Rules            |
+----------------------↑-----------------------------+
                       |
+----------------------------------------------------+
|                   DAO Layer                        |
|----------------------------------------------------|
| ProductDAO | OrderDAO | CategoryDAO | DraftDAO    |
+----------------------↑-----------------------------+
                       |
+----------------------------------------------------+
|              Database Layer (SQLite)               |
+----------------------------------------------------+
```

---

# Machine Learning Engine – Technical Overview

The recommendation engine uses **transaction co-occurrence analysis**.

Example:

```
T1: Burger, Fries, Coke
T2: Burger, Coke
T3: Fries, Coke
```

Confidence formula:

```
confidence(A → B) =
    transactions containing (A and B)
    ----------------------------------
    transactions containing (A)
```

This allows the system to suggest frequently paired products during checkout.

Fully offline. No external APIs.

---

# Security & Data Handling

- Password hashing (no plaintext storage)
- Role-based access control
- Local SQLite database
- No internet data transmission
- Recommended daily database backup

---

# Summary

Aissa's Kitchenette Management System is a modular, extensible, and production-ready offline POS and inventory solution designed for small-to-medium retail environments.