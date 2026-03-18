"""
Generates bridge/icon.png and bridge/icon.ico before PyInstaller bundles them.
Run this once before building: python build_icons.py
GitHub Actions runs this automatically before pyinstaller.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def make_icon(size=256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Dark circle background
    d.ellipse([4, 4, size - 4, size - 4], fill="#1a1a2e")

    # Green ring
    d.ellipse([4, 4, size - 4, size - 4], outline="#1D9E75", width=size // 16)

    # White "F" centred
    font_size = size // 2
    font = None
    for path in [
        "C:/Windows/Fonts/arialbd.ttf",           # Windows
        "/System/Library/Fonts/Helvetica.ttc",    # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    ]:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                pass

    if font is None:
        font = ImageFont.load_default()

    bbox = d.textbbox((0, 0), "F", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    d.text(
        ((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1]),
        "F",
        fill="white",
        font=font,
    )
    return img


if __name__ == "__main__":
    out = Path("bridge")
    out.mkdir(exist_ok=True)

    icon = make_icon(256)
    icon.save(out / "icon.png")
    print("Saved bridge/icon.png")

    sizes = [16, 32, 48, 64, 128, 256]
    icons = [make_icon(s) for s in sizes]
    icons[0].save(
        out / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=icons[1:],
    )
    print("Saved bridge/icon.ico")
    print("Done.")
