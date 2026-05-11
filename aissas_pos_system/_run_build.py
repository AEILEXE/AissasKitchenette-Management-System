"""Build helper that mirrors build.bat but in Python so it works reliably
from a non-interactive cmd.exe child (build.bat's delayed-expansion blocks
mis-parse under some redirection conditions).

Performs the same steps:
  1. python make_icon.py
  2. pyinstaller --clean main.spec
  3. copy dist/AissasKitchenette.exe to versioned filename
  4. ISCC.exe /DMyAppVersion=<v> installer.iss

Reads APP_VERSION from build.bat so we stay in sync with one source of truth.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── Read APP_VERSION from build.bat so we don't duplicate the version ─────────
bat_text = (HERE / "build.bat").read_text(encoding="utf-8", errors="replace")
m = re.search(r"^set APP_VERSION=(.+)$", bat_text, re.M)
if not m:
    print("ERROR: could not read APP_VERSION from build.bat")
    sys.exit(1)
APP_VERSION = m.group(1).strip()
print(f"Building v{APP_VERSION}")

EXE_NAME      = "AissasKitchenette.exe"
EXE_PATH      = HERE / "dist" / EXE_NAME
VERSIONED_EXE = HERE / "dist" / f"AissasKitchenette_POS_v{APP_VERSION}.exe"
SETUP_EXE     = HERE / "dist" / f"AissasKitchenette_POS_v{APP_VERSION}_Setup.exe"

ISCC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
]


def run(cmd, **kw):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    p = subprocess.run(cmd, cwd=str(HERE), **kw)
    if p.returncode != 0:
        print(f"!!! exited {p.returncode}")
        sys.exit(p.returncode)


# ── Pre-clean ────────────────────────────────────────────────────────────────
print("\n[PRE] Removing stale outputs ...")
for p in [
    HERE / "dist" / EXE_NAME,
    VERSIONED_EXE,
    SETUP_EXE,
]:
    if p.exists():
        try:
            p.unlink()
            print(f"  rm {p.name}")
        except Exception as e:
            print(f"  warn: could not delete {p.name}: {e}")

# Clear __pycache__
for root, dirs, _files in os.walk(HERE / "app"):
    for d in list(dirs):
        if d == "__pycache__":
            shutil.rmtree(Path(root) / d, ignore_errors=True)

# ── Step 1: icon ─────────────────────────────────────────────────────────────
print("\n[1/3] Generating icon ...")
run([sys.executable, "make_icon.py"])
assert (HERE / "assets" / "logo.ico").exists(), "assets/logo.ico missing after make_icon.py"

# ── Step 2: PyInstaller ──────────────────────────────────────────────────────
print("\n[2/3] PyInstaller build ...")
run([sys.executable, "-m", "PyInstaller", "--clean", "main.spec"])
assert EXE_PATH.exists(), f"PyInstaller produced no EXE at {EXE_PATH}"

print(f"\n  Copying {EXE_NAME} -> {VERSIONED_EXE.name}")
shutil.copy2(EXE_PATH, VERSIONED_EXE)

# ── Step 3: Inno Setup ───────────────────────────────────────────────────────
iscc = next((p for p in ISCC_CANDIDATES if p.exists()), None)
if iscc is None:
    print("\n[3/3] Inno Setup not installed — skipping installer step.")
else:
    print(f"\n[3/3] Inno Setup build ({iscc}) ...")
    run([str(iscc), f"/DMyAppVersion={APP_VERSION}", "installer.iss"])
    assert SETUP_EXE.exists(), f"Inno Setup produced no installer at {SETUP_EXE}"

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n================================================================")
print(f"  Build complete — v{APP_VERSION}")
print("================================================================")
for p in (EXE_PATH, VERSIONED_EXE, SETUP_EXE):
    if p.exists():
        mb = p.stat().st_size / 1_048_576
        print(f"  {p.name:50s}  ({mb:.1f} MB)")
