# Terminal profile card — design

Date: 2026-10-11 · Status: approved in chat

## Goal

Replace the default profile README of `WalberFellipe/WalberFellipe` with an animated
terminal-style card. The centerpiece is Walber's photo rendered as ASCII art whose
color cycles through a neon gradient, next to identity info, GitHub metrics, and a
contribution heatmap. The generator is written from scratch, with portrait
processing designed for a light-background photo.

Success: opening github.com/WalberFellipe shows the animated card in both GitHub
themes, the portrait is recognizable, and metrics refresh daily without manual work.

## Approach

A Python + Pillow generator writes two self-contained SVGs (`dark.svg`, `light.svg`)
animated with SMIL. GitHub plays SMIL inside `<img>` when the SVG is served from
`raw.githubusercontent.com`, so the README references the raw URLs. A daily GitHub
Action regenerates the SVGs and commits them when they change.

## Repository layout

```
README.md                         <picture> with dark/light sources, nothing else
dark.svg, light.svg               generated — never edited by hand
assets/portrait.png               source photo (256×256, light-gray background)
scripts/build_profile.py          generator; DATA and PALETTES at the top
.github/workflows/refresh.yml     daily + manual regeneration
docs/superpowers/specs/…          this spec
```

## Portrait pipeline

1. **Background removal** — flood fill from every border pixel that is light and
   unsaturated (luma > 150, max−min channel < 40), then a 5px median filter on the
   mask. The black shirt and dark hair are not reachable from the light border, so
   they stay in the subject. No ML dependency.
2. **Crop** — fractions `CROP = (x0, y0, x1, y1)` trimming most of the shirt
   (starting point from the probe: `0.06, 0.0, 0.94, 0.84`).
3. **Tone** — grayscale, autocontrast, contrast boost; tuned by eye against rendered
   output.
4. **Mapping** — resize to `COLS` × rows (rows derived from the monospace cell
   ratio so the face is not stretched); background cells → space; subject cells →
   ramp index ≥ 1 so the silhouette (hair, shirt) never disappears — except in the
   bottom 25% of rows, which dissolve into deterministic noise so the shoulders fade
   out instead of ending in a hard edge.
   The light theme inverts the tones (dark pixels → dense glyphs) so the portrait
   reads as ink on paper rather than a photo negative.
5. **Color** — the ASCII `<text>` is filled with a linear gradient whose stops
   animate through the palette on a 9s loop.

## Palettes

| Token        | Dark theme | Light theme |
|--------------|-----------|-------------|
| gradient 1   | `#00E5FF` | `#0891B2`   |
| gradient 2   | `#FF2BD6` | `#C026D3`   |
| gradient 3   | `#7C4DFF` | `#6D28D9`   |
| background   | `#0B0F19` → `#111827` | `#F8FAFC` → `#EEF2F7` |

Light-theme stops are darker variants of the same hues because pure cyan is
unreadable on white. Panel borders, labels, and heatmap levels derive from the same
three hues per theme. Scanline blend is `screen` on dark, `multiply` on light.

## Card layout (viewBox width 1180, height computed)

- **Title bar** — traffic-light dots, `walber@dev ~ % ./profile.sh --live`,
  blinking `SCANNING` indicator.
- **VISUAL.MAP** (left) — the ASCII portrait, vertically centered on its visible rows.
- **SYSTEM.INFO** (right) — header `walber@dev · up <days>d` (days since
  2020-02-01), then dotted key/value lines aligned on a fixed value column:

  | Key           | Value |
  |---------------|-------|
  | Subject       | Walber Fellipe |
  | Role          | Full-stack Developer / AI Engineer |
  | Origin        | Araxá - MG, Brazil |
  | Status        | Building • Learning • Shipping |
  | Currently     | Diagonal Social · Studying AI Engineering |
  | ToolChain     | VS Code, IntelliJ, Git, Docker |
  | Core Lang     | TypeScript, Python, PHP, Kotlin |
  | Core Frontend | React, Next |
  | Core Backend  | Node.js, Nest, Express, Fastify, FastAPI |
  | Core Mobile   | React Native, Flutter |
  | Core Database | PostgreSQL, MongoDB, SQLite, Redis |
  | Core ORM/BaaS | Prisma, Drizzle, Supabase, Firebase |
  | Core Cloud    | AWS (S3, Cognito), Google Cloud, BigQuery |
  | Core AI       | LLM, RAG, MCP, TensorFlow.js |
  | Integrations  | Stripe, Pusher, Magento |
  | — Contact —   | |
  | Mail          | walberfellipe18@gmail.com |
  | Portfolio     | walberfellipe.com.br |
  | LinkedIn      | walber-fellipe |
  | Github        | WalberFellipe |

  ends with a blinking `>` cursor.
- **SYSTEM.METRICS** (full width) — CONTRIBUTIONS (total, current streak, longest
  streak, since), IMPACT (stars, forks, PRs, issues), NETWORK (followers, following,
  repos), LANGUAGES (top 5 with grow-in bars), sync date. Optional CODE TIME line.
- **GIT.ACTIVITY** (full width) — 1-year contribution heatmap (wave reveal by
  column), TOP REPOS (top 3 by stars, then most recent push), ACTIVITY (last push,
  years on GitHub).

The canvas height is computed from the panel positions; nothing downstream
hardcodes it.

## Animation sequence

CRT power-on (shutters + flash) → boot log types and fades → portrait reveal mask
opens → info lines type in staggered → metrics/activity cards slide and fade in →
idle loop: gradient cycling (9s), blinking cursor, scanline sweep, RGB glitch burst
about every 7s.

## Data sources

All fetched at build time; every fetcher returns `None` on failure and the
renderer prints `—` or omits the row, so the build never fails on network errors.

- **GraphQL** (needs a token): `contributionsCollection` per year from the account
  creation year (2019) to today → total contributions, current and longest
  streak, and the last 365 days for the heatmap. Streaks are computed locally from
  the calendar; no third-party stats service.
- **REST**: profile (followers, following, created_at), owned non-fork repos
  (stars, forks, pushed_at, top repos), per-repo languages by bytes (capped to the
  80 most recently pushed), PR and issue counts via search.
- **WakaTime** (optional, `WAKATIME_API_KEY`): hours per language and the CODE TIME
  line; when present it drives LANGUAGES, else GitHub bytes (%).
- **Token precedence**: `GH_PAT` (includes private repos) → `GITHUB_TOKEN` →
  unauthenticated (REST only; GraphQL sections omitted).

## Workflow

`.github/workflows/refresh.yml`: triggers `schedule` (daily 03:00 UTC) and
`workflow_dispatch`. Steps: checkout, Python 3.12, `pip install pillow`, run the
generator with `GITHUB_TOKEN`, `GH_PAT`, `WAKATIME_API_KEY`, commit `dark.svg` and
`light.svg` as `github-actions[bot]` only if they changed. No `push` trigger, so
the bot commit cannot loop.

## Verification

- Generator runs locally with `GITHUB_TOKEN=$(gh auth token)` and writes both SVGs.
- Both SVGs parse as XML.
- Open each SVG in the built-in browser and screenshot at several moments
  (boot, mid-typing, idle, glitch) in both themes; check portrait likeness,
  alignment of the info column, nothing clipped at the canvas edge.
- Offline run (no token) still produces valid SVGs.
- Walber reviews the rendered card before anything is pushed.

## Out of scope

Snake contribution animation, extra README sections or badges, Instagram,
WhatsApp, and an "Open To" line.
