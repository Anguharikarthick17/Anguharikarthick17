#!/usr/bin/env python3
"""Render a local portrait as a compact, static monochrome ASCII SVG."""

from __future__ import annotations

import argparse
import math
import os
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "ascii-portrait.svg"
RAMP = "@%#*+=-:. "
CHAR_ASPECT_RATIO = 0.5
CELL_WIDTH = 5
CELL_HEIGHT = 8


def grayscale_to_ascii(value: int) -> str:
    """Map a grayscale value from dark/dense to light/sparse ASCII."""
    if not 0 <= value <= 255:
        raise ValueError("grayscale value must be between 0 and 255")
    index = round(value / 255 * (len(RAMP) - 1))
    return RAMP[index]


def subject_bounds(image: Image.Image, threshold: int, padding: float = 0.03) -> tuple[int, int, int, int]:
    mask = image.point(lambda pixel: 255 if pixel < threshold else 0)
    bounds = mask.getbbox()
    if bounds is None:
        return (0, 0, image.width, image.height)
    left, top, right, bottom = bounds
    pad_x = round((right - left) * padding)
    pad_y = round((bottom - top) * padding)
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(image.width, right + pad_x),
        min(image.height, bottom + pad_y),
    )


def image_to_ascii(
    photo: Path,
    columns: int,
    brightness: float,
    contrast: float,
    crop: str = "subject",
    background_threshold: int = 232,
) -> list[str]:
    if columns < 1:
        raise ValueError("columns must be positive")
    if not 0 <= background_threshold <= 255:
        raise ValueError("background_threshold must be between 0 and 255")
    with Image.open(photo) as source:
        image = ImageOps.exif_transpose(source).convert("L")
        if crop == "subject":
            image = image.crop(subject_bounds(image, background_threshold))
        elif crop != "full":
            raise ValueError("crop must be 'subject' or 'full'")
        image = ImageOps.autocontrast(image, cutoff=0.5)
        image = ImageEnhance.Contrast(image).enhance(contrast)
        image = ImageEnhance.Brightness(image).enhance(brightness)

        width, height = image.size
        rows = max(1, round(columns * height / width * CHAR_ASPECT_RATIO))
        image = image.resize((columns, rows), Image.Resampling.LANCZOS)
        pixels = image.tobytes()

    return [
        "".join(grayscale_to_ascii(pixels[row * columns + col]) for col in range(columns))
        for row in range(rows)
    ]


def render_svg(rows: list[str] | None, columns: int, label: str) -> str:
    text_x, text_y = 28, 76
    if rows is None:
        rows = []
    width = max(310, columns * CELL_WIDTH + 56)
    height = max(220, len(rows) * CELL_HEIGHT + 102)
    content = []

    if label:
        content.append(
            f'<text x="{width / 2:g}" y="{height / 2 - 4:g}" class="placeholder" '
            f'text-anchor="middle">{escape(label)}</text>'
        )
        content.append(
            f'<text x="{width / 2:g}" y="{height / 2 + 22:g}" class="hint" '
            'text-anchor="middle">Set --photo to a local image to generate your portrait.</text>'
        )
    else:
        for index, row in enumerate(rows):
            content.append(
                f'<text x="{text_x}" y="{text_y + index * CELL_HEIGHT}" '
                f'class="ascii-row">{escape(row)}</text>'
            )

    title = "AHK portrait study"
    description = (
        "Portrait placeholder. Supply a local photo with scripts/make_ascii_svg.py --photo."
        if label
        else "A compact monochrome ASCII rendering of a locally supplied portrait."
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{title}</title>
  <desc id="desc">{description}</desc>
  <style>
    .background {{ fill: #080B0A; }}
    .frame {{ fill: none; stroke: #34433C; stroke-width: 1; }}
    .rule {{ stroke: #26372F; stroke-width: 1; }}
    .brand {{ fill: #67E6A4; font: 10px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 1px; }}
    .meta {{ fill: #84918A; font: 9px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .5px; }}
    .ascii-row {{ fill: #67E6A4; font: 8px ui-monospace, SFMono-Regular, Menlo, monospace;
      white-space: pre; }}
    .placeholder {{ fill: #67E6A4; font: 600 14px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .hint {{ fill: #84918A; font: 10px ui-monospace, SFMono-Regular, Menlo, monospace; }}
  </style>
  <rect class="background" width="{width}" height="{height}" rx="10"/>
  <rect class="frame" x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="10"/>
  <path class="rule" d="M16 48H{width - 16}"/>
  <text class="brand" x="22" y="31">AHK <tspan class="meta">//</tspan> PORTRAIT</text>
  <text class="meta" x="{width - 22}" y="31" text-anchor="end">GENZLOG / LOCAL</text>
  <path class="brand" d="M16 15h14v1H16zM16 15v14h1V15zM{width - 30} {height - 16}h14v1h-14zM{width - 17} {height - 29}h1v14h-1z"/>
  {''.join(content)}
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path, help="Path to a local portrait photo (never copied by this script)")
    parser.add_argument("--output", type=Path, default=OUTPUT, help=f"Output SVG (default: {OUTPUT})")
    parser.add_argument("--columns", type=int, default=160, help="ASCII character columns (default: 160)")
    parser.add_argument("--brightness", type=float, default=1.0, help="Brightness multiplier (default: 1.0)")
    parser.add_argument("--contrast", type=float, default=1.15, help="Contrast multiplier (default: 1.15)")
    parser.add_argument(
        "--crop",
        choices=("subject", "full"),
        default="subject",
        help="Crop to darker foreground content or use the full image (default: subject)",
    )
    parser.add_argument(
        "--background-threshold",
        type=int,
        default=232,
        help="Grayscale threshold used to find the subject crop (default: 232)",
    )
    args = parser.parse_args()
    if args.columns < 8 or args.columns > 160:
        parser.error("--columns must be between 8 and 160")
    if args.brightness <= 0 or args.contrast <= 0 or not math.isfinite(args.brightness + args.contrast):
        parser.error("--brightness and --contrast must be finite positive numbers")
    if not 0 <= args.background_threshold <= 255:
        parser.error("--background-threshold must be between 0 and 255")

    rows = None
    placeholder = "PORTRAIT NOT CONFIGURED"
    if args.photo is not None:
        if not args.photo.is_file():
            parser.error(f"photo file does not exist: {args.photo}")
        try:
            rows = image_to_ascii(
                args.photo,
                args.columns,
                args.brightness,
                args.contrast,
                args.crop,
                args.background_threshold,
            )
        except (OSError, ValueError) as error:
            parser.error(f"cannot read portrait image: {error}")
        placeholder = ""

    args.output.parent.mkdir(parents=True, exist_ok=True)
    svg = render_svg(rows, args.columns, placeholder)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent, delete=False
    ) as output_file:
        temporary_path = Path(output_file.name)
        output_file.write(svg)
    try:
        os.replace(temporary_path, args.output)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Wrote {args.output}")
    if rows is None:
        print("Portrait placeholder written; pass --photo with a local image to render your portrait.")


if __name__ == "__main__":
    main()
