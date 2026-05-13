"""
make_icon.py — Generate assets/logo.ico from assets/logo.png or logo.jpg

Run:
    python make_icon.py

Output:
    assets/logo.ico (multi-size ICO for Windows + PyInstaller)
"""

from __future__ import annotations

import sys
from pathlib import Path


def main():
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is required. Install it using: pip install Pillow")
        sys.exit(1)

    base_dir = Path(__file__).parent
    assets_dir = base_dir / "assets"

    png_path = assets_dir / "logo.png"
    jpg_path = assets_dir / "logo.jpg"

    # Find source image
    if png_path.exists():
        src_path = png_path
    elif jpg_path.exists():
        src_path = jpg_path
    else:
        print(f"ERROR: No logo found in {assets_dir}")
        print("Expected: logo.png or logo.jpg")
        sys.exit(1)

    output_path = assets_dir / "logo.ico"

    try:
        img = Image.open(src_path).convert("RGBA")

        # Standard Windows icon sizes
        sizes = [
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ]

        img.save(output_path, format="ICO", sizes=sizes)

        size_kb = output_path.stat().st_size // 1024
        print(f"SUCCESS: Created {output_path} ({size_kb} KB)")

    except Exception as e:
        print(f"ERROR: Failed to generate icon -> {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()