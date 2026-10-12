# Terminal Profile Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an animated terminal-style profile card (`dark.svg` / `light.svg`) with Walber's photo as color-cycling ASCII art, identity info, GitHub metrics and a contribution heatmap, refreshed daily by a GitHub Action.

**Architecture:** A small Python package `scripts/profilecard/` with three focused modules — `portrait` (photo → ASCII lines), `data` (GitHub/WakaTime fetchers + pure metric math), `render` (SVG string builder) — driven by `scripts/build_profile.py`, which holds the editable `DATA`/`PALETTES` config and writes both SVGs to the repo root. Animations are SMIL inside the SVG.

**Tech Stack:** Python 3.12+ (local 3.14), Pillow, stdlib only otherwise (`urllib`, `json`, `xml.etree` for tests, `unittest`), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-11-profile-card-design.md`

## Global Constraints

- Only third-party dependency: Pillow. Tests use stdlib `unittest` (`py -m unittest discover -s tests -v`); no pytest.
- Generated `dark.svg` / `light.svg` are never edited by hand; regenerate with `py scripts/build_profile.py` from the repo root.
- SVG viewBox width is `1180`; height is computed (`canvas_h`), never hardcoded downstream.
- Palettes (exact): dark gradient `#00E5FF`, `#FF2BD6`, `#7C4DFF`, background `#0B0F19` → `#111827`; light gradient `#0891B2`, `#C026D3`, `#6D28D9`, background `#F8FAFC` → `#EEF2F7`.
- Gradient color cycle `dur="9s"`; glitch burst cycle `dur="7s"`.
- Scanline blend: `screen` on dark, `multiply` on light.
- Prompt/user string: `walber@dev`; title bar `walber@dev ~ % ./profile.sh --live`.
- Uptime: days since `2020-02-01`, rendered `up <days>d`.
- GitHub user: `WalberFellipe`; account creation year 2019.
- Token precedence: `GH_PAT` → `GITHUB_TOKEN` → none. Every fetcher returns `None` on any failure; missing values render as `—`, never `None`.
- Workflow triggers: `schedule` cron `0 3 * * *` and `workflow_dispatch` only (no `push`).
- Nothing is pushed to GitHub without Walber's explicit OK.

## Review Focus

1. Long SYSTEM.INFO values (`Diagonal Social · Studying AI Engineering`, 41 chars) must fit inside the info panel without clipping — Task 3 test `test_info_values_fit_panel`.
2. Non-ASCII text (`Araxá`, `•`, `·`) must survive: file written as UTF-8 with an XML declaration — Task 4 test `test_written_files_are_utf8_and_keep_accents`.
3. Partial API failure (e.g. search rate-limited → `prs=None`, no languages) must render `—` / omit bars, never the string `None` or a division error — Task 3 test `test_missing_metrics_render_dash`.
4. CI runs at 03:00 UTC, when today usually has 0 contributions: the current streak must still count up to yesterday — Task 2 test `test_current_streak_survives_empty_today`.
5. Light theme effects must stay visible on a white background (multiply scanline, dark gradient stops) — Task 3 test `test_theme_specific_blend_and_colors`.

---

### Task 1: Portrait pipeline (photo → ASCII)

