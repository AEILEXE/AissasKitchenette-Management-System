@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set APP_VERSION=3.0

echo.
echo ================================================================
echo   Aissa's Kitchenette POS  --  Build Script  v%APP_VERSION%
echo   Started: %DATE%  %TIME%
echo ================================================================
echo.

REM =========================
REM PRE-FLIGHT CHECKS
REM =========================
echo PRE CHECK: Checking prerequisites...

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo Python: %%v

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller not found
    exit /b 1
)

echo OK
echo.

REM =========================
REM BACKUP
REM =========================
echo PRE BACKUP: Backing up previous build outputs...

if not exist "dist\backup" md "dist\backup"
for %%F in ("dist\*.exe") do copy /y "%%F" "dist\backup\%%~nxF" >nul 2>&1

echo Done
echo.

REM =========================
REM CLEAN
REM =========================
echo PRE CLEAN: Removing stale outputs and cache...

if exist "dist\main.exe" del /f /q "dist\main.exe"
if exist "dist\AissasKitchenette_Setup.exe" del /f /q "dist\AissasKitchenette_Setup.exe"

for /d /r "app" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

del /s /q "app\*.pyc" 2>nul

echo Done
echo.

REM =========================
REM STEP 1 ICON
REM =========================
echo STEP 1: Generating icon

pushd "%~dp0"

python make_icon.py
if errorlevel 1 (
    echo ERROR: Icon generation failed
    popd
    exit /b 1
)

if not exist "assets\logo.ico" (
    echo ERROR: Icon not created
    popd
    exit /b 1
)

popd

echo Icon ready
echo.

REM =========================
REM STEP 2 BUILD EXE
REM =========================
echo STEP 2: Building EXE

pyinstaller --clean main.spec
if errorlevel 1 (
    echo ERROR: PyInstaller failed
    exit /b 1
)

if not exist "dist\main.exe" (
    echo ERROR: EXE not generated
    exit /b 1
)

echo Build successful
echo.

REM =========================
REM VERSION COPY
REM =========================
copy /y "dist\main.exe" "dist\AissasKitchenette_POS_v%APP_VERSION%.exe" >nul

echo Copied versioned EXE
echo.

REM =========================
REM STEP 3 INSTALLER
REM =========================
echo STEP 3: Building installer

set ISCC=

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo WARNING: Inno Setup not found, skipping installer
    goto summary
)

%ISCC% /DMyAppVersion=%APP_VERSION% installer.iss

if errorlevel 1 (
    echo ERROR: Installer build failed
    exit /b 1
)

echo Installer created
echo.

REM =========================
REM SUMMARY
REM =========================
:summary
echo.
echo ================================================================
echo BUILD COMPLETE
echo ================================================================
echo.

if exist "dist\main.exe" (
    echo EXE: main.exe
)

if exist "dist\AissasKitchenette_POS_v%APP_VERSION%.exe" (
    echo EXE: Versioned build created
)

if exist "dist\AissasKitchenette_POS_v%APP_VERSION%_Setup.exe" (
    echo SETUP: Installer created
)

echo.
echo DONE. You can distribute the Setup EXE.
echo.