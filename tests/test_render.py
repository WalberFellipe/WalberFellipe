import datetime
import os
import re
import unittest
import xml.etree.ElementTree as ET

import tests._path  # noqa: F401

from profilecard.palettes import DARK, LIGHT
from build_profile import INFO
from profilecard.portrait import ADVANCE, portrait_ascii
from profilecard.render import FS_ASCII, INFO_PANEL, MAP_PANEL, VALUE_COL, Card, build_svg


NOW = datetime.datetime(2026, 10, 11, 12, tzinfo=datetime.timezone.utc)


def full_card():
    start = datetime.date(2025, 9, 1)
    calendar = [(start + datetime.timedelta(i), (i * 7) % 11) for i in range(406)]
    return Card(
        info=list(INFO), user="walber@dev", uptime_days=2444,
        ascii_rows=["x" * 90] * 60,
        streaks={"total": 3487, "current": 4, "longest": 13},
        github={"followers": 10, "following": 12, "repos": 22, "stars": 2, "forks": 0,
                "prs": 344, "issues": 55,
                "langs": [("TypeScript", 50), ("JavaScript", 23), ("PHP", 11), ("CSS", 8), ("SCSS", 4)],
                "top_repos": [("VacinaPetMobile", 1, "TypeScript"), ("Orbit", 0, "TypeScript")],
                "last_push": "2026-10-11T00:00:00Z", "joined": 2019},
        wakatime=None, calendar=calendar, sync_date="2026-10-11", now=NOW)


def empty_card():
    c = full_card()
    c.streaks = c.github = c.wakatime = c.calendar = None
    return c


class RenderTest(unittest.TestCase):
    def test_is_valid_xml_with_viewbox(self):
        svg = build_svg(full_card(), DARK)
        root = ET.fromstring(svg.encode("utf-8"))
        w, h = root.get("viewBox").split()[2:]
        self.assertEqual(w, "1180")
        self.assertGreater(float(h), 800)

    def test_contains_identity_and_title(self):
        svg = build_svg(full_card(), DARK)
        for s in ["walber@dev ~ % ./profile.sh --live", "up 2444d", "Walber Fellipe",
                  "Araxá - MG, Brazil", "walberfellipe18@gmail.com", "walber-fellipe"]:
            self.assertIn(s, svg)

    def test_escapes_markup(self):
        c = full_card()
        c.info.append(("Note", "R&D <AI>"))
        self.assertIn("R&amp;D &lt;AI&gt;", build_svg(c, DARK))

    def test_info_values_fit_panel(self):
        x, y, w, h = INFO_PANEL
        longest = max(VALUE_COL + len(v) for _, v in full_card().info)
        self.assertLessEqual(16 + longest * 13 * 0.60, w)
        self.assertLessEqual(len(full_card().info) * 17 + 60, h)

    def test_real_portrait_fits_map_panel(self):
        x, y, w, h = MAP_PANEL
        rows = portrait_ascii(os.path.join(tests._path.ROOT, "assets", "portrait.png"))
        self.assertLessEqual(len(rows) * FS_ASCII, h - 30)          # clear of the panel label
        self.assertLessEqual(max(map(len, rows)) * FS_ASCII * ADVANCE, w - 20)

    def test_missing_metrics_render_dash(self):
        svg = build_svg(empty_card(), DARK)
        ET.fromstring(svg.encode("utf-8"))
        self.assertNotIn("None", svg)
        self.assertIn("—", svg)

    def test_theme_specific_blend_and_colors(self):
        d, l = build_svg(full_card(), DARK), build_svg(full_card(), LIGHT)
        self.assertIn("#00E5FF", d)
        self.assertIn("#0891B2", l)
        self.assertIn("mix-blend-mode:screen", d)
        self.assertIn("mix-blend-mode:multiply", l)

    def test_heatmap_has_371_cells_or_none(self):
        self.assertEqual(build_svg(full_card(), DARK).count('class="hm"'), 371)
        self.assertEqual(build_svg(empty_card(), DARK).count('class="hm"'), 0)

    def test_wakatime_drives_languages_and_code_time(self):
        c = full_card()
        c.wakatime = {"range": "ALL TIME", "langs": [("TypeScript", "812h05m")],
                      "total": "1,203 hrs 4 mins", "daily_avg": "2 hrs 1 min"}
        svg = build_svg(c, DARK)
        self.assertIn("812h05m", svg)
        self.assertIn("CODE TIME", svg)
        self.assertNotIn("CODE TIME", build_svg(full_card(), DARK))

    def test_gradient_cycles_every_9s(self):
        svg = build_svg(full_card(), DARK)
        self.assertRegex(svg, r'attributeName="stop-color"[^>]*dur="9s"')

    def test_info_lines_type_in_order(self):
        svg = build_svg(full_card(), DARK)
        begins = [float(b) for b in re.findall(r'id="lc\d+".*?begin="([\d.]+)s"', svg, re.S)]
        self.assertEqual(len(begins), len(full_card().info))
        self.assertEqual(begins, sorted(begins))
        self.assertGreaterEqual(begins[0], 2.2)

    def test_glitch_filter_present(self):
        svg = build_svg(full_card(), DARK)
        self.assertIn('id="glitch"', svg)
        self.assertIn('dur="7s"', svg)


if __name__ == "__main__":
    unittest.main()
