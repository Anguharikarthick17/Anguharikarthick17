#!/usr/bin/env python3
"""Build the AHK identity banner from data/profile.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "profile.json"
OUTPUT = ROOT / "assets" / "info-card.svg"
COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}\Z")


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


def render(profile: dict) -> str:
    width, height = 1000, 440
    name = escape(profile["display_name"])
    short_name = escape(profile["short_name"])
    role = escape(profile["role"])
    brand_name = escape(profile["brand"]["name"])
    brand_concept = escape(profile["brand"]["concept"].upper())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{short_name} // DIGITAL OPERATING SYSTEM</title>
  <desc id="desc">{name}, {role}. {brand_name} — {brand_concept}.</desc>
  <style>
    .bg {{ fill: #080B0A; }}
    .grid {{ stroke: #18211D; stroke-width: 1; }}
    .frame {{ fill: none; stroke: #34433C; stroke-width: 1; }}
    .accent {{ fill: #67E6A4; }}
    .muted {{ fill: #84918A; }}
    .primary {{ fill: #E5EBE7; }}
    .eyebrow {{ font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 2px; }}
    .hero {{ font: 700 144px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: -10px; }}
    .name {{ font: 500 30px ui-sans-serif, system-ui, sans-serif; letter-spacing: .3px; }}
    .role {{ font: 15px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .5px; }}
    .micro {{ font: 10px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 1px; }}
    .rule {{ stroke: #34433C; stroke-width: 1; }}
    .ring {{ fill: none; stroke: #26372F; stroke-width: 1; }}
  </style>
  <rect class="bg" width="{width}" height="{height}"/>
  <path class="grid" d="M0 110H1000M0 330H1000M520 0V440M940 0V440" opacity=".55"/>
  <path class="frame" d="M18 1H982a17 17 0 0 1 17 17V422a17 17 0 0 1-17 17H18A17 17 0 0 1 1 422V18A17 17 0 0 1 18 1Z"/>
  <path class="accent" d="M40 48h34v2H40zM40 48v34h2V48z"/>
  <text class="eyebrow accent" x="56" y="70">{brand_name} <tspan class="muted">/</tspan> {brand_concept}</text>
  <text class="micro muted" x="944" y="70" text-anchor="end">AHK <tspan class="accent">//</tspan> DIGITAL OPERATING SYSTEM</text>
  <text class="hero accent" x="56" y="232">{short_name}</text>
  <path class="rule" d="M60 258H535"/>
  <text class="name primary" x="61" y="304">{name}</text>
  <text class="role muted" x="62" y="338">{role}</text>
  <text class="micro muted" x="62" y="395">IDENTITY <tspan class="accent">/</tspan> 001</text>
  <text class="micro muted" x="490" y="395" text-anchor="end">GENZLOG <tspan class="accent">//</tspan> PERSONAL SYSTEMS</text>
  <g transform="translate(733 218)">
    <circle class="ring" r="142"/><circle class="ring" r="116"/><circle class="ring" r="72"/>
    <path class="rule" d="M-170 0H170M0-170V170M-120-120L120 120M120-120L-120 120" opacity=".58"/>
    <path class="accent" d="M0-151v22M0 129v22M-151 0h22M129 0h22" stroke="#67E6A4" stroke-width="2"/>
    <circle class="accent" r="4"/><circle class="ring" r="16"/>
    <text class="micro muted" x="0" y="-184" text-anchor="middle">AHK / CORE ID</text>
    <text class="micro muted" x="0" y="195" text-anchor="middle">GENZLOG · EST. BY CURIOSITY</text>
    <text class="micro accent" x="147" y="-118">01</text>
    <text class="micro accent" x="-168" y="135">SYS</text>
  </g>
  <path class="accent" d="M958 359h18v2h-18zM974 343h2v18h-2z"/>
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
