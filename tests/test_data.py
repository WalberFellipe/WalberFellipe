import contextlib
import datetime
import io
import unittest
from unittest import mock

import tests._path  # noqa: F401

from profilecard.data import (ago, compute_streaks, fetch_calendar, fetch_github,
                              fetch_wakatime, fmt_num, uptime_days)

D = datetime.date


def series(start, counts):
    return [(start + datetime.timedelta(i), c) for i, c in enumerate(counts)]


class MetricMathTest(unittest.TestCase):
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
        self.assertEqual(fmt_num(15698), "15,698")
        self.assertEqual(fmt_num(None), "—")

    def test_ago(self):
        now = datetime.datetime(2026, 10, 11, 12, tzinfo=datetime.timezone.utc)
        self.assertEqual(ago("2026-10-10T13:00:00Z", now), "23h ago")
        self.assertEqual(ago("2026-10-01T12:00:00Z", now), "10d ago")
        self.assertEqual(ago("garbage", now), "")

    def test_uptime(self):
        self.assertEqual(uptime_days(D(2020, 2, 1), D(2026, 10, 11)), 2444)


class FetcherTest(unittest.TestCase):
    def setUp(self):
        # fetchers warn on stderr when they swallow a failure; keep test output clean
        quiet = contextlib.redirect_stderr(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

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
            if "/search/" in url:
                raise OSError("rate limited")
            if url.endswith("/users/u"):
                return {"followers": 10, "following": 3, "public_repos": 2,
                        "created_at": "2019-06-03T00:00:00Z"}
            if "/repos?" in url:
                return [{"name": "a", "full_name": "u/a", "fork": False, "stargazers_count": 2,
                         "forks_count": 1, "language": "TypeScript",
                         "pushed_at": "2026-10-10T00:00:00Z"}]
            if url.endswith("/languages"):
                return {"TypeScript": 300, "Python": 100}
            return []

        with mock.patch("profilecard.data._get_json", side_effect=fake):
            g = fetch_github("u", "t", private=False)
        self.assertEqual((g["stars"], g["forks"], g["followers"]), (2, 1, 10))
        self.assertIsNone(g["prs"])
        self.assertEqual(g["langs"], [("TypeScript", 75), ("Python", 25)])

    def test_private_repos_count_but_are_never_named(self):
        # GH_PAT mode sees private repos: they feed the totals, never the public top list
        repos = [{"name": "secret-client-app", "full_name": "u/secret-client-app", "fork": False,
                  "private": True, "stargazers_count": 5, "forks_count": 0, "language": "PHP",
                  "pushed_at": "2026-10-11T00:00:00Z"},
                 {"name": "open", "full_name": "u/open", "fork": False, "private": False,
                  "stargazers_count": 1, "forks_count": 0, "language": "TypeScript",
                  "pushed_at": "2026-10-01T00:00:00Z"}]

        def fake(url, token, body=None):
            if url.endswith("/users/u"):
                return {"followers": 1, "following": 1, "public_repos": 1, "created_at": ""}
            if "/repos?" in url:
                return repos
            raise OSError

        with mock.patch("profilecard.data._get_json", side_effect=fake):
            g = fetch_github("u", "pat", private=True)
        self.assertEqual([r[0] for r in g["top_repos"]], ["open"])
        self.assertEqual(g["stars"], 6)

    def test_swallowed_failures_are_logged(self):
        err = io.StringIO()
        with mock.patch("profilecard.data._get_json", side_effect=OSError("HTTP 401")), \
                contextlib.redirect_stderr(err):
            fetch_calendar("u", "t", 2019, D(2026, 10, 11))
            fetch_github("u", "t", private=False)
        self.assertIn("calendar", err.getvalue())
        self.assertIn("HTTP 401", err.getvalue())

    def test_top_repos_skip_profile_repo(self):
        repos = [{"name": n, "full_name": f"u/{n}", "fork": False, "stargazers_count": 0,
                  "forks_count": 0, "language": None, "pushed_at": p}
                 for n, p in [("u", "2026-10-11T00:00:00Z"), ("b", "2026-10-01T00:00:00Z")]]

        def fake(url, token, body=None):
            if url.endswith("/users/u"):
                return {"followers": 1, "following": 1, "public_repos": 2, "created_at": ""}
            if "/repos?" in url:
                return repos
            raise OSError

        with mock.patch("profilecard.data._get_json", side_effect=fake):
            g = fetch_github("u", None, private=False)
        self.assertEqual([r[0] for r in g["top_repos"]], ["b"])


if __name__ == "__main__":
    unittest.main()
