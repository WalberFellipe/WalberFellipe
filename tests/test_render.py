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

    def test_activity_header_shows_last_year_total(self):
        # like GitHub: contributions of the last 365 days, today included
        c = full_card()
        today = c.now.date()
        c.calendar = [(today - datetime.timedelta(i), 3) for i in reversed(range(400))]
        svg = build_svg(c, DARK)
        self.assertRegex(svg, r">1,095<.*?contributions in the last year")
        self.assertNotIn("CONTRIBUTION MATRIX · 1 YEAR", svg)

    def test_activity_header_without_calendar_has_no_total(self):
        svg = build_svg(empty_card(), DARK)
        self.assertIn("CONTRIBUTION MATRIX · 1 YEAR", svg)
        self.assertNotIn("contributions in the last year", svg)

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
        # intros start with the document; the visible start is keyTimes[1] * dur
        svg = build_svg(full_card(), DARK)
        found = re.findall(r'id="lc\d+".*?keyTimes="0;([\d.]+);1" dur="([\d.]+)s"', svg, re.S)
        begins = [round(float(k) * float(d), 2) for k, d in found]
        self.assertEqual(len(begins), len(full_card().info))
        self.assertEqual(begins, sorted(begins))
        self.assertGreaterEqual(begins[0], 2.2)

    def test_static_frame_is_finished_card(self):
        # with animation disabled or unsupported, the document itself must be the final card
        ns = "{http://www.w3.org/2000/svg}"
        root = ET.fromstring(build_svg(full_card(), DARK).encode("utf-8"))
        crt = root.find(f".//{ns}g[@id='crt']")
        intro_only = {id(e) for e in crt.iter()}
        for el in root.iter():
            if id(el) in intro_only or "boot" in (el.get("class") or ""):
                continue
            self.assertNotEqual(el.get("opacity"), "0", f"{el.tag} {el.attrib}")
        for clip in root.iter(f"{ns}clipPath"):
            for r in clip.iter(f"{ns}rect"):
                self.assertNotIn("0", (r.get("width"), r.get("height")), clip.get("id"))
        shutters = [r for r in crt.findall(f"{ns}rect") if r.get("fill") == DARK["bg0"]]
        self.assertEqual(len(shutters), 2)
        self.assertTrue(all(r.get("visibility") == "hidden" for r in shutters))

    def test_glitch_filter_present(self):
        svg = build_svg(full_card(), DARK)
        self.assertIn('id="glitch"', svg)
        self.assertIn('dur="7s"', svg)


if __name__ == "__main__":
    unittest.main()
