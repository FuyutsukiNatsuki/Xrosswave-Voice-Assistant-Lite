"""Generate the app icon (assets/icon.ico).

Draws a simple on-brand mark: a dark rounded tile with a yellow pitch curve and
small colored formant dots, matching the GUI's plot colors. Re-run to regenerate;
replace assets/icon.ico with your own .ico anytime.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\make_icon.py
"""

import math
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
SIZE = 256
BG = (30, 30, 30, 255)
PITCH = (255, 221, 0, 255)       # yellow F0 curve
FORMANTS = [(255, 85, 85), (85, 255, 85), (85, 255, 255), (255, 85, 255)]


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 6
    d.rounded_rectangle([2, 2, size - 3, size - 3], radius=r, fill=BG)

    # Pitch curve: a rising sine sweep across the tile.
    pad = size * 0.16
    width = max(2, size // 24)
    pts = []
    n = 80
    for i in range(n + 1):
        x = pad + (size - 2 * pad) * i / n
        phase = i / n
        y = size / 2 - math.sin(phase * math.pi * 2.2) * (size * 0.18) * (0.5 + phase)
        pts.append((x, y))
    d.line(pts, fill=PITCH, width=width, joint="curve")

    # Formant dots along the bottom third.
    dot = max(3, size // 18)
    for j, color in enumerate(FORMANTS):
        cx = pad + (size - 2 * pad) * (0.18 + 0.22 * j)
        cy = size * (0.72 - 0.05 * j)
        d.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=color + (255,))
    return img


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    base = render(SIZE)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(OUT, format="ICO", sizes=sizes)
    print(f"wrote {os.path.abspath(OUT)} ({len(sizes)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
