@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM ── Single source of truth for version ────────────────────────────────────
REM    Keep in sync with: version_info.txt  (filevers/prodvers/FileVersion/ProductVersion)
REM                       app/config.py     (APP_VERSION)
REM                       installer.iss     (#ifndef MyAppVersion fallback)
set APP_VERSION=2.0-beta

echo.
echo ================================================================
echo   Aissa's Kitchenette POS  --  Build Script  v%APP_VERSION%
echo   Started: %DATE%  %TIME%
echo ================================================================
echo.

REM ════════════════════════════════════════════════════════════════
REM  PRE-FLIGHT CHECKS
REM ════════════════════════════════════════════════════════════════
echo [PRE] Checking prerequisites...

python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found on PATH.
    echo          Install Python 3.10+ and add it to PATH.
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo          %%v

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: PyInstaller not found.
    echo          Run:  pip install pyinstaller
    exit /b 1
)

if not exist "version_info.txt" (
    echo   ERROR: version_info.txt not found.
    echo          This file provides Windows EXE version metadata.
    echo          It must exist next to main.spec.
    exit /b 1
)

if not exist "main.spec" (
    echo   ERROR: main.spec not found.
    exit /b 1
)

if not exist "main.py" (
    echo   ERROR: main.py not found.
    exit /b 1
)

if not exist "assets" (
    echo   ERROR: assets\ directory not found.
    exit /b 1
)

if not exist "make_icon.py" (
    echo   WARNING: make_icon.py not found.
    echo            Skipping icon generation -- using existing assets\logo.ico if present.
    set SKIP_ICON=1
) else (
    set SKIP_ICON=0
)

echo   OK.
echo.

REM ════════════════════════════════════════════════════════════════
REM  BACKUP — preserve previous build outputs before cleaning
REM ════════════════════════════════════════════════════════════════
echo [PRE] Backing up previous build outputs...

if not exist "dist\backup" md "dist\backup"
for %%F in ("dist\*.exe") do copy /y "%%F" "dist\backup\%%~nxF" >nul 2>&1
echo   Done.
echo.

REM ════════════════════════════════════════════════════════════════
REM  PRE-CLEAN
REM ════════════════════════════════════════════════════════════════
echo [PRE] Removing stale outputs and bytecode cache...

if exist "dist\AissasKitchenette.exe"                                  del /f /q "dist\AissasKitchenette.exe"
if exist "dist\AissasKitchenette_Setup.exe"                            del /f /q "dist\AissasKitchenette_Setup.exe"
if exist "dist\AissasKitchenette_POS_v%APP_VERSION%.exe"               del /f /q "dist\AissasKitchenette_POS_v%APP_VERSION%.exe"
if exist "dist\AissasKitchenette_POS_v%APP_VERSION%_Setup.exe"         del /f /q "dist\AissasKitchenette_POS_v%APP_VERSION%_Setup.exe"

REM Remove all __pycache__ dirs and .pyc files under app\
for /d /r "app" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)
del /s /q "app\*.pyc" 2>nul

echo   Done.
echo.

REM ════════════════════════════════════════════════════════════════
REM  STEP 1 — Generate logo.ico
REM ════════════════════════════════════════════════════════════════
echo [1/3] Generating icon (assets\logo.ico) ...

if "!SKIP_ICON!"=="1" (
    if not exist "assets\logo.ico" (
        echo   ERROR: make_icon.py missing AND assets\logo.ico not found.
        echo          Cannot build without an icon file.
        exit /b 1
    )
    echo   Skipped (make_icon.py not found; using existing assets\logo.ico).
) else (
    python make_icon.py
    if errorlevel 1 (
        echo   ERROR: Icon generation failed.
        echo          Make sure Pillow is installed:  pip install Pillow
        exit /b 1
    )
    if not exist "assets\logo.ico" (
        echo   ERROR: make_icon.py ran but assets\logo.ico was not created.
        exit /b 1
    )
    echo   Done.
)
echo.

