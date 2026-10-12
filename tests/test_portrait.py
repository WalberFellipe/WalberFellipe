import os
import tempfile
import unittest

import tests._path  # noqa: F401
from PIL import Image, ImageDraw

from profilecard.portrait import RAMP, portrait_ascii, subject_mask

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

    def test_subject_never_blank_above_fade(self):
        # silhouette preserved: dark shirt/hair still render as glyphs before the fade
        rows = portrait_ascii(PHOTO, cols=100)
        self.assertNotEqual(rows[int(len(rows) * 0.6)].ljust(100)[50], " ")

    def test_bottom_fades_out(self):
        rows = portrait_ascii(PHOTO)
        glyphs = lambda r: sum(ch != " " for ch in r)  # noqa: E731
        start = rows[int(len(rows) * 0.75) - 1]
        self.assertLess(glyphs(rows[-1]), 0.35 * glyphs(start))

    def test_invert_makes_dark_regions_dense(self):
        # light theme draws ink on paper: dark pixels must get the denser glyphs
        img = Image.new("RGB", (60, 60), (225, 225, 220))
        ImageDraw.Draw(img).rectangle([10, 10, 29, 49], fill=(20, 20, 20))     # dark half
        ImageDraw.Draw(img).rectangle([30, 10, 49, 49], fill=(170, 120, 100))  # skin-ish half
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "two-tone.png")
            img.save(path)
            normal = portrait_ascii(path, cols=30, crop=(0, 0, 1, 1), fade=0)
            inverted = portrait_ascii(path, cols=30, crop=(0, 0, 1, 1), fade=0, invert=True)
        mid = len(normal) // 2
        dark_col, skin_col = 9, 19      # 60px -> 30 cols: dark ~ cols 5-14, skin ~ 15-24
        self.assertLess(RAMP.index(normal[mid][dark_col]), RAMP.index(normal[mid][skin_col]))
        self.assertGreater(RAMP.index(inverted[mid][dark_col]), RAMP.index(inverted[mid][skin_col]))

    def test_deterministic(self):
        # daily CI rebuilds must not churn the portrait
        self.assertEqual(portrait_ascii(PHOTO), portrait_ascii(PHOTO))


if __name__ == "__main__":
    unittest.main()
