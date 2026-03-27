"""
make_icon.py — Convert assets/logo.jpg to assets/logo.ico

Run once before building the EXE:
    python make_icon.py

Produces assets/logo.ico with sizes: 16, 24, 32, 48, 64, 128, 256 px.
PyInstaller and Windows taskbar both need a proper .ico file.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is required.  Run:  pip install Pillow")
        sys.exit(1)

    assets = Path(__file__).parent / "assets"
    src = assets / "logo.jpg"

    if not src.exists():
        # Also try .png
        src = assets / "logo.png"
    if not src.exists():
        print(f"ERROR: Logo not found.  Expected:  {assets / 'logo.jpg'}  or  {assets / 'logo.png'}")
        sys.exit(1)

    out = assets / "logo.ico"

    img = Image.open(src).convert("RGBA")

    # PIL's ICO format accepts a `sizes` list and handles all the resizing internally.
    # This is simpler and more reliable than the append_images approach.
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(str(out), format="ICO", sizes=sizes)
    print(f"Created  {out}  ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
