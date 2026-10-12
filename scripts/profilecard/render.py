"""Card data -> one self-contained SVG document (terminal-style profile card)."""
import dataclasses
import datetime
from xml.sax.saxutils import escape

from .data import ago, fmt_num
from .portrait import ADVANCE

W = 1180
GAP = 12
MONO = "'SF Mono', Menlo, Consolas, 'Liberation Mono', 'Courier New', monospace"
ASCII_FONT = "'Courier New', Consolas, monospace"
FS_ASCII = 6.6

MAP_PANEL = (12, 50, 500, 470)
INFO_PANEL = (524, 50, 644, 470)
INFO_FS, INFO_LH = 13, 17
VALUE_COL = 22                      # info values start at this character column
METRICS_Y, METRICS_H = 532, 150
ACTIVITY_H = 150
HEAT_DAYS, CELL, CELL_GAP = 371, 9, 2

# animation timeline (seconds)
BOOT_END = 2.2                      # boot log gone; portrait reveal + info typing start
LINE_STEP = 0.10                    # stagger between typed info lines
TYPE_DUR = 0.34
BOOT_LINES = ("> booting devOS...", "> mounting /portrait", "> loading profile.sh")


def _line_begin(i):
    return BOOT_END + LINE_STEP * i


def _cards_begin(card):
    return _line_begin(len(card.info)) + 0.3


def _slide_in(gid, body, begin):
    return (f'<g id="{gid}" opacity="0">{_fade_in(begin)}'
            f'<animateTransform attributeName="transform" type="translate" from="0 16" to="0 0" '
            f'dur="0.7s" begin="{begin:.2f}s" fill="freeze" calcMode="spline" keyTimes="0;1" '
            f'keySplines="0.2 0.8 0.2 1"/>{body}</g>')


def _fade_in(begin, dur=0.7):
    return (f'<animate attributeName="opacity" from="0" to="1" dur="{dur}s" '
            f'begin="{begin:.2f}s" fill="freeze"/>')


@dataclasses.dataclass
class Card:
    info: list
    user: str
    uptime_days: int
    ascii_rows: list
    streaks: dict | None
    github: dict | None
    wakatime: dict | None
    calendar: list | None
    sync_date: str
    now: datetime.datetime


def _t(x, y, text, cls, extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}"{extra}>{escape(str(text))}</text>'


def _dotted(key, value, width):
    """'key ...... value' with the value starting at character column `width`."""
    return (key + " ").ljust(width - 1, ".") + " " + value


def _panel(x, y, w, h, label, p):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{p["panel"]}" '
            f'fill-opacity="0.72" stroke="{p["border"]}"/>'
            + _t(x + 12, y + 16, label, "mono lbl"))


# ------------------------------------------------------------------ sections

def _title_bar(card, p):
    dots = "".join(f'<circle cx="{cx}" cy="20" r="5" fill="{c}"/>'
                   for cx, c in ((24, "#EF4444"), (42, "#F59E0B"), (60, "#10B981")))
    title = (f'<text x="{W / 2}" y="24" text-anchor="middle" class="mono m sm">'
             f'{escape(card.user)} ~ % ./profile.sh --live</text>')
    scan = (f'<circle id="scandot" cx="{W - 98}" cy="20" r="4" fill="{p["accent"]}">'
            f'<animate attributeName="opacity" values="1;0.15;1" dur="1.1s" repeatCount="indefinite"/>'
            f'</circle>'
            + _t(W - 88, 24, "SCANNING", "mono a lbl2"))
    return dots + title + scan


def _visual_map(card, p):
    x, y, w, h = MAP_PANEL
    rows = card.ascii_rows
    filled = [i for i, r in enumerate(rows) if r.strip()]
    out = [_panel(x, y, w, h, "VISUAL.MAP", p)]
    if not filled:
        return "".join(out)
    first, last = filled[0], filled[-1]
    adv = FS_ASCII * ADVANCE
    x0 = x + (w - max(len(r) for r in rows) * adv) / 2
    y0 = y + (h - (last - first + 1) * FS_ASCII) / 2 - first * FS_ASCII + FS_ASCII * 0.8
    spans = [f'<tspan x="{x0:.1f}" y="{y0 + i * FS_ASCII:.1f}">{escape(r)}</tspan>'
             for i, r in enumerate(rows) if r.strip()]
    out.append(
        f'<clipPath id="reveal"><rect x="{x}" y="{y}" width="{w}" height="0">'
        f'<animate attributeName="height" from="0" to="{h}" dur="2.4s" begin="{BOOT_END:.2f}s" '
        f'fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.25 0.1 0.25 1"/></rect></clipPath>'
        f'<g id="portrait" clip-path="url(#reveal)"><g filter="url(#glitch)">'
        f'<text class="ascii" xml:space="preserve">{"".join(spans)}'
        f'<animate attributeName="opacity" values="0.88;1;0.93;1;0.9" dur="3.8s" '
        f'begin="{BOOT_END + 2.4:.2f}s" repeatCount="indefinite"/></text></g></g>')
    return "".join(out)


