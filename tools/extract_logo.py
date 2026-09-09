"""Extract the shift.AI mark from the supplied brand image as a transparent PNG.

Keeps only the left glyph, drops the wordmark/tagline, removes the white
background (with proper alpha un-premultiplication so anti-aliased edges stay
clean), suppresses the soft drop shadow, and writes app icons.

Run: python tools/extract_logo.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SRC = Path(r"C:\Users\sarth\Downloads\ChatGPT Image Sep 8, 2026, 09_57_56 PM.png")
ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "frontend" / "public" / "brand"
APP = ROOT / "frontend" / "app"
DOWNLOADS = Path.home() / "Downloads"

# Region that contains only the mark (measured with tools/analyze_logo.py).
MARK_BOX = (190, 250, 460, 680)
NAVY = (11, 19, 32)
ORANGE = (255, 122, 0)


def cutout(image: Image.Image) -> Image.Image:
    """Turn a white-background RGB image into a clean RGBA cutout."""
    image = image.convert("RGB")
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    src = image.load()
    dst = out.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = src[x, y]
            lo, hi = min(r, g, b), max(r, g, b)
            alpha = 1.0 - lo / 255.0
            if alpha <= 0.02:
                continue
            # Drop the grey drop-shadow: the mark itself is strongly saturated.
            if (hi - lo) < 12 and alpha < 0.9:
                continue
            inv = 255.0 * (1.0 - alpha)
            colour = tuple(
                min(255, max(0, round((channel - inv) / alpha)))
                for channel in (r, g, b)
            )
            dst[x, y] = (*colour, min(255, round(alpha * 255)))
    return out


def square(image: Image.Image, size: int, pad_ratio: float = 0.06) -> Image.Image:
    """Fit a trimmed cutout into a transparent square canvas."""
    trimmed = image.crop(image.getbbox())
    inner = round(size * (1 - pad_ratio * 2))
    scale = min(inner / trimmed.width, inner / trimmed.height)
    resized = trimmed.resize(
        (max(1, round(trimmed.width * scale)), max(1, round(trimmed.height * scale))),
        Image.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(
        resized,
        ((size - resized.width) // 2, (size - resized.height) // 2),
        resized,
    )
    return canvas


def rounded_tile(mark: Image.Image, size: int, radius_ratio: float = 0.22) -> Image.Image:
    """Mark on a navy rounded tile (used for the Apple touch icon)."""
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=round(size * radius_ratio),
        fill=(*NAVY, 255),
    )
    glyph = square(mark, size, pad_ratio=0.22)
    tile.alpha_composite(glyph)
    return tile


def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
    )
    for name in candidates:
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def social_card(mark: Image.Image) -> Image.Image:
    """1200x630 share card: navy field, mark, wordmark, tagline."""
    width, height = 1200, 630
    card = Image.new("RGB", (width, height), NAVY)
    draw = ImageDraw.Draw(card)
    for y in range(height):  # soft vertical lift
        t = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=(
                round(NAVY[0] + 9 * t),
                round(NAVY[1] + 12 * t),
                round(NAVY[2] + 18 * t),
            ),
        )
    draw.rectangle((0, 0, width, 6), fill=ORANGE)

    glyph = square(mark, 168, pad_ratio=0.0)
    card.paste(glyph, (96, 150), glyph)

    title = load_font(96)
    tagline = load_font(34, bold=False)
    draw.text((300, 150), "shift", font=title, fill=(255, 255, 255))
    shift_width = draw.textlength("shift", font=title)
    draw.text((300 + shift_width, 150), ".AI", font=title, fill=ORANGE)
    draw.text(
        (300, 272),
        "Plan smarter. Build what matters.",
        font=tagline,
        fill=(198, 208, 222),
    )
    draw.text(
        (96, 470),
        "Evidence-led strategy · Diagnose before you build · Independent red-team review",
        font=load_font(28, bold=False),
        fill=(139, 152, 170),
    )
    return card


def main() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    source = Image.open(SRC)
    mark = cutout(source.crop(MARK_BOX))

    trimmed = mark.crop(mark.getbbox())
    trimmed.save(BRAND / "logo-mark.png")
    square(mark, 1024).save(BRAND / "logo-mark-square.png")
    square(mark, 512).save(BRAND / "logo-mark-512.png")
    square(mark, 256).save(APP / "icon.png")
    rounded_tile(mark, 180).save(APP / "apple-icon.png")
    social_card(mark).save(APP / "opengraph-image.png", optimize=True)
    if DOWNLOADS.exists():
        trimmed.save(DOWNLOADS / "shiftai-logo-mark-transparent.png")

    print("mark (trimmed):", trimmed.size)
    print("wrote:")
    for path in (
        BRAND / "logo-mark.png",
        BRAND / "logo-mark-square.png",
        BRAND / "logo-mark-512.png",
        APP / "icon.png",
        APP / "apple-icon.png",
        APP / "opengraph-image.png",
        DOWNLOADS / "shiftai-logo-mark-transparent.png",
    ):
        print(" ", path)


if __name__ == "__main__":
    main()
