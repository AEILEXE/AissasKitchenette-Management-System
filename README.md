# Aissa's Kitchenette Management System

## Project Description

### What the System Is
Aissa's Kitchenette Management System is a comprehensive Point-of-Sale (POS) application built with Python and Tkinter. It provides a user-friendly desktop interface for managing sales, inventory, and transactions in a fully offline environment.

### What Problem It Solves
This system addresses the challenges of manual inventory tracking, order management, and sales recording in small businesses. It eliminates paperwork, reduces errors in calculations, and provides real-time insights into business operations without requiring internet connectivity.

### Who It Is For
This application is designed for small business owners, particularly those running kitchenettes, cafes, retail stores, or similar establishments that need efficient offline management of products, orders, and sales data.

## Features / Functions

The system includes the following main functions:

- **User Authentication**: Secure login system to protect access to the POS interface
- **Product Management**: Add, edit, and delete products with stock level tracking
- **Category Management**: Organize products into categories for better organization
- **Order Processing**: Create and manage customer orders with dynamic cart functionality
- **Draft Orders**: Save incomplete orders for later completion
- **Discount System**: Apply discounts to individual items or entire orders
- **Payment Processing**: Handle checkout and calculate totals automatically
- **Receipt Generation**: Create and print transaction receipts
- **Transaction History**: View and search past sales records
- **Inventory Tracking**: Monitor stock levels and manage product availability
- **Reporting**: Generate reports on sales and inventory data
- **Offline Operation**: All data stored locally using SQLite database

## Installation

Follow these step-by-step instructions to set up the project on your computer:

1. **Clone the Repository**
   ```
   git clone <repository-url>
   cd AissasKitchenette-Management-System
   ```

2. **Navigate into the Project Directory**
   ```
   cd aissas_pos_system
   ```

3. **Create a Virtual Environment**
   - **Windows**:
     ```
     python -m venv .venv
     ```
   - **macOS/Linux**:
     ```
     python3 -m venv .venv
     ```

4. **Activate the Virtual Environment**
   - **Windows**:
     ```
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS/Linux**:
     ```
     source .venv/bin/activate
     ```

5. **Install Dependencies**
   ```
   pip install -r requirements.txt
   ```

   The `requirements.txt` file contains a list of all Python packages required for the project to run. It specifies the package names and their minimum versions. Running `pip install -r requirements.txt` automatically downloads and installs all these dependencies, ensuring the project has everything it needs to function properly.

## How to Run

Once installation is complete, start the application with this command:

```
python main.py
```

The application window will open, and you can log in with the default credentials (username: admin, password: admin123).

## Project Structure

Here's a brief overview of the important files and folders in the repository:

- `aissas_pos_system/` - Main application directory
  - `main.py` - Entry point script to launch the application
  - `requirements.txt` - List of Python dependencies
  - `app/` - Core application package
    - `config.py` - Application configuration settings
    - `constants.py` - Constant values used throughout the app
    - `utils.py` - Utility functions
    - `validators.py` - Input validation functions
    - `db/` - Database layer
      - `database.py` - Database connection and initialization
      - `dao.py` - Data Access Objects for database operations
      - `schema.py` - Database table definitions
      - `seed_*.py` - Scripts to populate initial data
    - `models/` - Data model classes
      - `user.py`, `product.py`, `order.py`, etc. - Business object definitions
    - `services/` - Business logic layer
      - `auth_service.py` - User authentication
      - `pos_service.py` - Point of sale operations
      - `inventory_service.py` - Inventory management
      - `report_service.py` - Report generation
    - `ui/` - User interface components
      - `app_window.py` - Main application window
      - `login_view.py` - Login screen
      - `pos_view.py` - Point of sale interface
      - `inventory_view.py` - Inventory management screens
      - `reports_view.py` - Reporting interface
      - `theme.py` - UI styling and themes
- `assets/` - Static assets like icons
- `product_images/` - Product image files
- `exports/` - Generated reports and exports
- `data/` - Additional data files

## Troubleshooting

### Common Issues and Fixes

1. **Python Not Found Error**
   - Ensure Python 3.10 or higher is installed
   - Check that `python` or `python3` command is available in your terminal
   - On Windows, you may need to add Python to your PATH during installation

2. **Virtual Environment Issues**
   - Make sure you're in the correct directory when creating/activating the virtual environment
   - On Windows, ensure you're using PowerShell or Command Prompt with execution policy allowing scripts
   - Try deactivating and reactivating if activation fails

3. **Dependencies Installation Fails**
   - Ensure pip is up to date: `python -m pip install --upgrade pip`
   - Check your internet connection
   - Some packages may require additional system libraries (e.g., Pillow may need image libraries)

4. **Application Won't Start**
   - Verify all dependencies are installed correctly
   - Check that you're running from the `aissas_pos_system` directory
   - Ensure no other instances of the application are running

5. **Database Errors**
   - The application creates its database automatically on first run
   - If you encounter database issues, try deleting any existing `.db` files in the data directory
   - Ensure the application has write permissions in its directory

6. **UI Issues (e.g., Tkinter not working)**
   - Tkinter comes built-in with Python, but on some Linux distributions you may need to install it separately
   - Ubuntu/Debian: `sudo apt-get install python3-tk`
   - Ensure your display environment supports GUI applications

If you encounter issues not covered here, check the application logs or try reinstalling the dependencies.
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

