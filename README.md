# Aissas Kitchenette — POS Management System

This repository contains a small Point-of-Sale (POS) application used for managing categories, products, draft orders, and transactions for Aissa's Kitchenette. The application is a Tkinter-based desktop app backed by a simple SQLite database.

Key features
- Categories and responsive product grid (1-3 columns depending on window width)
- Add products to cart, change quantity, apply discounts, save/load drafts
- Transactions list with searchable IDs, date filters (From/To), and status/payment filters
- Resolve pending transactions (Reference No.) and print/open receipts

Quick start
1. Create and activate a Python virtual environment (recommended):

	```powershell
	python -m venv .venv
	.\\.venv\\Scripts\\Activate.ps1
	```

2. Install dependencies (from the `aissas_pos_system` folder):

	```powershell
	pip install -r aissas_pos_system\\requirements.txt
	```

3. Run the app:

	```powershell
	cd aissas_pos_system
	python main.py
	```

Notes / UI tips
- Use the search box in the POS screen (shows a muted placeholder `Search…` when empty).
- Mouse wheel scrolling works by hovering over the Categories, Items, or Current Order areas (no need to click first).
- The Transactions view has labeled date filters (`From` / `To`) and placeholders `YYYY-MM-DD` to make filtering easier.
- Printing a receipt will generate a text receipt and attempt to open it automatically on your platform; if auto-open fails the path to the saved receipt will be shown.

Project structure
- `aissas_pos_system/` — main application code and resources
- `aissas_pos_system/app/` — Python package with UI, services, and DB code
- `product_images/`, `data/`, `exports/` — assets and output folders

If you want help running the app or adjusting settings (e.g., switching to a packaged PDF receipt printer), ask and I can add step-by-step instructions.