def _info_rows(card, p):
    """(y, svg) per info line, header excluded."""
    x, y, w, h = INFO_PANEL
    tx = x + 16
    rows = []
    for i, (key, value) in enumerate(card.info):
        ly = y + 62 + i * INFO_LH
        if key.startswith("—"):
            end = tx + (len(key) + 1) * INFO_FS * ADVANCE
            svg = (_t(tx, ly, key, "mono a info")
                   + f'<line x1="{end:.1f}" y1="{ly - 4}" x2="{x + w - 16}" y2="{ly - 4}" '
                     f'stroke="{p["border"]}"/>')
        else:
            prefix = _dotted(key, "", VALUE_COL)
            svg = (f'<text x="{tx}" y="{ly}" class="mono info" xml:space="preserve">'
                   f'<tspan class="k">{escape(key)}</tspan>'
                   f'<tspan class="m">{escape(prefix[len(key):])}</tspan>'
                   f'<tspan class="v">{escape(value)}</tspan></text>')
        # typing effect: a clip rect sweeps open left to right
        clip = (f'<clipPath id="lc{i}"><rect x="{tx - 2}" y="{ly - 14}" width="0" height="{INFO_LH + 2}">'
                f'<animate attributeName="width" from="0" to="{w - 28}" dur="{TYPE_DUR}s" '
                f'begin="{_line_begin(i):.2f}s" fill="freeze"/></rect></clipPath>')
        rows.append((ly, f'{clip}<g clip-path="url(#lc{i})">{svg}</g>'))
    return rows


def _boot_log(p):
    x, y, w, h = INFO_PANEL
    out = []
    for j, line in enumerate(BOOT_LINES):
        b = 0.95 + j * 0.35
        out.append(f'<text x="{x + 16}" y="{y + 62 + j * INFO_LH}" class="mono k info" opacity="0">'
                   f'{escape(line)}'
                   f'<animate attributeName="opacity" from="0" to="1" dur="0.18s" begin="{b:.2f}s" fill="freeze"/>'
                   f'<animate attributeName="opacity" from="1" to="0" dur="0.3s" begin="{BOOT_END - 0.3:.2f}s" '
                   f'fill="freeze"/></text>')
    return "".join(out)


def _system_info(card, p):
    x, y, w, h = INFO_PANEL
    tx = x + 16
    up = f"up {card.uptime_days}d"
    head_len = len(card.user) + 3 + len(up)
    head = (f'<text x="{tx}" y="{y + 38}" class="mono info" xml:space="preserve">'
            f'<tspan class="a b">{escape(card.user)}</tspan><tspan class="m"> · </tspan>'
            f'<tspan class="k">{escape(up)}</tspan></text>'
            f'<line x1="{tx + head_len * INFO_FS * ADVANCE + 12:.1f}" y1="{y + 34}" '
            f'x2="{x + w - 16}" y2="{y + 34}" stroke="{p["border"]}"/>')
    rows = _info_rows(card, p)
    cy = y + 62 + len(rows) * INFO_LH
    cursor = (f'<g opacity="0">{_fade_in(_line_begin(len(rows)), 0.2)}'
              + _t(tx, cy, ">", "mono k info")
              + f'<rect id="cursor" x="{tx + 14}" y="{cy - 11}" width="8" height="13" fill="{p["label"]}">'
                f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.05s" '
                f'repeatCount="indefinite"/></rect></g>')
    body = "".join(svg for _, svg in rows)
    return _panel(x, y, w, h, "SYSTEM.INFO", p) + head + _boot_log(p) + body + cursor


