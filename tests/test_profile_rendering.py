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
SVG_NAMESPACE = {"svg": "http://www.w3.org/2000/svg"}


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


info_card = load_script("make_info_card_under_test", ROOT / "scripts" / "make_info_card.py")
heatmap_renderer = load_script(
    "render_heatmap_svg_under_test_for_profile",
    ROOT / "scripts" / "render_heatmap_svg.py",
)


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

    def test_identity_banner_uses_configured_identity_and_accessible_layout(self):
        root = ElementTree.fromstring(info_card.render(self.profile))
        title = root.findtext("svg:title", namespaces=SVG_NAMESPACE)
        description = root.findtext("svg:desc", namespaces=SVG_NAMESPACE)
        visible_text = "".join(root.itertext())

        self.assertEqual(title, "AHK // DIGITAL OPERATING SYSTEM")
        self.assertIn(self.profile["display_name"], visible_text)
        self.assertIn(self.profile["role"], visible_text)
        self.assertIn(self.profile["brand"]["name"], visible_text)
        self.assertIn(self.profile["brand"]["concept"].upper(), visible_text)
        self.assertTrue(description)
        self.assertEqual(root.attrib["role"], "img")
        self.assertEqual(root.attrib["aria-labelledby"], "title desc")
        self.assertEqual(root.attrib["viewBox"], "0 0 1000 440")

    def test_identity_banner_escapes_profile_text(self):
        profile = copy.deepcopy(self.profile)
        profile["display_name"] = "Angu <tester> & Hari"
        profile["role"] = "Developer & AI explorer"
        profile["brand"]["concept"] = "Log <learn> & repeat"

        root = ElementTree.fromstring(info_card.render(profile))
        visible_text = "".join(root.itertext())

        self.assertIn(profile["display_name"], visible_text)
        self.assertIn(profile["role"], visible_text)
        self.assertIn(profile["brand"]["concept"].upper(), visible_text)

    def test_readme_content_and_project_links_match_configuration(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        project_section = readme.split("## 02 / PROJECT INDEX", 1)[1].split(
            "## 03 / CONTRIBUTION SIGNAL", 1
        )[0]
        markdown_projects = re.findall(
            r"^\| \*\*\[([^\]]+)\]\((https://github\.com/[^)]+)\)\*\* — (.+) \|$",
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
        self.assertIn("All 19 configured projects are retained.", readme)
        self.assertIn("access and visibility have not been independently verified", readme)

        for field in ("bio", "focus", "career_interests", "currently_building"):
            for configured_value in (
                [self.profile[field]] if isinstance(self.profile[field], str) else self.profile[field]
            ):
                self.assertIn(configured_value, readme)
        for configured_value in self.profile["brand"]["interests"]:
            self.assertIn(configured_value, readme)
        self.assertIn("Second-year undergraduate", readme)

        for url in self.profile["social_links"].values():
            self.assertIn(f"]({url})", readme)
        for stack_item in (*self.profile["languages"], *self.profile["tools"]):
            self.assertIn(f"`{stack_item}`", readme)

    def test_readme_uses_relative_accessible_generated_images(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        markdown_images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", readme)
        html_images = []
        for tag in re.findall(r"<img\b[^>]*>", readme):
            source = re.search(r'\bsrc="([^"]+)"', tag)
            alt = re.search(r'\balt="([^"]*)"', tag)
            self.assertIsNotNone(source)
            self.assertIsNotNone(alt)
            self.assertTrue(alt.group(1).strip())
            html_images.append((alt.group(1), source.group(1)))

        images = [*markdown_images, *html_images]
        self.assertEqual(len(images), 3)
        for alt_text, relative_path in images:
            self.assertTrue(alt_text.strip())
            self.assertFalse(relative_path.startswith(("http://", "https://", "/")))
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_generated_svgs_are_accessible_static_and_within_layout_limits(self):
        names = ("ascii-portrait.svg", "info-card.svg", "contrib-heatmap.svg")
        for name in names:
            with self.subTest(name=name):
                path = ROOT / "assets" / name
                root = ElementTree.parse(path).getroot()
                self.assertEqual(root.attrib.get("role"), "img")
                self.assertEqual(root.attrib.get("aria-labelledby"), "title desc")
                self.assertTrue(root.findtext("svg:title", namespaces=SVG_NAMESPACE))
                self.assertTrue(root.findtext("svg:desc", namespaces=SVG_NAMESPACE))
                width, height = (float(value) for value in root.attrib["viewBox"].split()[2:])
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertLessEqual(width, 1600)
                self.assertLessEqual(height, 1000)
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"<image\b")
                self.assertNotIn("base64,", text)
                self.assertNotIn("@keyframes", text)
                self.assertNotIn("animation:", text)

        portrait_root = ElementTree.parse(ROOT / "assets" / "ascii-portrait.svg").getroot()
        self.assertLessEqual(int(portrait_root.attrib["width"]), 400)
        self.assertLessEqual(int(portrait_root.attrib["height"]), 450)
        portrait_rows = portrait_root.findall(".//svg:text[@class='ascii-row']", SVG_NAMESPACE)
        self.assertLessEqual(len(portrait_rows), 45)
        self.assertTrue((ROOT / "photos" / "portrait.jpg").is_file())

    def test_heatmap_uses_preserved_real_contribution_calendar(self):
        data = json.loads((ROOT / "data" / "contributions.json").read_text(encoding="utf-8"))
        days = [day for week in data["weeks"] for day in week]

        self.assertTrue(data["available"])
        self.assertEqual(data["source"], "GitHub GraphQL API")
        self.assertEqual(data["username"], self.profile["github_username"])
        self.assertEqual(sum(day["count"] for day in days), data["total_contributions"])
        self.assertEqual(
            (ROOT / "assets" / "contrib-heatmap.svg").read_text(encoding="utf-8"),
            heatmap_renderer.render(data),
        )
        self.assertIn(str(data["total_contributions"]), "".join(
            ElementTree.parse(ROOT / "assets" / "contrib-heatmap.svg").getroot().itertext()
        ))

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
