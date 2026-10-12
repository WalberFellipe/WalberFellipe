import datetime
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import tests._path  # noqa: F401

import build_profile

TODAY = datetime.date(2026, 10, 11)


class BuildTest(unittest.TestCase):
    def test_offline_build_writes_both_themes(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("profilecard.data._get_json", side_effect=OSError), \
                mock.patch.dict(os.environ, {}, clear=True):
            paths = build_profile.main(out_dir=d, today=TODAY)
            self.assertEqual(sorted(os.path.basename(p) for p in paths), ["dark.svg", "light.svg"])
            for p in paths:
                ET.parse(p)

    def test_written_files_are_utf8_and_keep_accents(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("profilecard.data._get_json", side_effect=OSError):
            p = build_profile.main(out_dir=d, today=TODAY)[0]
            with open(p, "rb") as f:
                raw = f.read()
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn("Araxá".encode("utf-8"), raw)


if __name__ == "__main__":
    unittest.main()
