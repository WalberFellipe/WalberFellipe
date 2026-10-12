import contextlib
import datetime
import io
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import tests._path  # noqa: F401

import build_profile

TODAY = datetime.date(2026, 10, 11)


@contextlib.contextmanager
def offline(env=None):
    """Every HTTP call fails; the environment holds only `env` (no stray tokens)."""
    with mock.patch("profilecard.data._get_json", side_effect=OSError("offline")), \
            mock.patch.dict(os.environ, env or {}, clear=True), \
            contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        yield


class BuildTest(unittest.TestCase):
    def test_offline_build_writes_both_themes(self):
        with tempfile.TemporaryDirectory() as d, offline():
            paths = build_profile.main(out_dir=d, today=TODAY)
            self.assertEqual(sorted(os.path.basename(p) for p in paths), ["dark.svg", "light.svg"])
            for p in paths:
                ET.parse(p)

    def test_written_files_are_utf8_and_keep_accents(self):
        with tempfile.TemporaryDirectory() as d, offline():
            p = build_profile.main(out_dir=d, today=TODAY)[0]
            with open(p, "rb") as f:
                raw = f.read()
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn("Araxá".encode("utf-8"), raw)

    def test_light_theme_uses_inverted_portrait(self):
        with tempfile.TemporaryDirectory() as d, offline():
            build_profile.main(out_dir=d, today=TODAY)
            art = {}
            for theme in ("dark", "light"):
                with open(os.path.join(d, f"{theme}.svg"), encoding="utf-8") as f:
                    art[theme] = re.search(r'<text class="ascii".*?</text>', f.read(), re.S).group(0)
        self.assertFalse(art["dark"] == art["light"], "light theme should use the inverted portrait")

    def test_dead_token_keeps_previous_card_and_fails(self):
        # a configured token that gets nothing back (expired PAT, outage) must not
        # overwrite the last good card with an all-dash one
        with tempfile.TemporaryDirectory() as d, offline({"GITHUB_TOKEN": "expired"}):
            with self.assertRaises(SystemExit) as stop:
                build_profile.main(out_dir=d, today=TODAY)
            self.assertEqual(os.listdir(d), [])
        self.assertNotEqual(stop.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
