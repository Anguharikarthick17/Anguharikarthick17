#!/usr/bin/env python3
"""Render a local portrait as an animated, monochrome ASCII SVG."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "ascii-portrait.svg"
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def image_to_ascii(photo: Path, columns: int, brightness: float, contrast: float) -> list[str]:
    with Image.open(photo) as source:
        image = ImageOps.exif_transpose(source).convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(contrast)
        image = ImageEnhance.Brightness(image).enhance(brightness)

        width, height = image.size
        rows = max(1, round(columns * height / width * 0.58))
        image = image.resize((columns, rows), Image.Resampling.LANCZOS)
        pixels = list(image.getdata())

    ramp_last = len(RAMP) - 1
    return [
        "".join(RAMP[round(pixels[row * columns + col] / 255 * ramp_last)] for col in range(columns))
        for row in range(rows)
    ]


def render_svg(rows: list[str] | None, columns: int, label: str) -> str:
    cell_width, cell_height = 9, 16
    text_x, text_y = 28, 76
    if rows is None:
        rows = ["", "", "", "", "", ""]
    width = max(520, columns * cell_width + 56)
    height = max(210, len(rows) * cell_height + 124)
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
                f'<text x="{text_x}" y="{text_y + index * cell_height}" '
                f'class="ascii-row" style="animation-delay:{index * 38}ms">{escape(row)}</text>'
            )

    title = "AHK terminal portrait"
    description = (
        "Portrait placeholder. Supply a local photo with scripts/make_ascii_svg.py --photo."
        if label
        else "A monochrome ASCII rendering of a user-provided portrait, revealed line by line."
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{title}</title>
  <desc id="desc">{description}</desc>
  <style>
    .background {{ fill: #07110d; }}
    .frame {{ fill: none; stroke: #234634; stroke-width: 1; }}
    .bar {{ fill: #0d1c14; }}
    .dot-red {{ fill: #ff6b6b; }} .dot-yellow {{ fill: #ffd166; }} .dot-green {{ fill: #4ade80; }}
    .brand {{ fill: #8ba596; font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .ascii-row {{ fill: #63f59a; font: 13px ui-monospace, SFMono-Regular, Menlo, monospace;
      white-space: pre; opacity: 0; animation: reveal .32s ease-out forwards; }}
    .placeholder {{ fill: #63f59a; font: 600 16px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .hint {{ fill: #91a99a; font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    @keyframes reveal {{ to {{ opacity: 1; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .ascii-row {{ animation: none; opacity: 1; }}
    }}
  </style>
  <rect class="background" width="100%" height="100%" rx="12"/>
  <rect class="frame" x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="12"/>
  <path class="bar" d="M12 1h{width - 24}a11 11 0 0 1 11 11v31H1V12A11 11 0 0 1 12 1Z"/>
  <circle class="dot-red" cx="21" cy="17" r="4"/><circle class="dot-yellow" cx="36" cy="17" r="4"/>
  <circle class="dot-green" cx="51" cy="17" r="4"/>
  <text class="brand" x="70" y="21">GENZLOG / portrait</text>
  {''.join(content)}
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path, help="Path to a local portrait photo (never copied by this script)")
    parser.add_argument("--output", type=Path, default=OUTPUT, help=f"Output SVG (default: {OUTPUT})")
    parser.add_argument("--columns", type=int, default=56, help="ASCII character columns (default: 56)")
    parser.add_argument("--brightness", type=float, default=1.08, help="Brightness multiplier (default: 1.08)")
    parser.add_argument("--contrast", type=float, default=1.25, help="Contrast multiplier (default: 1.25)")
    args = parser.parse_args()
    if args.columns < 8 or args.columns > 160:
        parser.error("--columns must be between 8 and 160")
    if args.brightness <= 0 or args.contrast <= 0 or not math.isfinite(args.brightness + args.contrast):
        parser.error("--brightness and --contrast must be finite positive numbers")

    rows = None
    placeholder = "PORTRAIT NOT CONFIGURED"
    if args.photo is not None:
        if not args.photo.is_file():
            parser.error(f"photo file does not exist: {args.photo}")
        try:
            rows = image_to_ascii(args.photo, args.columns, args.brightness, args.contrast)
        except (OSError, ValueError) as error:
            parser.error(f"cannot read portrait image: {error}")
        placeholder = ""

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(rows, args.columns, placeholder), encoding="utf-8")
    print(f"Wrote {args.output}")
    if rows is None:
        print("Portrait placeholder written; pass --photo with a local image to render your portrait.")


if __name__ == "__main__":
    main()
