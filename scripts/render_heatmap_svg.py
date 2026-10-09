#!/usr/bin/env python3
"""Render verified contribution-calendar JSON as an animated SVG heatmap."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "contributions.json"
OUTPUT = ROOT / "assets" / "contrib-heatmap.svg"
COLORS = {
    "NONE": "#14251b",
    "FIRST_QUARTILE": "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE": "#26a641",
    "FOURTH_QUARTILE": "#39d353",
}
LEVEL_LABELS = ["Less", "More"]


def flatten_days(data: dict) -> list[dict]:
    days = []
    for week in data.get("weeks", []):
        if not isinstance(week, list):
            raise ValueError("each contribution week must be a list")
        for day in week:
            if (
                not isinstance(day, dict)
                or not isinstance(day.get("level"), str)
                or day["level"] not in COLORS
                or type(day.get("count")) is not int
                or day["count"] < 0
            ):
                raise ValueError("contribution day has an invalid count or level")
            try:
                parsed_date = date.fromisoformat(day["date"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("contribution day has an invalid ISO date") from error
            if parsed_date.isoformat() != day["date"]:
                raise ValueError("contribution day has a non-canonical ISO date")
            days.append(day)
    return days


def render_unavailable(message: str) -> str:
    safe = escape(message)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 860 150" role="img" aria-labelledby="title desc">
  <title id="title">Contribution heatmap not configured</title>
  <desc id="desc">{safe}</desc>
  <style>
    .bg {{ fill: #07110d; }} .border {{ fill: none; stroke: #234634; }}
    .title {{ fill: #63f59a; font: 600 16px ui-monospace, Menlo, monospace; }}
    .message {{ fill: #b4c8ba; font: 13px ui-monospace, Menlo, monospace; }}
  </style>
  <rect class="bg" width="100%" height="100%" rx="12"/><rect class="border" x=".5" y=".5" width="859" height="149" rx="12"/>
  <text class="title" x="24" y="52">CONTRIBUTION DATA UNAVAILABLE</text>
  <text class="message" x="24" y="82">{safe}</text>
</svg>
'''


def render(data: dict) -> str:
    if not data.get("available"):
        message = data.get("message") or "Configure a GitHub username and token, then run the contribution fetch script."
        return render_unavailable(str(message))
    username = escape(str(data.get("username", "GitHub user")))
    days = flatten_days(data)
    if not days:
        return render_unavailable("The API returned no contribution days. Re-run the fetch after checking the account.")

    first_day = min(date.fromisoformat(day["date"]) for day in days)
    start = date.fromordinal(first_day.toordinal() - (first_day.weekday() + 1) % 7)
    cell, gap = 11, 3
    step = cell + gap
    grid_x, grid_y = 56, 54
    weeks_count = max((date.fromisoformat(day["date"]) - start).days // 7 for day in days) + 1
    width = max(640, grid_x + weeks_count * step + 110)
    height = 178

    rects = []
    for day in days:
        day_date = date.fromisoformat(day["date"])
        offset = (day_date - start).days
        x = grid_x + (offset // 7) * step
        y = grid_y + (offset % 7) * step
        title = f'{day_date.isoformat()}: {day["count"]} contributions (level {day["level"].lower()})'
        rects.append(
            f'<rect class="day" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{COLORS[day["level"]]}" style="animation-delay:{len(rects) * 1.5:g}ms">'
            f'<title>{escape(title)}</title></rect>'
        )

    month_labels = []
    seen_months = set()
    for day in sorted(days, key=lambda entry: entry["date"]):
        current = date.fromisoformat(day["date"])
        month_key = (current.year, current.month)
        if current.day <= 7 and month_key not in seen_months:
            x = grid_x + ((current - start).days // 7) * step
            month_labels.append(f'<text class="muted" x="{x}" y="43">{current.strftime("%b")}</text>')
            seen_months.add(month_key)
    total = data.get("total_contributions")
    total_label = f"{total} contributions in the displayed calendar" if isinstance(total, int) else "Contribution levels shown; counts available on hover"
    legend_x = max(grid_x + 8, width - 143)
    legend = []
    for index, level in enumerate(
        ("NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE")
    ):
        legend.append(f'<rect x="{legend_x + index * 16}" y="151" width="11" height="11" rx="2" fill="{COLORS[level]}"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{username} GitHub contribution heatmap</title>
  <desc id="desc">Contribution intensity by day for {username}. Colors encode contribution levels; hover a square for the exact count and date. {escape(total_label)}.</desc>
  <style>
    .bg {{ fill: #07110d; }} .border {{ fill: none; stroke: #234634; }}
    .heading {{ fill: #63f59a; font: 600 14px ui-monospace, Menlo, monospace; }}
    .muted {{ fill: #91a99a; font: 11px ui-monospace, Menlo, monospace; }}
    .day {{ opacity: 0; animation: reveal .45s ease-out forwards; }}
    @keyframes reveal {{ to {{ opacity: 1; }} }}
    @media (prefers-reduced-motion: reduce) {{ .day {{ animation: none; opacity: 1; }} }}
  </style>
  <rect class="bg" width="100%" height="100%" rx="12"/><rect class="border" x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="12"/>
  <text class="heading" x="24" y="27">{username} / CONTRIBUTIONS</text>
  <text class="muted" x="{width - 258}" y="27">{escape(total_label)}</text>
  {''.join(month_labels)}
  {''.join(rects)}
  <text class="muted" x="24" y="161">Contribution level</text>
  {''.join(legend)}
  <text class="muted" x="{legend_x + 88}" y="161">{LEVEL_LABELS[0]}  →  {LEVEL_LABELS[1]}</text>
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        data = json.loads(args.data.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("contributions JSON must contain an object")
        svg = render(data)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
