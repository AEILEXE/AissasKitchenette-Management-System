# Aissas Kitchenette — POS Management System

## Project Overview

Aissas Kitchenette POS Management System is a comprehensive Point-of-Sale (POS) application designed for small businesses and offline retail setups. It enables efficient management of products, categories, orders, and transactions in a fully offline, desktop-based environment. The system is built to handle daily operations such as product inventory, order processing, payment handling, and receipt generation without requiring an internet connection. It is ideal for small kitchenettes, cafes, or retail stores that need a reliable, local solution for managing sales and inventory.

## Features

- **User Authentication**: Secure login system for authorized access to the POS interface.
- **Product Management**: Add, edit, delete products, and manage stock levels with real-time updates.
- **Category Management**: Organize products into categories for easy navigation and display.
- **Order System**: Add items to cart, update quantities, and remove items dynamically.
- **Draft Orders**: Auto-save or manually save orders as drafts for later completion.
- **Discount System**: Apply discounts to individual items or entire orders.
- **Checkout & Payment**: Process payments and calculate totals automatically.
- **Receipt Printing**: Generate and print receipts for transactions.
- **Transaction History**: View and manage past transactions with detailed records.
- **Search and Filter**: Search for items and filter transactions by various criteria.
- **Date Filtering**: Filter transactions by date range using a calendar selector (From – To).
- **Scrollable Item Lists**: Navigate through product lists with smooth scrolling.
- **Clickable Item Cards**: Interactive product cards for easy selection.
- **Offline Database Storage**: All data is stored locally using SQLite, ensuring no internet dependency.

## How the System Works (Step-by-Step Flow)

1. **User Logs In**: Start by logging into the system using valid credentials (default demo: username: admin, password: admin123).
2. **Select or Search Products**: Browse categories or use the search box to find products. The interface displays a responsive grid of items.
3. **Add to Order**: Click on a product card to add it to the current order. Quantities can be adjusted directly in the cart.
4. **Update Quantities**: Modify item quantities dynamically; the total updates in real-time.
5. **Apply Discounts**: Optionally apply discounts to items or the overall order.
6. **Save as Draft**: Save the current order as a draft for later retrieval and completion.
7. **Checkout**: Proceed to checkout where the total is calculated automatically, including any discounts.
8. **Process Payment**: Complete the transaction; the system records the sale.
9. **Generate Receipt**: A receipt is generated and can be printed or opened automatically.
10. **View History**: Access transaction history to search, filter, and review past sales.

## System Architecture (Simple Explanation)

The system is built using Python for its core logic and user interface. It utilizes Tkinter for the graphical user interface (GUI), providing a native desktop experience. Data is stored in a local SQLite database, ensuring fast and reliable offline storage. The application follows a DAO (Data Access Object) pattern for database interactions, separating business logic from data handling. All components are designed for local execution, with no internet connectivity required, making it suitable for offline environments.

## Installation Guide

1. Clone the repository:
   ```
   git clone <repository-url>
   cd AissasKitchenette-Management-System
   ```

2. Create and activate a Python virtual environment (recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:
   ```powershell
   cd aissas_pos_system
   pip install -r requirements.txt
   ```

4. Run the application:
   ```powershell
   python main.py
   ```

## System Requirements

### Software Requirements
- **Operating System**: Windows 10 or Windows 11
- **Python Version**: Python 3.10 or higher
- **Package Manager**: pip (comes with Python)
- **Required Python Libraries**:
  - tkinter (built-in with Python)
  - sqlite3 (built-in with Python)
  - Pillow (version 9.0.0 or higher) - for image handling
  - matplotlib (version 3.5.0 or higher) - for reporting and charts
  - pyinstaller (version 5.0.0 or higher) - optional, for building standalone executables

### Hardware Requirements
- **Minimum RAM**: 4GB
- **Free Disk Space**: 500MB
- **Screen Resolution**: Minimum 1366x768
- **Optional Hardware**:
  - Thermal printer for receipt printing
  - Barcode scanner for quick product entry
  - Receipt printer for physical receipts

## Folder Structure

- `aissas_pos_system/` — Main application code and resources
  - `app/` — Python package containing UI, services, and database code
  - `db/` — Database-related files and schemas
  - `services/` — Business logic services
  - `ui/` — User interface components
  - `main.py` — Entry point to run the application
- `product_images/`, `data/`, `exports/` — Assets and output folders for images, backups, and reports

## Future Improvements

- Inventory analytics and reporting dashboards
- Offline machine learning for sales prediction
- Customer purchase tracking and loyalty programs
- Low stock alerts and automated reordering suggestions
- Enhanced sales reports with charts and export options
- Multi-user support with role-based access
- Integration with external devices like cash drawers

## Notes / UI Tips

- Use the search box in the POS screen (shows a muted placeholder `Search…` when empty).
- Mouse wheel scrolling works by hovering over the Categories, Items, or Current Order areas (no need to click first).
- The Transactions view has labeled date filters (`From` / `To`) and placeholders `YYYY-MM-DD` to make filtering easier.
- Printing a receipt will generate a text receipt and attempt to open it automatically on your platform; if auto-open fails, the path to the saved receipt will be shown.

If you need help running the app or adjusting settings (e.g., switching to a packaged PDF receipt printer), feel free to ask for step-by-step instructions.