**Files:**
- Create: `assets/portrait.png` (copy of the user's photo, 256×256 RGB)
- Create: `scripts/profilecard/__init__.py` (empty)
- Create: `scripts/profilecard/portrait.py`
- Create: `tests/__init__.py` (empty), `tests/_path.py` (inserts `<repo>/scripts` into `sys.path`; every test module does `import tests._path`)
- Test: `tests/test_portrait.py`

**Interfaces:**
- Produces:
  - `subject_mask(img: Image.Image) -> Image.Image` — mode `"L"`, same size, 255 = subject, 0 = background.
  - `portrait_ascii(path: str, cols: int = 100, crop: tuple[float, float, float, float] = (0.06, 0.0, 0.94, 0.84), ramp: str = RAMP) -> list[str]` — rows right-stripped; every row `len <= cols`.
  - `RAMP = " .'`:-~=+*cvxzsoaekw%8B#@"` (index 0 = background only).

- [ ] **Step 1: Copy the photo**

Copy the user's photo to `assets/portrait.png`. (Source in this session: the `images/2.png` attachment in the session temp dir.) Verify: `py -c "from PIL import Image; print(Image.open('assets/portrait.png').size)"` → `(256, 256)`.

- [ ] **Step 2: Write the failing tests** in `tests/test_portrait.py`

```python
def test_mask_synthetic_square(self):
    img = Image.new("RGB", (40, 40), (225, 225, 220))         # light gray bg
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
    self.assertEqual(m.getpixel((0, 128)), 0)     # left background
    self.assertEqual(m.getpixel((128, 128)), 255) # face

def test_ascii_shape(self):
    rows = portrait_ascii(PHOTO, cols=100)
    self.assertTrue(40 <= len(rows) <= 70)
    self.assertTrue(all(len(r) <= 100 for r in rows))
    self.assertEqual(rows[0][:10].strip(), "")    # top-left is background

def test_subject_never_blank(self):
    # silhouette preserved: centre column of the bottom row is a non-space glyph
    rows = portrait_ascii(PHOTO, cols=100)
    self.assertNotEqual(rows[-1].ljust(100)[50], " ")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `py -m unittest tests.test_portrait -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'profilecard'`.

- [ ] **Step 4: Implement `subject_mask` and `portrait_ascii`**

`subject_mask`: BFS flood fill seeded from every border pixel where luma > 150 and `max(rgb) - min(rgb) < 40`, expanding only through pixels meeting the same test; then `MedianFilter(5)`. `portrait_ascii`: crop by fractions, grayscale → `autocontrast(cutoff=1)` → `Contrast(1.25)`; rows = `int(cols * (h / w) * 0.60)` (monospace advance 0.60, line-height 1.0); resize gray and mask with LANCZOS; mask < 128 → `" "`, else `ramp[1 + int(v * (len(ramp) - 2))]`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -m unittest tests.test_portrait -v`
Expected: 5 tests OK.

- [ ] **Step 6: Commit**

```bash
git add assets/portrait.png scripts/profilecard tests
git commit -m "feat: photo to ASCII portrait with light-background removal"
```

---

### Task 2: Data layer (metric math + None-safe fetchers)

**Files:**
- Create: `scripts/profilecard/data.py`
- Test: `tests/test_data.py`

**Interfaces:**
- Produces:
  - `compute_streaks(days: list[tuple[datetime.date, int]], today: datetime.date) -> dict` with keys `total: int`, `current: int`, `longest: int`. Current streak ends at `today` if today > 0, else at `today - 1`.
  - `fmt_num(n: int | None) -> str` — `1234 → "1,234"`, `None → "—"`.
  - `ago(iso: str | None, now: datetime.datetime) -> str` — `"<m>m ago"` / `"<h>h ago"` / `"<d>d ago"`, `""` on bad input.
  - `uptime_days(since: datetime.date, today: datetime.date) -> int`.
  - `fetch_calendar(user: str, token: str | None, since_year: int, today: datetime.date) -> list[tuple[date, int]] | None` — GraphQL `contributionsCollection(from, to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}`, one query per year, deduplicated, sorted. `None` when no token or on any error.
  - `fetch_github(user: str, token: str | None, private: bool) -> dict | None` — keys `followers, following, repos, stars, forks, prs, issues, langs: list[tuple[str, int]]` (top 5, percent), `top_repos: list[tuple[str, int, str]]` (name ≤17 chars, stars, language; top 3 by stars then `pushed_at`), `last_push: str | None` (ISO), `joined: int | None` (year). `private=True` uses `/user/repos?affiliation=owner&visibility=all`; per-repo language calls capped to the 80 most recently pushed. Individual sub-request failures set that key to `None`/`[]` instead of failing the whole dict.
  - `fetch_wakatime(key: str | None) -> dict | None` — `{"range": "ALL TIME", "langs": [(name, "1400h26m"), ...top 5], "total": "3,840 hrs", "daily_avg": "4 hrs 13 mins"}`; tries `all_time → last_year → last_30_days → last_7_days`.
  - All HTTP goes through one helper `_get_json(url: str, token: str | None, body: dict | None = None) -> dict` so tests can patch `profilecard.data._get_json`.

- [ ] **Step 1: Write the failing tests** in `tests/test_data.py`

```python
D = datetime.date
def series(start, counts):  # helper: consecutive days from start
    return [(start + datetime.timedelta(i), c) for i, c in enumerate(counts)]

def test_streaks_basic(self):
    s = compute_streaks(series(D(2026, 1, 1), [1, 2, 0, 3, 1, 1]), D(2026, 1, 6))
    self.assertEqual(s, {"total": 8, "current": 3, "longest": 3})

def test_current_streak_survives_empty_today(self):
    s = compute_streaks(series(D(2026, 1, 1), [1, 1, 1, 0]), D(2026, 1, 4))
    self.assertEqual(s["current"], 3)

def test_current_streak_broken_yesterday(self):
    s = compute_streaks(series(D(2026, 1, 1), [1, 1, 0, 0]), D(2026, 1, 4))
    self.assertEqual(s["current"], 0)

def test_fmt_num(self):
    self.assertEqual(fmt_num(15698), "15,698"); self.assertEqual(fmt_num(None), "—")

def test_ago(self):
    now = datetime.datetime(2026, 10, 11, 12, tzinfo=datetime.timezone.utc)
    self.assertEqual(ago("2026-10-10T13:00:00Z", now), "23h ago")
    self.assertEqual(ago("2026-10-01T12:00:00Z", now), "10d ago")
    self.assertEqual(ago("garbage", now), "")

def test_uptime(self):
    self.assertEqual(uptime_days(D(2020, 2, 1), D(2026, 10, 11)), 2444)

def test_calendar_without_token_is_none(self):
    self.assertIsNone(fetch_calendar("WalberFellipe", None, 2019, D(2026, 10, 11)))

def test_fetchers_swallow_network_errors(self):
    with mock.patch("profilecard.data._get_json", side_effect=OSError("down")):
        self.assertIsNone(fetch_calendar("u", "t", 2019, D(2026, 10, 11)))
        self.assertIsNone(fetch_github("u", "t", private=False))
        self.assertIsNone(fetch_wakatime("k"))

def test_github_partial_failure_keeps_rest(self):
    # profile + repos succeed, search endpoint fails -> prs/issues None, rest present
    def fake(url, token, body=None):
        if "/search/" in url: raise OSError("rate limited")
        if url.endswith("/users/u"): return {"followers": 10, "following": 3, "public_repos": 2, "created_at": "2019-06-03T00:00:00Z"}
        if "/repos?" in url: return [{"name": "a", "full_name": "u/a", "fork": False, "stargazers_count": 2,
                                      "forks_count": 1, "language": "TypeScript", "pushed_at": "2026-10-10T00:00:00Z"}]
        if url.endswith("/languages"): return {"TypeScript": 300, "Python": 100}
        return []
    with mock.patch("profilecard.data._get_json", side_effect=fake):
        g = fetch_github("u", "t", private=False)
    self.assertEqual((g["stars"], g["forks"], g["followers"]), (2, 1, 10))
    self.assertIsNone(g["prs"])
    self.assertEqual(g["langs"], [("TypeScript", 75), ("Python", 25)])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m unittest tests.test_data -v`
Expected: ERROR `ImportError: cannot import name 'compute_streaks'`.

- [ ] **Step 3: Implement `scripts/profilecard/data.py`** with the signatures above. `_get_json` uses `urllib.request` with `User-Agent: profile-card`, `Accept: application/vnd.github+json`, `Authorization: Bearer <token>` when given, timeout 30s; POSTs JSON when `body` is set (GraphQL at `https://api.github.com/graphql`). WakaTime uses Basic auth with the base64 key — give `_get_json` an optional `auth_header: str | None` keyword for it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m unittest tests.test_data -v`
Expected: 9 tests OK.

- [ ] **Step 5: Live smoke check (network, not a unit test)**

Run: `GITHUB_TOKEN=$(gh auth token) py -c "import os,sys,datetime; sys.path.insert(0,'scripts'); from profilecard.data import *; t=os.environ['GITHUB_TOKEN']; c=fetch_calendar('WalberFellipe',t,2019,datetime.date.today()); print(len(c), compute_streaks(c, datetime.date.today())); print(fetch_github('WalberFellipe',t,False))"`
Expected: a day count > 2000, a streak dict, and a dict with `followers` ≈ 10 and `repos` ≈ 22.

- [ ] **Step 6: Commit**

```bash
git add scripts/profilecard/data.py tests/test_data.py
git commit -m "feat: None-safe GitHub/WakaTime fetchers and streak math"
```

---

### Task 3: SVG renderer — layout, panels, themes

**Files:**
- Create: `scripts/profilecard/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `fmt_num`, `ago` from Task 2; ASCII rows from Task 1 (plain `list[str]`).
- Produces:
  - `@dataclass Card` with fields: `info: list[tuple[str, str]]` (ordered key/value; a key starting with `"—"` renders as a section divider, e.g. `("— Contact", "")`), `user: str`, `uptime_days: int`, `ascii_rows: list[str]`, `streaks: dict | None`, `github: dict | None`, `wakatime: dict | None`, `calendar: list[tuple[date, int]] | None` (last 371 days used), `sync_date: str`, `now: datetime.datetime`.
  - `build_svg(card: Card, palette: dict[str, str]) -> str` — complete SVG document string starting with `<?xml version="1.0" encoding="UTF-8"?>`.
  - `INFO_PANEL = (x, y, w, h)` and `VALUE_COL` module constants used by the fit test.
  - Palette dict keys (both themes must define all): `g1 g2 g3 bg0 bg1 panel border text muted label accent scanblend scanop heat0 heat1 heat2 heat3 heat4`.

Layout (viewBox `0 0 1180 canvas_h`): title bar 0–40 (red/amber/green dots at x 24/42/60, centered title, `SCANNING` label with a dot at the right); VISUAL.MAP panel `x=12 y=50 w=500 h=470`; SYSTEM.INFO `x=524 y=50 w=644 h=470`; SYSTEM.METRICS full width `y=532 h≈150`; GIT.ACTIVITY full width below it `h≈150`; `canvas_h = activity_bottom + 12`. ASCII font: `font-size 6.2px`, line height 6.2, advance 0.60 em; centre the portrait on its non-blank rows inside VISUAL.MAP. Info font: 13px monospace, line height 17, `xml:space="preserve"`; each line is `key + "." * pad` to `VALUE_COL = 22` chars, then value. Heatmap: 53 columns × 7 rows of 9px cells, 2px gap, levels by quartile of non-zero counts → `heat0..heat4`.

Static content only in this task (no `<animate>` yet) so it can be checked as a still image.

- [ ] **Step 1: Write the failing tests** in `tests/test_render.py` (build a `Card` fixture `full_card()` with the spec's DATA rows, 60 dummy ASCII rows of `"x" * 90`, realistic streaks/github/calendar; and `empty_card()` with all fetched fields `None`)

```python
def test_is_valid_xml_with_viewbox(self):
    svg = build_svg(full_card(), DARK)
    root = ET.fromstring(svg.encode("utf-8"))
    w, h = root.get("viewBox").split()[2:]
    self.assertEqual(w, "1180"); self.assertGreater(float(h), 800)

def test_contains_identity_and_title(self):
    svg = build_svg(full_card(), DARK)
    for s in ["walber@dev ~ % ./profile.sh --live", "up 2444d", "Walber Fellipe",
              "Araxá - MG, Brazil", "walberfellipe18@gmail.com", "walber-fellipe"]:
        self.assertIn(s, svg)

def test_escapes_markup(self):
    c = full_card(); c.info.append(("Note", "R&D <AI>"))
    self.assertIn("R&amp;D &lt;AI&gt;", build_svg(c, DARK))

def test_info_values_fit_panel(self):
    x, y, w, h = INFO_PANEL
    longest = max(VALUE_COL + len(v) for _, v in full_card().info)
    self.assertLessEqual(16 + longest * 13 * 0.60, w)          # 16px inner padding
    self.assertLessEqual(len(full_card().info) * 17 + 60, h)    # header + rows fit

def test_missing_metrics_render_dash(self):
    svg = build_svg(empty_card(), DARK)
    ET.fromstring(svg.encode("utf-8"))
    self.assertNotIn("None", svg)
    self.assertIn("—", svg)

def test_theme_specific_blend_and_colors(self):
    d, l = build_svg(full_card(), DARK), build_svg(full_card(), LIGHT)
    self.assertIn("#00E5FF", d); self.assertIn("#0891B2", l)
    self.assertIn("mix-blend-mode:screen", d); self.assertIn("mix-blend-mode:multiply", l)

def test_heatmap_has_371_cells_or_none(self):
    self.assertEqual(build_svg(full_card(), DARK).count('class="hm"'), 371)
    self.assertEqual(build_svg(empty_card(), DARK).count('class="hm"'), 0)
```

`DARK` / `LIGHT` are imported from `build_profile` (Task 4) — until then define them in `scripts/profilecard/palettes.py` and have `build_profile.py` re-export them. (Create `scripts/profilecard/palettes.py` in this task with both palettes using the exact Global Constraints hex values; pick the remaining keys to match.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m unittest tests.test_render -v`
Expected: ERROR `ImportError: cannot import name 'build_svg'`.

- [ ] **Step 3: Implement `render.py` and `palettes.py`**

Small private helpers per panel (`_title_bar`, `_visual_map`, `_system_info`, `_metrics`, `_activity`) each returning an SVG fragment string and taking `(card, palette, y)`; `build_svg` stacks them and computes `canvas_h`. All text goes through `xml.sax.saxutils.escape`. ASCII text is filled with `url(#asciiGrad)` (`<linearGradient id="asciiGrad">` with stops `g1`, `g2`). Scanline group carries `style="mix-blend-mode:{scanblend}"`. Language bars use widths proportional to percent (or hours) with max 110px; skipped entirely when `langs` is empty. When `wakatime` is set, LANGUAGES shows hours and a CODE TIME line `CODE TIME · <range>  <total> total · avg <daily_avg>/day` is added under the metrics columns.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m unittest tests.test_render -v`
Expected: 7 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/profilecard/render.py scripts/profilecard/palettes.py tests/test_render.py
git commit -m "feat: static terminal card renderer with dark and light palettes"
```

---

### Task 4: Animation layer, entry point, README, workflow

**Files:**
- Modify: `scripts/profilecard/render.py` (add SMIL)
- Create: `scripts/build_profile.py`
- Create: `.github/workflows/refresh.yml`
- Modify: `README.md` (replace default content)
- Test: `tests/test_render.py` (add animation tests), `tests/test_build.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `scripts/build_profile.py`: module constants `USER = "WalberFellipe"`, `HANDLE = "walber@dev"`, `CODING_SINCE = date(2020, 2, 1)`, `JOINED_YEAR = 2019`, `INFO: list[tuple[str, str]]` (spec table order, with `("— Contact", "")` divider), `PALETTES = {"dark": DARK, "light": LIGHT}`; `main(out_dir: str = ROOT, today: date | None = None) -> list[str]` returns written paths.
  - Animation timing constants in `render.py`: `BOOT_END = 2.2`, info line `i` begins at `BOOT_END + 0.10 * i`, cards begin after the last info line + 0.3s.

Animation content (all SMIL, `fill="freeze"` for intro, `repeatCount="indefinite"` for loops):
CRT power-on (two shutter rects translate away at 0.42s over 0.5s + flash rect opacity 0→1→0); boot log lines (`> booting devOS...`, `> mounting /portrait`, `> loading profile.sh`) appear 0.18s apart and fade by `BOOT_END`; portrait reveal = clipPath rect height 0→full over 2.4s starting at `BOOT_END`; each info line is clipped by a rect whose width animates 0→panel width over 0.34s at its begin time; cursor blinks 1.05s; `asciiGrad` stops animate `stop-color` g1→g2→g3→g1 with `dur="9s"`; ASCII group opacity flicker 3.8s; scanline translates top→bottom 4.6s; `#glitch` filter (feTurbulence + feDisplacementMap whose `scale` animates `0;0;22;3;14;0;0` at keyTimes `0;0.71;0.735;0.76;0.8;0.84;1`, `dur="7s"`) applied to the card group; metrics/activity groups fade + translate 16px→0 over 0.7s; heatmap cells reveal column by column (0.012s per column); language bars grow width over 0.6s.

- [ ] **Step 1: Write the failing tests**

In `tests/test_render.py`:
```python
def test_gradient_cycles_every_9s(self):
    svg = build_svg(full_card(), DARK)
    self.assertRegex(svg, r'attributeName="stop-color"[^>]*dur="9s"')

def test_info_lines_type_in_order(self):
    svg = build_svg(full_card(), DARK)
    begins = [float(b) for b in re.findall(r'id="lc\d+".*?begin="([\d.]+)s"', svg, re.S)]
    self.assertEqual(len(begins), len(full_card().info))
    self.assertEqual(begins, sorted(begins)); self.assertGreaterEqual(begins[0], 2.2)

def test_glitch_filter_present(self):
    svg = build_svg(full_card(), DARK)
    self.assertIn('id="glitch"', svg); self.assertIn('dur="7s"', svg)
```
In `tests/test_build.py`:
```python
def test_offline_build_writes_both_themes(self):
    with mock.patch("profilecard.data._get_json", side_effect=OSError), \
         mock.patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as d:
        paths = build_profile.main(out_dir=d, today=datetime.date(2026, 10, 11))
        self.assertEqual(sorted(os.path.basename(p) for p in paths), ["dark.svg", "light.svg"])
        for p in paths: ET.parse(p)

def test_written_files_are_utf8_and_keep_accents(self):
    with mock.patch("profilecard.data._get_json", side_effect=OSError), tempfile.TemporaryDirectory() as d:
        p = build_profile.main(out_dir=d, today=datetime.date(2026, 10, 11))[0]
        raw = open(p, "rb").read()
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn("Araxá".encode("utf-8"), raw)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m unittest discover -s tests -v`
Expected: the 3 new render tests FAIL; `test_build` ERRORs with `ModuleNotFoundError: No module named 'build_profile'`.

- [ ] **Step 3: Add the animation layer to `render.py`** per the content list above, keeping each effect in its own helper.

- [ ] **Step 4: Implement `scripts/build_profile.py`**

`main` reads tokens per Global Constraints (`GH_PAT` → private=True), calls the three fetchers + `compute_streaks`, builds one `Card`, renders each palette, writes `<out_dir>/<theme>.svg` with `encoding="utf-8", newline="\n"`, prints `wrote dark.svg (ascii rows=N)`. Runnable as `py scripts/build_profile.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -m unittest discover -s tests -v`
Expected: all tests OK (5 + 9 + 10 + 2 = 26).

- [ ] **Step 6: Write `README.md`**

```html
<div align="center">
<a href="https://github.com/WalberFellipe">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="https://raw.githubusercontent.com/WalberFellipe/WalberFellipe/main/dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/WalberFellipe/WalberFellipe/main/light.svg">
    <img alt="Walber Fellipe — terminal profile card" src="https://raw.githubusercontent.com/WalberFellipe/WalberFellipe/main/dark.svg" width="100%">
  </picture>
</a>
</div>
```

- [ ] **Step 7: Write `.github/workflows/refresh.yml`**

Job `refresh-card` on `ubuntu-latest`, `permissions: contents: write`, `timeout-minutes: 5`: `actions/checkout@v4`, `actions/setup-python@v5` (3.12), `pip install pillow`, `python scripts/build_profile.py` with env `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`, `GH_PAT: ${{ secrets.GH_PAT }}`, `WAKATIME_API_KEY: ${{ secrets.WAKATIME_API_KEY }}`; then commit `dark.svg light.svg` as `github-actions[bot]` (`41898282+github-actions[bot]@users.noreply.github.com`) with `chore: daily profile card refresh` only if `git diff --staged --quiet` fails. Triggers exactly per Global Constraints. Verify: `grep -nP '\t' .github/workflows/refresh.yml` prints nothing, and the `on:` block lists only `schedule` and `workflow_dispatch`.

- [ ] **Step 8: Generate the real SVGs**

Run: `GITHUB_TOKEN=$(gh auth token) py scripts/build_profile.py`
Expected: `wrote dark.svg …` and `wrote light.svg …`; both files > 40 KB.

- [ ] **Step 9: Commit**

```bash
git add scripts .github README.md dark.svg light.svg tests
git commit -m "feat: animated card, build entry point, README and daily refresh workflow"
```

---

### Task 5: Visual verification and tuning

**Files:**
- Modify (only if tuning is needed): `scripts/profilecard/portrait.py` defaults (`crop`, contrast), `scripts/profilecard/render.py` spacing constants, `scripts/profilecard/palettes.py` non-gradient colors
- Regenerate: `dark.svg`, `light.svg`

- [ ] **Step 1: Open `dark.svg` in the built-in browser** — add a `.claude/launch.json` entry `{"name": "card", "runtimeExecutable": "py", "runtimeArgs": ["-m", "http.server", "8765"], "port": 8765}`, `preview_start` it, navigate to `http://localhost:8765/dark.svg` — and screenshot at ~1s (boot), ~3s (typing), ~6s (idle), and during a glitch (pause with `document.querySelector('svg').pauseAnimations(); setCurrentTime(t)` via the JS tool).
Expected: portrait recognizable as Walber, no characters outside the VISUAL.MAP panel, every SYSTEM.INFO value aligned on one column and inside the panel, metrics/heatmap fully visible, nothing clipped at the canvas bottom.

- [ ] **Step 2: Same for `light.svg` with `colorScheme: "light"`.**
Expected: portrait and scanline clearly visible on the light background.

- [ ] **Step 3: Tune and regenerate** if any check fails; rerun `py -m unittest discover -s tests -v` (all OK) after every change.

- [ ] **Step 4: Show Walber** the dark and light screenshots and wait for approval. Do not push.

- [ ] **Step 5: Commit**

```bash
git add -A scripts dark.svg light.svg
git commit -m "chore: tune portrait and layout after visual review"
```

- [ ] **Step 6: Push only after Walber's explicit OK** — `git push origin main`, then trigger the workflow once with `gh workflow run refresh.yml` and confirm it succeeds with `gh run list --workflow refresh.yml --limit 1`.