def _lang_rows(card):
    """[(name, weight, label)] from WakaTime hours when available, else GitHub percent."""
    if card.wakatime:
        out = []
        for name, text in card.wakatime["langs"]:
            hrs, _, mins = text.rstrip("m").partition("h")
            out.append((name, int(hrs or 0) * 60 + int(mins or 0), text))
        return out
    if card.github and card.github.get("langs"):
        return [(name, pct, f"{pct}%") for name, pct in card.github["langs"]]
    return []


def _metrics(card, p, y):
    x, w, h = 12, W - 24, METRICS_H
    s, g = card.streaks or {}, card.github or {}
    days = lambda n: "—" if n is None else f"{n}d"  # noqa: E731
    cols = [
        ("CONTRIBUTIONS", [("total", fmt_num(s.get("total"))), ("current", days(s.get("current"))),
                           ("longest", days(s.get("longest"))), ("since", str(g.get("joined") or "—"))]),
        ("IMPACT", [("stars", fmt_num(g.get("stars"))), ("forks", fmt_num(g.get("forks"))),
                    ("pull reqs", fmt_num(g.get("prs"))), ("issues", fmt_num(g.get("issues")))]),
        ("NETWORK", [("followers", fmt_num(g.get("followers"))), ("following", fmt_num(g.get("following"))),
                     ("repos", fmt_num(g.get("repos")))]),
    ]
    out = [_panel(x, y, w, h, "SYSTEM.METRICS", p),
           f'<text x="{x + w - 14}" y="{y + 16}" text-anchor="end" class="mono m lbl2">'
           f'synced {escape(card.sync_date)}</text>']
    for cx, (header, rows) in zip((30, 300, 560), cols):
        out.append(_t(cx, y + 38, header, "mono h"))
        for i, (k, v) in enumerate(rows):
            out.append(f'<text x="{cx}" y="{y + 58 + i * 16}" class="mono sm" xml:space="preserve">'
                       f'<tspan class="k">{escape(k)}</tspan>'
                       f'<tspan class="m">{escape(_dotted(k, "", 12)[len(k):])}</tspan>'
                       f'<tspan class="v">{escape(v)}</tspan></text>')

    lx = 820
    src = card.wakatime["range"] if card.wakatime else "GITHUB"
    out.append(_t(lx, y + 38, f"LANGUAGES · {src}", "mono h"))
    langs = _lang_rows(card)
    begin = _cards_begin(card)
    top = max((wt for _, wt, _ in langs), default=0)
    for i, (name, wt, label) in enumerate(langs):
        ly = y + 58 + i * 16
        bw = max(2, round(110 * wt / top)) if top else 2
        out.append(_t(lx, ly, name[:12], "mono v sm"))
        out.append(f'<rect class="bar" x="{lx + 100}" y="{ly - 8}" width="{bw}" height="8" rx="2" '
                   f'fill="url(#asciiGrad)"><animate attributeName="width" from="0" to="{bw}" dur="0.6s" '
                   f'begin="{begin + 0.4 + i * 0.1:.2f}s" fill="freeze"/></rect>')
        out.append(_t(lx + 220, ly, label, "mono m sm"))
    if not langs:
        out.append(_t(lx, y + 58, "—", "mono m sm"))

    if card.wakatime:
        wk = card.wakatime
        out.append(f'<text x="30" y="{y + h - 14}" class="mono sm" xml:space="preserve">'
                   f'<tspan class="h">CODE TIME · {escape(wk["range"])}</tspan>'
                   f'<tspan class="v">   {escape(wk["total"])} total · avg {escape(wk["daily_avg"])}/day</tspan>'
                   f'</text>')
    return _slide_in("metrics", "".join(out), begin)


def _heat_levels(counts):
    nz = sorted(c for c in counts if c > 0)
    if not nz:
        return [0] * len(counts)
    q = [nz[int(len(nz) * f)] for f in (0.25, 0.5, 0.75)]
    return [0 if c == 0 else 1 + sum(c > t for t in q) for c in counts]


