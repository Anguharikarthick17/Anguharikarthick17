#!/usr/bin/env python3
"""Fetch a public GitHub contribution calendar via the official GraphQL API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "profile.json"
OUTPUT = ROOT / "data" / "contributions.json"
API_URL = "https://api.github.com/graphql"
VALID_CONTRIBUTION_LEVELS = {
    "NONE",
    "FIRST_QUARTILE",
    "SECOND_QUARTILE",
    "THIRD_QUARTILE",
    "FOURTH_QUARTILE",
}
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount contributionLevel }
        }
      }
    }
  }
}
"""


class FetchError(Exception):
    """An API or configuration error that should be shown to the caller."""


def fetch_calendar(username: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": username}}).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "genzlog-profile-contributions",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            if error.code in {429, 500, 502, 503, 504} and attempt < 2:
                retry_after = error.headers.get("Retry-After")
                delay = min(int(retry_after), 30) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(delay)
                continue
            if error.code == 403:
                reset = error.headers.get("X-RateLimit-Reset")
                suffix = f" Rate-limit reset timestamp: {reset}." if reset else ""
                raise FetchError(f"GitHub rejected the request (HTTP 403). Check token access or rate limits.{suffix} {detail}")
            if error.code == 401:
                raise FetchError("GitHub authentication failed (HTTP 401). Check PROFILE_READ_TOKEN.")
            raise FetchError(f"GitHub GraphQL request failed (HTTP {error.code}): {detail}")
        except urllib.error.URLError as error:
            if attempt < 2:
                time.sleep(2**attempt)
                continue
            raise FetchError(f"Could not reach the GitHub API: {error.reason}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise FetchError(f"GitHub returned invalid JSON: {error}") from error
    else:
        raise FetchError("GitHub request failed after retries.")

    if not isinstance(payload, dict):
        raise FetchError("GitHub returned a response with an unexpected JSON shape.")
    errors = payload.get("errors")
    if errors:
        if not isinstance(errors, list) or not all(
            isinstance(item, dict) and isinstance(item.get("message"), str)
            for item in errors
        ):
            raise FetchError("GitHub returned malformed GraphQL errors.")
        messages = "; ".join(item.get("message", "Unknown GraphQL error") for item in errors)
        if any("rate limit" in message.lower() for message in messages.split("; ")):
            raise FetchError(f"GitHub API rate limit reached: {messages}. Retry after the limit resets.")
        raise FetchError(f"GitHub GraphQL error: {messages}")
    try:
        calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        raw_weeks = calendar["weeks"]
        total = calendar["totalContributions"]
    except (KeyError, TypeError) as error:
        raise FetchError(
            f"GitHub response did not include a contribution calendar for {username!r}. "
            "Confirm the username is public and the API response format has not changed."
        ) from error

    if type(total) is not int or total < 0 or not isinstance(raw_weeks, list):
        raise FetchError("GitHub returned malformed contribution calendar data.")
    weeks = []
    for raw_week in raw_weeks:
        days = raw_week.get("contributionDays") if isinstance(raw_week, dict) else None
        if not isinstance(days, list):
            raise FetchError("GitHub returned a week without contributionDays.")
        week = []
        for day in days:
            if not isinstance(day, dict):
                raise FetchError("GitHub returned a malformed contribution day.")
            day_date = day.get("date")
            if not isinstance(day_date, str):
                raise FetchError("GitHub returned a contribution day with a non-string date.")
            try:
                parsed_date = date.fromisoformat(day_date)
            except ValueError as error:
                raise FetchError("GitHub returned a contribution day with an invalid ISO date.") from error
            if parsed_date.isoformat() != day_date:
                raise FetchError("GitHub returned a contribution day with a non-canonical ISO date.")

            count = day.get("contributionCount")
            if type(count) is not int or count < 0:
                raise FetchError("GitHub returned a contribution day with an invalid contribution count.")

            level = day.get("contributionLevel")
            if not isinstance(level, str) or level not in VALID_CONTRIBUTION_LEVELS:
                raise FetchError(
                    "GitHub returned a contribution day with an unknown contribution level."
                )
            week.append(
                {
                    "date": day_date,
                    "count": count,
                    "level": level,
                }
            )
        weeks.append(week)
    days = [day for week in weeks for day in week]
    if sum(day["count"] for day in days) != total:
        raise FetchError("GitHub contribution total does not match the daily contribution counts.")
    dates = [date.fromisoformat(day["date"]) for day in days]
    if any(current.toordinal() != previous.toordinal() + 1 for previous, current in zip(dates, dates[1:])):
        raise FetchError("GitHub contribution dates are not consecutive and unique.")
    return {
        "available": True,
        "source": "GitHub GraphQL API",
        "username": username,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_contributions": total,
        "weeks": weeks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=PROFILE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--token-env", default="PROFILE_READ_TOKEN", help="Environment variable holding the API token")
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Configuration error: cannot read {args.profile}: {error}", file=sys.stderr)
        return 1
    if not isinstance(profile, dict):
        print("Configuration error: profile.json must contain a JSON object.", file=sys.stderr)
        return 1
    graph = profile.get("contribution_graph", {})
    if not isinstance(graph, dict):
        print("Configuration error: contribution_graph must be a JSON object.", file=sys.stderr)
        return 1
    enabled = graph.get("enabled", True)
    if not isinstance(enabled, bool):
        print("Configuration error: contribution_graph.enabled must be a boolean.", file=sys.stderr)
        return 1
    if not enabled:
        print("Contribution fetching is disabled by contribution_graph.enabled.", file=sys.stderr)
        return 1
    source = graph.get("data_source", "github")
    if source != "github":
        print(f"Configuration error: unsupported contribution_graph.data_source: {source!r}.", file=sys.stderr)
        return 1
    configured_username = graph.get("username", profile.get("github_username"))
    root_username = profile.get("github_username")
    if root_username is not None and not isinstance(root_username, str):
        print("Configuration error: github_username must be a string.", file=sys.stderr)
        return 1
    if configured_username is not None and not isinstance(configured_username, str):
        print("Configuration error: contribution_graph.username must be a string.", file=sys.stderr)
        return 1
    if root_username and configured_username and root_username.casefold() != configured_username.casefold():
        print(
            "Configuration error: github_username and contribution_graph.username must match.",
            file=sys.stderr,
        )
        return 1
    username = configured_username
    if not isinstance(username, str) or not username or username == "YOUR_GITHUB_USERNAME":
        print("Configuration error: set github_username in data/profile.json first.", file=sys.stderr)
        return 1
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username):
        print("Configuration error: github_username is not a valid GitHub login.", file=sys.stderr)
        return 1
    token = os.environ.get(args.token_env)
    if not token:
        print(
            f"Authentication required: set {args.token_env} to a token with public profile read access. "
            "No contribution data was changed.",
            file=sys.stderr,
        )
        return 1
    try:
        result = fetch_calendar(username, token)
    except FetchError as error:
        print(f"Contribution fetch failed: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent, delete=False
    ) as output_file:
        temporary_path = Path(output_file.name)
        output_file.write(json.dumps(result, indent=2) + "\n")
    try:
        os.replace(temporary_path, args.output)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Fetched {len(result['weeks'])} contribution weeks for {username} into {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
