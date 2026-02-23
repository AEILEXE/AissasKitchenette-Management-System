# Aissas POS System

This folder contains the runnable POS application. Use the instructions below to set up and run the app locally.

Requirements
- Python 3.8+
- See `requirements.txt` for third-party packages.

Run locally
1. From project root create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Start the application:

   ```powershell
   python main.py
   ```

Notes
- The main app is `main.py`. UI files are under `app/ui/`.
- Database files and exports are saved under `data/` and `exports/` respectively.
- Receipts are generated as plain text files and the app will try to open them automatically using the OS default viewer.

If you want a packaged executable or additional deployment instructions, I can add them.
# Alissa's POS System (Offline)

## Run
python main.py

## Tech
- Python 3.10+
- Tkinter GUI
- SQLite (offline local database)

## Default demo login
- username: admin
- password: admin123

## Optional dependencies
pip install pillow matplotlib pyinstaller

## Export files
CSV exports go into /exports
