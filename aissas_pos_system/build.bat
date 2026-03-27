@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ========================================
echo  Aissa's Kitchenette -- Build Script
echo ========================================
echo.

REM ── Step 1: Generate logo.ico from logo.jpg ─────────────────────────────
echo [1/3] Generating icon (assets\logo.ico)...
python make_icon.py
if errorlevel 1 (
    echo ERROR: Icon generation failed.
    echo        Make sure Pillow is installed:  pip install Pillow
    exit /b 1
)
echo       Done.
echo.

REM ── Step 2: Build the EXE via PyInstaller ───────────────────────────────
echo [2/3] Building EXE with PyInstaller...
pyinstaller --clean main.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    echo        Make sure PyInstaller is installed:  pip install pyinstaller
    exit /b 1
)
echo       Done.  EXE:  dist\AissasKitchenette.exe
echo.

REM ── Step 3: Build the installer with Inno Setup (optional) ──────────────
echo [3/3] Building installer...

set ISCC_64="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set ISCC_32="C:\Program Files\Inno Setup 6\ISCC.exe"

if exist %ISCC_64% (
    %ISCC_64% installer.iss
) else if exist %ISCC_32% (
    %ISCC_32% installer.iss
) else (
    echo       Inno Setup 6 not found -- skipping installer step.
    echo       Install from: https://jrsoftware.org/isdl.php
    echo       Then re-run this script to also produce the installer.
    goto :done
)

if errorlevel 1 (
    echo ERROR: Installer build failed.
    exit /b 1
)
echo       Done.  Installer:  dist\AissasKitchenette_Setup.exe

:done
echo.
echo ========================================
echo  Build complete!
echo ========================================
echo.
