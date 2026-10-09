#!/usr/bin/env python3
"""Build the profile's terminal information card from data/profile.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "profile.json"
OUTPUT = ROOT / "assets" / "info-card.svg"
LINE_LIMIT = 84
COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}\Z")


def wrap(text: str, limit: int = LINE_LIMIT) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        while len(word) > limit:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:limit])
            word = word[limit:]
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def valid_link(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme in {"https", "http"}
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
    )


def load_profile(path: Path) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError("profile must be a JSON object")
    required = (
        "github_username", "display_name", "short_name", "role", "bio", "focus",
        "currently_building", "career_interests", "languages", "tools", "location",
        "brand", "projects", "social_links",
    )
    missing = [key for key in required if key not in profile]
    if missing:
        raise ValueError(f"profile is missing required fields: {', '.join(missing)}")
    for key in ("github_username", "display_name", "short_name", "role", "bio", "location"):
        if not isinstance(profile[key], str):
            raise ValueError(f"profile field {key!r} must be a string")
    for key in ("focus", "currently_building", "career_interests", "languages", "tools"):
        if not isinstance(profile[key], list) or not all(isinstance(item, str) for item in profile[key]):
            raise ValueError(f"profile field {key!r} must be a list of strings")

    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", profile["github_username"]):
        raise ValueError("profile field 'github_username' is not a valid GitHub username")
    brand = profile["brand"]
    if not isinstance(brand, dict):
        raise ValueError("profile field 'brand' must be an object")
    for key in ("name", "concept"):
        if not isinstance(brand.get(key), str):
            raise ValueError(f"profile field 'brand.{key}' must be a string")
    if not isinstance(brand.get("interests"), list) or not all(
        isinstance(item, str) for item in brand["interests"]
    ):
        raise ValueError("profile field 'brand.interests' must be a list of strings")

    if not isinstance(profile["projects"], list):
        raise ValueError("profile field 'projects' must be a list of objects")
    for index, project in enumerate(profile["projects"]):
        if not isinstance(project, dict) or not all(
            isinstance(project.get(key), str) for key in ("name", "description", "github_url")
        ):
            raise ValueError(f"profile project at index {index} must have string name, description, and github_url")
        if not valid_link(project["github_url"]):
            raise ValueError(f"profile project {project['name']!r} has an invalid GitHub URL")
        parsed = urlparse(project["github_url"])
        parts = parsed.path.strip("/").split("/")
        if (
            parsed.hostname.lower() != "github.com"
            or len(parts) != 2
            or parts[0].casefold() != profile["github_username"].casefold()
            or parts[1].casefold() != project["name"].casefold()
        ):
            raise ValueError(
                f"profile project {project['name']!r} URL must point to "
                f"github.com/{profile['github_username']}/{project['name']}"
            )

    if not isinstance(profile["social_links"], dict) or not all(
        isinstance(label, str) and isinstance(url, str)
        for label, url in profile["social_links"].items()
    ):
        raise ValueError("profile field 'social_links' must map labels to URL strings")
    for label, url in profile["social_links"].items():
        if url and not valid_link(url):
            raise ValueError(f"social link {label!r} must be an http(s) URL")
    for key in ("portfolio_url", "leetcode_url", "resume_url"):
        value = profile.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"profile field {key!r} must be a string")
        if value and not valid_link(value):
            raise ValueError(f"profile field {key!r} must be an http(s) URL")
    email = profile.get("email", "")
    if not isinstance(email, str):
        raise ValueError("profile field 'email' must be a string")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("profile field 'email' must be a valid email address")

    theme = profile.get("theme", {})
    if not isinstance(theme, dict):
        raise ValueError("profile field 'theme' must be an object")
    for key in ("background", "accent", "text"):
        value = theme.get(key)
        if value is not None and (not isinstance(value, str) or not COLOR_PATTERN.fullmatch(value)):
            raise ValueError(f"profile field 'theme.{key}' must be a six-digit hex color")
    return profile


def card_lines(profile: dict) -> list[tuple[str, str, str | None]]:
    lines: list[tuple[str, str, str | None]] = [
        ("label", "$ whoami", None),
        ("value", f'{profile["short_name"]} / {profile["display_name"]}', None),
        ("label", "$ role", None),
        ("value", profile["role"], None),
        ("label", "$ bio", None),
        ("value", profile["bio"], None),
    ]
    for key, command in (
        ("focus", "$ focus"),
        ("currently_building", "$ currently-building"),
        ("career_interests", "$ career-interests"),
        ("languages", "$ languages"),
        ("tools", "$ tools"),
    ):
        lines.append(("label", command, None))
        if profile[key]:
            lines.append(("value", " · ".join(profile[key]), None))

    lines.extend([("label", "$ location", None), ("value", profile["location"], None)])
    brand = profile["brand"]
    lines.extend([
        ("label", f'$ brand / {brand["name"]}', None),
        ("value", brand["concept"], None),
        ("label", "$ brand-interests", None),
    ])
    if brand["interests"]:
        lines.append(("value", " · ".join(brand["interests"]), None))
    lines.append(("projects", "$ projects", None))

    github_url = f'https://github.com/{profile["github_username"]}'
    if "github" not in {label.casefold() for label in profile["social_links"]}:
        lines.extend([("label", "$ github", None), ("link", github_url, github_url)])
    for label, url in profile["social_links"].items():
        if url:
            lines.append(("link", label, url))
    optional_links = (
        ("portfolio", profile.get("portfolio_url", "")),
        ("leetcode", profile.get("leetcode_url", "")),
        ("resume", profile.get("resume_url", "")),
    )
    for label, url in optional_links:
        if url:
            lines.append(("link", label, url))
    email = profile.get("email", "")
    if email:
        lines.append(("link", email, f"mailto:{email}"))
    return lines


def render(profile: dict) -> str:
    width = 920
    row_height = 18
    y = 76
    theme = profile.get("theme", {})
    background = theme.get("background", "#0D1117")
    accent = theme.get("accent", "#69F0A0")
    text_color = theme.get("text", "#C9D1D9")
    svg_lines = []
    for kind, text, href in card_lines(profile):
        if kind == "label":
            svg_lines.append(f'<text class="label" x="30" y="{y}">{escape(text)}</text>')
            y += row_height
        elif kind == "projects":
            svg_lines.append(f'<text class="label" x="30" y="{y}">{escape(text)}</text>')
            y += row_height
            project_rows = [
                (
                    project,
                    wrap(project["description"], 55),
                )
                for project in profile["projects"]
            ]
            for index in range(0, len(project_rows), 2):
                row_height_for_projects = 0
                for column, (project, description_lines) in enumerate(project_rows[index:index + 2]):
                    x = 30 + column * 432
                    svg_lines.append(
                        f'<a class="link" href={quoteattr(project["github_url"])}>'
                        f'<text x="{x}" y="{y}">{escape(project["name"])}</text></a>'
                    )
                    for line_index, line in enumerate(description_lines, start=1):
                        svg_lines.append(
                            f'<text class="value" x="{x + 12}" y="{y + line_index * 16}">'
                            f'{escape(line)}</text>'
                        )
                    row_height_for_projects = max(
                        row_height_for_projects,
                        (len(description_lines) + 1) * 16 + 3,
                    )
                y += row_height_for_projects
        elif kind == "link" and href:
            for line in wrap(text):
                svg_lines.append(
                    f'<a class="link" href={quoteattr(href)}>'
                    f'<text x="48" y="{y}">{escape(line)}</text></a>'
                )
                y += row_height
        else:
            for line in wrap(text):
                svg_lines.append(f'<text class="value" x="48" y="{y}">{escape(line)}</text>')
                y += row_height
    height = max(240, y + 24)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(profile["display_name"])} | terminal profile</title>
  <desc id="desc">Terminal-style profile for {escape(profile["display_name"])} with configured focus areas, interests, languages, tools, projects, brand, and social links.</desc>
  <style>
    .bg {{ fill: {background}; }} .border {{ fill: none; stroke: #234634; }}
    .bar {{ fill: #151d25; }} .dot-red {{ fill: #ff6b6b; }} .dot-yellow {{ fill: #ffd166; }}
    .dot-green {{ fill: #4ade80; }} .muted {{ fill: #8ba596; font: 12px ui-monospace, Menlo, monospace; }}
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .label {{ fill: {accent}; }} .value {{ fill: {text_color}; }}
    .link {{ fill: {accent}; font: 12px ui-monospace, Menlo, monospace; }}
  </style>
  <rect class="bg" width="100%" height="100%" rx="12"/>
  <rect class="border" x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="12"/>
  <path class="bar" d="M12 1h{width - 24}a11 11 0 0 1 11 11v32H1V12A11 11 0 0 1 12 1Z"/>
  <circle class="dot-red" cx="21" cy="17" r="4"/><circle class="dot-yellow" cx="36" cy="17" r="4"/>
  <circle class="dot-green" cx="51" cy="17" r="4"/>
  <text class="muted" x="70" y="21">{escape(profile["brand"]["name"])} / profile.json</text>
  {''.join(svg_lines)}
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=PROFILE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        svg = render(load_profile(args.profile))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
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


if __name__ == "__main__":
    main()