def _activity(card, p, y):
    x, w, h = 12, W - 24, ACTIVITY_H
    out = [_panel(x, y, w, h, "GIT.ACTIVITY", p),
           _t(30, y + 38, "CONTRIBUTION MATRIX · 1 YEAR", "mono h")]
    gx, gy = 30, y + 48
    begin = _cards_begin(card) + 0.15
    if card.calendar:
        days = card.calendar[-HEAT_DAYS:]
        step = CELL + CELL_GAP
        for i, ((_, c), lvl) in enumerate(zip(days, _heat_levels([c for _, c in days]))):
            out.append(f'<rect class="hm" x="{gx + (i // 7) * step}" y="{gy + (i % 7) * step}" '
                       f'width="{CELL}" height="{CELL}" rx="2" fill="{p[f"heat{lvl}"]}" opacity="0">'
                       f'{_fade_in(begin + 0.3 + (i // 7) * 0.012, 0.28)}</rect>')
        ly = gy + 7 * step + 12
        out.append(_t(gx, ly, "less", "mono m lbl2"))
        out += [f'<rect x="{gx + 30 + k * 12}" y="{ly - 8}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{p[f"heat{k}"]}"/>' for k in range(5)]
        out.append(_t(gx + 94, ly, "more", "mono m lbl2"))
    else:
        out.append(_t(gx, gy + 30, "contribution data unavailable · —", "mono m sm"))

    rx = 720
    g = card.github or {}
    out.append(_t(rx, y + 38, "TOP REPOS", "mono h"))
    repos = g.get("top_repos") or []
    for i, (name, stars, lang) in enumerate(repos[:3]):
        out.append(f'<text x="{rx}" y="{y + 56 + i * 16}" class="mono sm" xml:space="preserve">'
                   f'<tspan class="k">{escape(name)}</tspan>'
                   f'<tspan class="m">{escape(_dotted(name, "", 20)[len(name):])}</tspan>'
                   f'<tspan class="v">{stars}★ {escape(lang)}</tspan></text>')
    if not repos:
        out.append(_t(rx, y + 56, "—", "mono m sm"))

    out.append(_t(rx, y + 112, "ACTIVITY", "mono h"))
    last = ago(g.get("last_push"), card.now) or "—"
    joined = g.get("joined")
    since = f"since {joined} · {card.now.year - joined}y" if joined else "—"
    for i, (k, v) in enumerate((("last push", last), ("on GitHub", since))):
        out.append(f'<text x="{rx}" y="{y + 128 + i * 16}" class="mono sm" xml:space="preserve">'
                   f'<tspan class="k">{escape(k)}</tspan>'
                   f'<tspan class="m">{escape(_dotted(k, "", 12)[len(k):])}</tspan>'
                   f'<tspan class="v">{escape(v)}</tspan></text>')
    return _slide_in("activity", "".join(out), begin)


# --------------------------------------------------------------------- shell

def _defs(p):
    return f"""<defs>
  <linearGradient id="asciiGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{p['g1']}"><animate attributeName="stop-color" values="{p['g1']};{p['g2']};{p['g3']};{p['g1']}" dur="9s" repeatCount="indefinite"/></stop>
    <stop offset="100%" stop-color="{p['g2']}"><animate attributeName="stop-color" values="{p['g2']};{p['g3']};{p['g1']};{p['g2']}" dur="9s" repeatCount="indefinite"/></stop>
  </linearGradient>
  <linearGradient id="borderGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{p['g1']}"/><stop offset="50%" stop-color="{p['g3']}"/>
    <stop offset="100%" stop-color="{p['g2']}"/>
  </linearGradient>
  <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{p['bg0']}"/><stop offset="100%" stop-color="{p['bg1']}"/>
  </linearGradient>
  <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{p['g1']}" stop-opacity="0"/>
    <stop offset="50%" stop-color="{p['g1']}" stop-opacity="0.14"/>
    <stop offset="100%" stop-color="{p['g1']}" stop-opacity="0"/>
  </linearGradient>
  <filter id="glitch" x="-5%" y="-5%" width="110%" height="110%">
    <feTurbulence type="fractalNoise" baseFrequency="0.0001 0.09" numOctaves="1" seed="4" result="noise">
      <animate attributeName="seed" values="4;19;7;23;11;4" keyTimes="0;0.71;0.75;0.8;0.86;1" dur="7s" calcMode="discrete" repeatCount="indefinite"/>
    </feTurbulence>
    <feDisplacementMap in="SourceGraphic" in2="noise" scale="0" xChannelSelector="R" yChannelSelector="G" result="torn">
      <animate attributeName="scale" values="0;0;22;3;14;0;0" keyTimes="0;0.71;0.735;0.76;0.8;0.84;1" dur="7s" repeatCount="indefinite"/>
    </feDisplacementMap>
    <feColorMatrix in="torn" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="red"/>
    <feOffset in="red" dx="0" result="redShift">
      <animate attributeName="dx" values="0;0;-5;3;-4;0;0" keyTimes="0;0.71;0.735;0.76;0.8;0.84;1" dur="7s" repeatCount="indefinite"/>
    </feOffset>
    <feColorMatrix in="torn" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0" result="cyan"/>
    <feBlend in="redShift" in2="cyan" mode="screen"/>
  </filter>
</defs>
<style>
  .mono {{ font-family: {MONO}; }}
  .ascii {{ font-family: {ASCII_FONT}; font-size: {FS_ASCII}px; fill: url(#asciiGrad); }}
  .info {{ font-size: {INFO_FS}px; }}
  .sm {{ font-size: 11px; }}
  .lbl {{ font-size: 9px; letter-spacing: 1.5px; fill: {p['label']}; opacity: 0.75; }}
  .lbl2 {{ font-size: 9px; letter-spacing: 1.2px; }}
  .h {{ font-size: 10px; letter-spacing: 1.2px; fill: {p['accent']}; }}
  .k {{ fill: {p['label']}; }} .v {{ fill: {p['text']}; }} .m {{ fill: {p['muted']}; }}
  .a {{ fill: {p['accent']}; }} .b {{ font-weight: 700; }}
</style>"""


