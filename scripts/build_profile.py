"""Generate dark.svg and light.svg — the animated terminal profile card.

Usage (from the repo root):
    py scripts/build_profile.py

Edit INFO / PALETTES below and re-run. Never edit the generated .svg files by hand.
Optional env: GH_PAT (includes private repos), GITHUB_TOKEN, WAKATIME_API_KEY.
Requires: Pillow  ->  py -m pip install pillow
"""
import datetime
import os

from profilecard.data import (compute_streaks, fetch_calendar, fetch_github, fetch_wakatime,
                              uptime_days)
from profilecard.palettes import DARK, LIGHT
from profilecard.portrait import portrait_ascii
from profilecard.render import Card, build_svg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTRAIT = os.path.join(ROOT, "assets", "portrait.png")

USER = "WalberFellipe"
HANDLE = "walber@dev"
CODING_SINCE = datetime.date(2020, 2, 1)
JOINED_YEAR = 2019

INFO = [
    ("Subject", "Walber Fellipe"),
    ("Role", "Full-stack Developer / AI Engineer"),
    ("Origin", "Araxá - MG, Brazil"),
    ("Status", "Building • Learning • Shipping"),
    ("Currently", "Diagonal Social · Studying AI Engineering"),
    ("ToolChain", "VS Code, IntelliJ, Git, Docker"),
    ("Core Lang", "TypeScript, Python, PHP, Kotlin"),
    ("Core Frontend", "React, Next"),
    ("Core Backend", "Node.js, Nest, Express, Fastify, FastAPI"),
    ("Core Mobile", "React Native, Flutter"),
    ("Core Database", "PostgreSQL, MongoDB, SQLite, Redis"),
    ("Core ORM/BaaS", "Prisma, Drizzle, Supabase, Firebase"),
    ("Core Cloud", "AWS (S3, Cognito), Google Cloud, BigQuery"),
    ("Core AI", "LLM, RAG, MCP, TensorFlow.js"),
    ("Integrations", "Stripe, Pusher, Magento"),
    ("— Contact", ""),
    ("Mail", "walberfellipe18@gmail.com"),
    ("Portfolio", "walberfellipe.com.br"),
    ("LinkedIn", "walber-fellipe"),
    ("Github", "WalberFellipe"),
]

PALETTES = {"dark": DARK, "light": LIGHT}


def main(out_dir=ROOT, today=None):
    today = today or datetime.date.today()
    pat = os.environ.get("GH_PAT")
    token = pat or os.environ.get("GITHUB_TOKEN")

    calendar = fetch_calendar(USER, token, JOINED_YEAR, today)
    card = Card(
        info=INFO,
        user=HANDLE,
        uptime_days=uptime_days(CODING_SINCE, today),
        ascii_rows=portrait_ascii(PORTRAIT),
        streaks=compute_streaks(calendar, today) if calendar else None,
        github=fetch_github(USER, token, private=bool(pat)),
        wakatime=fetch_wakatime(os.environ.get("WAKATIME_API_KEY")),
        calendar=calendar,
        sync_date=today.isoformat(),
        now=datetime.datetime.now(datetime.timezone.utc),
    )

    paths = []
    for theme, palette in PALETTES.items():
        path = os.path.join(out_dir, f"{theme}.svg")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(build_svg(card, palette))
        print(f"wrote {theme}.svg  (ascii rows={len(card.ascii_rows)})")
        paths.append(path)
    return paths


if __name__ == "__main__":
    main()
