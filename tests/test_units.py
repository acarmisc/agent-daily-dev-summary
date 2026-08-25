import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit.git_source import resolve_clone_url
from audit.llm import chunk_commits, origin_refs


class TestOriginRefs(unittest.TestCase):
    @staticmethod
    def _commit(msg):
        return {"hash": "abc1234", "author": "a", "date": "d", "message": msg, "diff": ""}

    def test_jira_keys(self):
        refs = origin_refs([self._commit("fix PROJ-12 bug"), self._commit("PROJ-12 follow-up"), self._commit("misc")])
        self.assertEqual(refs, ["PROJ-12"])

    def test_issue_ref_fallback(self):
        refs = origin_refs([self._commit("improve x (#42)"), self._commit("revert (#42)")])
        self.assertEqual(refs, ["#42"])

    def test_none_found(self):
        self.assertEqual(origin_refs([self._commit("no refs here")]), [])


class TestResolveCloneUrl(unittest.TestCase):
    def test_github_token(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "t1"}):
            self.assertEqual(
                resolve_clone_url("https://github.com/org/repo.git"),
                "https://x-access-token:t1@github.com/org/repo.git",
            )

    def test_gitlab_token(self):
        with mock.patch.dict(os.environ, {"GITLAB_TOKEN": "t2"}):
            self.assertEqual(
                resolve_clone_url("https://gitlab.com/org/repo.git"),
                "https://oauth2:t2@gitlab.com/org/repo.git",
            )

    def test_public_passthrough(self):
        self.assertEqual(resolve_clone_url("https://example.com/repo.git"), "https://example.com/repo.git")

    def test_empty_token_raises(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
            with self.assertRaises(ValueError):
                resolve_clone_url("https://github.com/org/repo.git")

    def test_non_https_raises(self):
        with self.assertRaises(ValueError):
            resolve_clone_url("ftp://example.com/repo.git")


class TestChunkCommits(unittest.TestCase):
    @staticmethod
    def _commit(n=1, diff="x"):
        return {"hash": f"abc{n}def", "author": "a", "date": "2026-01-01", "message": "m", "diff": diff}

    def test_empty(self):
        self.assertEqual(chunk_commits([]), [])

    def test_small_single_chunk(self):
        chunks = chunk_commits([self._commit(), self._commit(2)])
        self.assertEqual(len(chunks), 1)

    def test_oversized_own_chunk(self):
        big = self._commit(diff="y" * 200)
        chunks = chunk_commits([big], max_chars=100)
        self.assertEqual(chunks, ["commit abc1def by a on 2026-01-01: m\n" + "y" * 200 + "\n"])

    def test_split_by_size(self):
        commits = [self._commit(i) for i in range(5)]
        chunks = chunk_commits(commits, max_chars=150)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(sum(c.count("commit ") for c in chunks), 5)


if __name__ == "__main__":
    unittest.main()
