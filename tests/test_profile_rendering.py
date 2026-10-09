import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


info_card = load_script("make_info_card_under_test", ROOT / "scripts" / "make_info_card.py")


class ProfileRenderingTests(unittest.TestCase):
    def setUp(self):
        self.profile = info_card.load_profile(ROOT / "data" / "profile.json")

    def test_profile_has_ordered_projects_with_matching_github_urls(self):
        self.assertEqual(len(self.profile["projects"]), 19)
        for project in self.profile["projects"]:
            self.assertEqual(
                project["github_url"],
                f'https://github.com/{self.profile["github_username"]}/{project["name"]}',
            )

    def test_invalid_project_url_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["projects"][0]["github_url"] = "https://github.com/someone-else/EcoRoute"
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must point to"):
                info_card.load_profile(profile_path)

    def test_card_renders_every_project_link_and_hides_empty_optional_links(self):
        profile = copy.deepcopy(self.profile)
        for key in ("portfolio_url", "leetcode_url", "resume_url", "email"):
            profile.pop(key, None)

        svg = info_card.render(profile)
        root = ElementTree.fromstring(svg)
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        links = root.findall(".//svg:a", namespace)
        link_urls = [link.attrib["href"] for link in links]

        self.assertEqual(
            link_urls[:len(profile["projects"])],
            [project["github_url"] for project in profile["projects"]],
        )
        self.assertEqual(len(link_urls), len(profile["projects"]) + len(profile["social_links"]))
        self.assertLess(int(root.attrib["height"]), 1200)
        visible_text = "".join(root.itertext())
        for project in profile["projects"]:
            self.assertIn(project["name"], visible_text)
            self.assertIn(project["description"], visible_text)
        self.assertNotIn('href=""', svg)

    def test_user_text_is_xml_escaped(self):
        profile = copy.deepcopy(self.profile)
        profile["bio"] = 'Builder <tester> & "designer"'
        root = ElementTree.fromstring(info_card.render(profile))
        rendered_text = "".join(root.itertext())
        self.assertIn(profile["bio"], rendered_text)

    def test_readme_projects_social_links_and_asset_paths_match_configuration(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        project_section = readme.split("## `~/projects`", 1)[1].split("## `~/stack`", 1)[0]
        markdown_projects = re.findall(
            r"^- \[([^\]]+)\]\((https://github\.com/[^)]+)\) — (.+)$",
            project_section,
            flags=re.MULTILINE,
        )
        self.assertEqual(
            markdown_projects,
            [
                (project["name"], project["github_url"], project["description"])
                for project in self.profile["projects"]
            ],
        )
        for url in self.profile["social_links"].values():
            self.assertIn(f"]({url})", readme)

        markdown_images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
        html_images = re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', readme)
        self.assertTrue(markdown_images)
        self.assertTrue(html_images)
        for relative_path in [*markdown_images, *html_images]:
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_generated_svg_assets_are_valid_and_portrait_does_not_embed_photo(self):
        for name in ("ascii-portrait.svg", "info-card.svg", "contrib-heatmap.svg"):
            with self.subTest(name=name):
                ElementTree.parse(ROOT / "assets" / name)
        portrait_svg = (ROOT / "assets" / "ascii-portrait.svg").read_text(encoding="utf-8")
        self.assertNotRegex(portrait_svg, r"<image\b")
        self.assertNotIn("base64,", portrait_svg)
        self.assertTrue((ROOT / "photos" / "portrait.jpg").is_file())

    def test_heatmap_uses_the_preserved_real_contribution_calendar(self):
        data = json.loads((ROOT / "data" / "contributions.json").read_text(encoding="utf-8"))
        days = [day for week in data["weeks"] for day in week]

        self.assertTrue(data["available"])
        self.assertEqual(data["source"], "GitHub GraphQL API")
        self.assertEqual(data["username"], self.profile["github_username"])
        self.assertEqual(sum(day["count"] for day in days), data["total_contributions"])
        self.assertEqual(
            (ROOT / "assets" / "contrib-heatmap.svg").read_text(encoding="utf-8"),
            load_script(
                "render_heatmap_svg_under_test_for_profile",
                ROOT / "scripts" / "render_heatmap_svg.py",
            ).render(data),
        )

    def test_local_photo_and_environment_files_are_git_ignored(self):
        for path in ("photos/portrait.jpg", ".env.local", ".venv/bin/python"):
            result = subprocess.run(
                ["git", "check-ignore", "--no-index", "-q", "--", path],
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{path} is not ignored")


if __name__ == "__main__":
    unittest.main()
