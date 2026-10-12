"""Build-time data: GitHub / WakaTime fetchers and the metric math on top of them.

Every fetcher returns None on failure so the card still builds offline or when an
API hiccups; the renderer shows "—" for whatever is missing.
"""
import base64
import collections
import datetime
import json
import urllib.request

API = "https://api.github.com"


def _get_json(url, token, body=None, auth_header=None):
    headers = {"User-Agent": "profile-card", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if auth_header:
        headers["Authorization"] = auth_header
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# ---------------------------------------------------------------- metric math

def compute_streaks(days, today):
    counts = dict(days)
    total = sum(counts.values())

    longest = run = 0
    prev = None
    for day in sorted(counts):
        if counts[day] > 0 and prev is not None and day - prev == datetime.timedelta(1):
            run += 1
        elif counts[day] > 0:
            run = 1
        else:
            run = 0
        longest = max(longest, run)
        prev = day

    # today usually has no contributions yet when CI runs, so it doesn't break the streak
    day = today if counts.get(today, 0) > 0 else today - datetime.timedelta(1)
    current = 0
    while counts.get(day, 0) > 0:
        current += 1
        day -= datetime.timedelta(1)
    return {"total": total, "current": current, "longest": longest}


def fmt_num(n):
    return "—" if n is None else f"{n:,}"


def ago(iso, now):
    try:
        t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    s = (now - t).total_seconds()
    if s < 3600:
        return f"{int(s // 60)}m ago"
    if s < 86400:
        return f"{int(s // 3600)}h ago"
    return f"{int(s // 86400)}d ago"


def uptime_days(since, today):
    return (today - since).days


# ------------------------------------------------------------------- fetchers

_CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def fetch_calendar(user, token, since_year, today):
    if not token:
        return None
    try:
        counts = {}
        for year in range(since_year, today.year + 1):
            end = min(datetime.date(year, 12, 31), today)
            variables = {"login": user, "from": f"{year}-01-01T00:00:00Z",
                         "to": f"{end.isoformat()}T23:59:59Z"}
            res = _get_json(f"{API}/graphql", token,
                            body={"query": _CALENDAR_QUERY, "variables": variables})
            if res.get("errors"):
                return None
            weeks = (res["data"]["user"]["contributionsCollection"]
                     ["contributionCalendar"]["weeks"])
            for week in weeks:
                for d in week["contributionDays"]:
                    counts[datetime.date.fromisoformat(d["date"])] = d["contributionCount"]
        return sorted(counts.items())
    except Exception:
        return None


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def fetch_github(user, token, private):
    try:
        prof = _get_json(f"{API}/users/{user}", token)
    except Exception:
        return None

    repos = []
    try:
        for page in range(1, 5):
            if private:
                url = f"{API}/user/repos?per_page=100&page={page}&affiliation=owner&visibility=all"
            else:
                url = f"{API}/users/{user}/repos?per_page=100&page={page}&type=owner"
            batch = _get_json(url, token)
            repos += batch
            if len(batch) < 100:
                break
        own = [r for r in repos if not r.get("fork")]
    except Exception:
        own = None

    stars = forks = top_repos = last_push = None
    langs = []
    if own is not None:
        stars = sum(r.get("stargazers_count", 0) for r in own)
        forks = sum(r.get("forks_count", 0) for r in own)
        showcase = [r for r in own if r["name"].lower() != user.lower()]  # not the profile repo
        ranked = sorted(showcase, key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at") or ""),
                        reverse=True)
        top_repos = [(r["name"][:17], r.get("stargazers_count", 0), r.get("language") or "")
                     for r in ranked[:3]]
        pushes = [r["pushed_at"] for r in own if r.get("pushed_at")]
        last_push = max(pushes) if pushes else None

        by = collections.Counter()
        if token:  # by code bytes, capped to the most recently pushed repos
            recent = sorted(own, key=lambda r: r.get("pushed_at") or "", reverse=True)[:80]
            for r in recent:
                got = _try(lambda: _get_json(f"{API}/repos/{r['full_name']}/languages", token))
                if got:
                    by.update(got)
                elif r.get("language"):
                    by[r["language"]] += 1
        else:  # one primary language per repo, no extra requests
            by.update(r["language"] for r in own if r.get("language"))
        total = sum(by.values())
        if total:
            langs = [(name, round(n / total * 100)) for name, n in by.most_common(5)]

    def search_count(kind):
        return _get_json(f"{API}/search/issues?q=author:{user}+type:{kind}&per_page=1",
                         token)["total_count"]

    created = prof.get("created_at") or ""
    return {
        "followers": prof.get("followers"),
        "following": prof.get("following"),
        "repos": len(own) if private and own is not None else prof.get("public_repos"),
        "stars": stars,
        "forks": forks,
        "prs": _try(lambda: search_count("pr")),
        "issues": _try(lambda: search_count("issue")),
        "langs": langs,
        "top_repos": top_repos,
        "last_push": last_push,
        "joined": int(created[:4]) if created[:4].isdigit() else None,
    }


_WAKATIME_RANGES = [("all_time", "ALL TIME"), ("last_year", "LAST YEAR"),
                    ("last_30_days", "LAST 30 DAYS"), ("last_7_days", "LAST 7 DAYS")]


def fetch_wakatime(key):
    if not key:
        return None
    auth = "Basic " + base64.b64encode(key.encode()).decode()
    for rng, label in _WAKATIME_RANGES:
        try:
            stats = _get_json(f"https://wakatime.com/api/v1/users/current/stats/{rng}",
                              None, auth_header=auth)["data"]
        except Exception:
            continue
        langs = [(l["name"], f"{int(l.get('hours', 0))}h{int(l.get('minutes', 0)):02d}m")
                 for l in stats.get("languages", []) if l["name"].lower() != "other"][:5]
        if not langs:
            continue
        return {"range": label, "langs": langs,
                "total": stats.get("human_readable_total", ""),
                "daily_avg": stats.get("human_readable_daily_average", "")}
    return None
