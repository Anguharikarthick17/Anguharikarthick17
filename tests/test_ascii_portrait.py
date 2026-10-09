import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from xml.etree import ElementTree
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "make_ascii_svg_under_test",
    ROOT / "scripts" / "make_ascii_svg.py",
)
portrait = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = portrait
SPEC.loader.exec_module(portrait)


class GrayscaleMappingTests(unittest.TestCase):
    def test_dark_pixels_use_dense_characters_and_highlights_use_space(self):
        self.assertEqual(portrait.grayscale_to_ascii(0), "@")
        self.assertEqual(portrait.grayscale_to_ascii(255), " ")
        self.assertEqual(portrait.grayscale_to_ascii(142), "=")
        self.assertEqual(set(portrait.RAMP), set(" .:-=+*#%@"))

    def test_rejects_grayscale_values_outside_byte_range(self):
        for value in (-1, 256):
            with self.subTest(value=value), self.assertRaises(ValueError):
                portrait.grayscale_to_ascii(value)


class PortraitGenerationTests(unittest.TestCase):
    def test_resizes_to_requested_columns_with_terminal_character_aspect(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "portrait.png"
            Image.new("RGB", (80, 100), (128, 128, 128)).save(image_path)

            rows = portrait.image_to_ascii(image_path, columns=40, brightness=1.0, contrast=1.0)

        self.assertEqual(len(rows), round(40 * 100 / 80 * portrait.CHAR_ASPECT_RATIO))
        self.assertTrue(all(len(row) == 40 for row in rows))

    def test_subject_crop_removes_light_backdrop_and_keeps_foreground_detail(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "portrait.png"
            image = Image.new("RGB", (120, 100), "white")
            for y in range(15, 86):
                for x in range(40, 81):
                    image.putpixel((x, y), (30 + (x + y) % 150,) * 3)
            image.save(image_path)

            rows = portrait.image_to_ascii(
                image_path,
                columns=40,
                brightness=1.0,
                contrast=1.0,
            )

        self.assertGreater(len(rows), 25)
        self.assertTrue(all(len(row) == 40 for row in rows))
        self.assertGreater(len({character for row in rows for character in row}), 4)
        self.assertEqual(
            portrait.subject_bounds(Image.new("L", (10, 10), 255), 232),
            (0, 0, 10, 10),
        )

    def test_missing_photo_writes_a_labeled_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "portrait.svg"
            with (
                patch.object(sys, "argv", ["make_ascii_svg.py", "--output", str(output)]),
                redirect_stdout(io.StringIO()),
            ):
                portrait.main()

            root = ElementTree.parse(output).getroot()
            svg = output.read_text(encoding="utf-8")

        self.assertIn("PORTRAIT NOT CONFIGURED", "".join(root.itertext()))
        self.assertNotIn("<image", svg)

    def test_svg_escapes_text_and_keeps_terminal_portrait_design(self):
        svg = portrait.render_svg(["<&\"@"], columns=4, label="")
        root = ElementTree.fromstring(svg)
        namespace = {"svg": "http://www.w3.org/2000/svg"}

        self.assertEqual(root.findtext("svg:title", namespaces=namespace), "AHK terminal portrait")
        self.assertIn("&lt;&amp;\"@", svg)
        self.assertIn('<desc id="desc">A monochrome ASCII rendering of a user-provided portrait, revealed line by line.</desc>', svg)
        self.assertIn('fill: #69F0A0', svg)
        self.assertIn("GENZLOG / portrait", svg)
        self.assertIn("prefers-reduced-motion: reduce", svg)


if __name__ == "__main__":
    unittest.main()