def _crt(canvas_h, p):
    """Power-on: a bright line strikes across the middle, then two shutters retract."""
    half = canvas_h / 2
    spline = 'calcMode="spline" keyTimes="0;1" keySplines="0.5 0 0.7 1"'
    return (
        f'<g id="crt">'
        f'<rect x="0" y="0" width="{W}" height="{half}" fill="{p["bg0"]}">'
        f'<animateTransform attributeName="transform" type="translate" from="0 0" to="0 {-half}" '
        f'dur="0.5s" begin="0.42s" fill="freeze" {spline}/></rect>'
        f'<rect x="0" y="{half}" width="{W}" height="{half}" fill="{p["bg0"]}">'
        f'<animateTransform attributeName="transform" type="translate" from="0 0" to="0 {half}" '
        f'dur="0.5s" begin="0.42s" fill="freeze" {spline}/></rect>'
        f'<rect x="{W / 2}" y="{half - 1}" width="0" height="2" fill="{p["g1"]}" opacity="0">'
        f'<animate attributeName="width" from="0" to="{W}" dur="0.36s" begin="0s" fill="freeze"/>'
        f'<animate attributeName="x" from="{W / 2}" to="0" dur="0.36s" begin="0s" fill="freeze"/>'
        f'<animate attributeName="opacity" values="0;1;0.9;0" keyTimes="0;0.18;0.5;1" dur="0.95s" '
        f'begin="0s" fill="freeze"/></rect>'
        f'<rect width="{W}" height="{canvas_h}" fill="{p["g1"]}" opacity="0">'
        f'<animate attributeName="opacity" values="0;0;0.35;0;0.1;0" keyTimes="0;0.42;0.52;0.62;0.7;1" '
        f'dur="1.15s" begin="0s" fill="freeze"/></rect>'
        f'</g>')


def build_svg(card, palette):
    p = palette
    activity_y = METRICS_Y + METRICS_H + GAP
    canvas_h = activity_y + ACTIVITY_H + GAP
    body = (_title_bar(card, p) + _visual_map(card, p) + _system_info(card, p)
            + _metrics(card, p, METRICS_Y) + _activity(card, p, activity_y))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {canvas_h}" '
        f'width="{W}" height="{canvas_h}" role="img" aria-label="{escape(card.user)} terminal profile card">\n'
        + _defs(p) + "\n"
        + f'<rect width="{W}" height="{canvas_h}" rx="14" fill="url(#bgGrad)"/>\n'
        + f'<g id="card">{body}</g>\n'
        + f'<g style="mix-blend-mode:{p["scanblend"]}" opacity="{p["scanop"]}">'
          f'<rect id="scan" x="0" y="-90" width="{W}" height="90" fill="url(#scanGrad)">'
          f'<animateTransform attributeName="transform" type="translate" from="0 0" to="0 {canvas_h + 90}" '
          f'dur="4.6s" repeatCount="indefinite"/></rect></g>\n'
        + f'<rect x="0.75" y="0.75" width="{W - 1.5}" height="{canvas_h - 1.5}" rx="14" fill="none" '
          f'stroke="url(#borderGrad)" stroke-width="1.5"/>\n'
        + _crt(canvas_h, p) + "\n"
        + "</svg>\n"
    )
