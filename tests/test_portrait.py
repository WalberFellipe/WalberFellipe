import os
import unittest

import tests._path  # noqa: F401
from PIL import Image, ImageDraw

from profilecard.portrait import portrait_ascii, subject_mask

PHOTO = os.path.join(tests._path.ROOT, "assets", "portrait.png")


class SubjectMaskTest(unittest.TestCase):
    def test_mask_synthetic_square(self):
        img = Image.new("RGB", (40, 40), (225, 225, 220))
        ImageDraw.Draw(img).rectangle([10, 10, 29, 29], fill=(20, 20, 20))
        m = subject_mask(img)
        self.assertEqual(m.getpixel((0, 0)), 0)
        self.assertEqual(m.getpixel((20, 20)), 255)

    def test_mask_keeps_dark_region_touching_border(self):
        # black shirt touches the bottom edge but must stay subject
        img = Image.new("RGB", (40, 40), (225, 225, 220))
        ImageDraw.Draw(img).rectangle([5, 25, 34, 39], fill=(15, 15, 15))
        self.assertEqual(subject_mask(img).getpixel((20, 39)), 255)

    def test_real_photo_corners_background_face_subject(self):
        m = subject_mask(Image.open(PHOTO).convert("RGB"))
        self.assertEqual(m.getpixel((0, 128)), 0)
        self.assertEqual(m.getpixel((128, 128)), 255)


class PortraitAsciiTest(unittest.TestCase):
    def test_ascii_shape(self):
        rows = portrait_ascii(PHOTO, cols=100)
        self.assertTrue(40 <= len(rows) <= 70, len(rows))
        self.assertTrue(all(len(r) <= 100 for r in rows))
        self.assertEqual(rows[0][:10].strip(), "")

    def test_subject_never_blank(self):
        # silhouette preserved: centre column of the bottom row is a glyph
        rows = portrait_ascii(PHOTO, cols=100)
        self.assertNotEqual(rows[-1].ljust(100)[50], " ")


if __name__ == "__main__":
    unittest.main()