REM ════════════════════════════════════════════════════════════════
REM  STEP 2 — Build EXE with PyInstaller
REM ════════════════════════════════════════════════════════════════
echo [2/3] Building EXE with PyInstaller (60-120 s typical) ...
echo.

pyinstaller --clean main.spec
if errorlevel 1 (
    echo.
    echo   ERROR: PyInstaller build failed.  See output above.
    echo          Common fixes:
    echo            pip install pyinstaller pillow matplotlib reportlab openpyxl
    exit /b 1
)

if not exist "dist\AissasKitchenette.exe" (
    echo   ERROR: dist\AissasKitchenette.exe was not produced.
    echo          Verify that main.spec sets  name='AissasKitchenette'.
    exit /b 1
)

for %%F in ("dist\AissasKitchenette.exe") do (
    set /a EXE_MB=%%~zF / 1048576
    echo.
    echo   Done.  dist\AissasKitchenette.exe  (!EXE_MB! MB^)
)

REM Create versioned POS-named copy of the EXE
copy /y "dist\AissasKitchenette.exe" "dist\AissasKitchenette_POS_v%APP_VERSION%.exe" >nul
if errorlevel 1 (
    echo   WARNING: Could not create renamed EXE copy.
) else (
    echo   Copied:  dist\AissasKitchenette_POS_v%APP_VERSION%.exe
)
echo.

REM ════════════════════════════════════════════════════════════════
REM  STEP 3 — Build installer with Inno Setup
REM ════════════════════════════════════════════════════════════════
echo [3/3] Building installer ...

set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    if exist "C:\Program Files\Inno Setup 6\ISCC.exe"   set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)

if not defined ISCC (
    echo   Inno Setup 6 not found -- skipping installer step.
    echo   Install from:  https://jrsoftware.org/isdl.php
    echo   Then re-run this script to produce the installer EXE.
    goto :summary
)

REM Pass version from this script so installer.iss stays DRY.
set ISCC_FLAGS=/DMyAppVersion=%APP_VERSION%
!ISCC! !ISCC_FLAGS! installer.iss
if errorlevel 1 (
    echo.
    echo   ERROR: Inno Setup build failed.  Check ISCC output above.
    exit /b 1
)

set SETUP_EXE=dist\AissasKitchenette_POS_v%APP_VERSION%_Setup.exe
if not exist "!SETUP_EXE!" (
    echo   ERROR: Installer not found at !SETUP_EXE! after build.
    echo          Verify OutputBaseFilename in installer.iss matches:
    echo            AissasKitchenette_POS_v{#MyAppVersion}_Setup
    exit /b 1
)

for %%F in ("!SETUP_EXE!") do (
    set /a SETUP_MB=%%~zF / 1048576
    echo   Done.  !SETUP_EXE!  (!SETUP_MB! MB^)
)

:summary
echo.
echo ================================================================
echo   Build complete  --  %DATE%  %TIME%
echo ================================================================
echo.
echo   Output files in dist\:
if exist "dist\AissasKitchenette.exe" (
    for %%F in ("dist\AissasKitchenette.exe") do (
        set /a SZ=%%~zF / 1048576
        echo     EXE      %%~nxF   (!SZ! MB^)
    )
)
if exist "dist\AissasKitchenette_POS_v%APP_VERSION%.exe" (
    for %%F in ("dist\AissasKitchenette_POS_v%APP_VERSION%.exe") do (
        set /a SZ=%%~zF / 1048576
        echo     EXE      %%~nxF   (!SZ! MB^)
    )
)
if exist "dist\AissasKitchenette_POS_v%APP_VERSION%_Setup.exe" (
    for %%F in ("dist\AissasKitchenette_POS_v%APP_VERSION%_Setup.exe") do (
        set /a SZ=%%~zF / 1048576
        echo     Setup    %%~nxF   (!SZ! MB^)
    )
)
echo.
echo   To distribute: share the Setup EXE only.
echo   The EXE alone can also be run directly without installing.
echo.
