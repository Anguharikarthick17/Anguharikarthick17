import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fetcher = load_script("fetch_contributions_under_test", ROOT / "scripts" / "fetch_contributions.py")
renderer = load_script("render_heatmap_svg_under_test", ROOT / "scripts" / "render_heatmap_svg.py")


class MockResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def api_response(days: list[dict]) -> dict:
    return {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": sum(day["contributionCount"] for day in days),
                        "weeks": [{"contributionDays": days}],
                    }
                }
            }
        }
    }


class ContributionFetchTests(unittest.TestCase):
    def fetch_days(self, days: list[dict]) -> dict:
        with patch.object(
            fetcher.urllib.request,
            "urlopen",
            return_value=MockResponse(api_response(days)),
        ):
            return fetcher.fetch_calendar("example-user", "test-token")

    def test_accepts_github_graphql_contribution_levels(self):
        levels = [
            "NONE",
            "FIRST_QUARTILE",
            "SECOND_QUARTILE",
            "THIRD_QUARTILE",
            "FOURTH_QUARTILE",
        ]
        days = [
            {
                "date": f"2026-01-{index:02d}",
                "contributionCount": index - 1,
                "contributionLevel": level,
            }
            for index, level in enumerate(levels, start=1)
        ]

        result = self.fetch_days(days)

        self.assertEqual([day["level"] for day in result["weeks"][0]], levels)

    def test_rejects_unknown_contribution_level(self):
        day = {"date": "2026-01-01", "contributionCount": 0, "contributionLevel": "FIRST"}
        with self.assertRaisesRegex(fetcher.FetchError, "unknown contribution level"):
            self.fetch_days([day])

    def test_rejects_invalid_dates_and_counts(self):
        invalid_days = [
            {"date": "2026-02-30", "contributionCount": 0, "contributionLevel": "NONE"},
            {"date": "20260101", "contributionCount": 0, "contributionLevel": "NONE"},
            {"date": "2026-01-01", "contributionCount": -1, "contributionLevel": "NONE"},
            {"date": "2026-01-01", "contributionCount": True, "contributionLevel": "NONE"},
        ]
        for day in invalid_days:
            with self.subTest(day=day):
                with self.assertRaises(fetcher.FetchError):
                    self.fetch_days([day])


class ContributionHeatmapTests(unittest.TestCase):
    def test_renders_all_confirmed_github_levels(self):
        levels = [
            "NONE",
            "FIRST_QUARTILE",
            "SECOND_QUARTILE",
            "THIRD_QUARTILE",
            "FOURTH_QUARTILE",
        ]
        days = [
            {
                "date": f"2026-01-{index:02d}",
                "count": index - 1,
                "level": level,
            }
            for index, level in enumerate(levels, start=1)
        ]

        svg = renderer.render(
            {
                "available": True,
                "username": "example-user",
                "weeks": [days],
            }
        )
        ElementTree.fromstring(svg)

        for level in levels:
            self.assertIn(renderer.COLORS[level], svg)
        self.assertIn("level fourth_quartile", svg)

    def test_rejects_invalid_dates_counts_and_levels(self):
        invalid_days = [
            {"date": "2026-02-30", "count": 0, "level": "NONE"},
            {"date": "20260101", "count": 0, "level": "NONE"},
            {"date": "2026-01-01", "count": -1, "level": "NONE"},
            {"date": "2026-01-01", "count": True, "level": "NONE"},
            {"date": "2026-01-01", "count": 0, "level": "FIRST"},
        ]
        for day in invalid_days:
            with self.subTest(day=day):
                with self.assertRaises(ValueError):
                    renderer.flatten_days({"weeks": [[day]]})


if __name__ == "__main__":
    unittest.main()
