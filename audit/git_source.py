"""Git source: clone repos and collect commits for auditing."""

import os
import subprocess
import tempfile
from datetime import datetime
from urllib.parse import urlsplit


def resolve_clone_url(url: str, token_env: str | None = None) -> str:
    scheme = urlsplit(url).scheme
    if scheme not in ("http", "https"):
        raise ValueError(f"not an http(s) URL: {url}")
    host = (urlsplit(url).hostname or "").lower()
    env_name = token_env
    if env_name is None:
        if host == "github.com":
            env_name = "GITHUB_TOKEN"
        elif "gitlab" in host:
            env_name = "GITLAB_TOKEN"
        elif host == "bitbucket.org":
            env_name = "BITBUCKET_TOKEN"
    token = os.environ.get(env_name) if env_name else None
    if token == "":
        raise ValueError(f"env var {env_name} is empty")
    if not token:
        return url
    if host == "github.com":
        prefix = "x-access-token"
    elif host == "bitbucket.org":
        prefix = "x-bitbucket-api-token-auth"
    else:
        prefix = "oauth2"
    rest = url.split("://", 1)[1]
    return f"https://{prefix}:{token}@{rest}"


def _run(args: list[str], cwd: str | None = None) -> bytes:
    return subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE).stdout


def collect_commits(
    repo_url: str,
    since: datetime,
    until: datetime,
    max_diff_bytes: int = 200_000,
    workdir: str | None = None,
    branch: str | None = None,
) -> list[dict]:
    resolved = resolve_clone_url(repo_url)
    tmp_ctx = tempfile.TemporaryDirectory() if workdir is None else None
    repo_dir = workdir or tmp_ctx.name
    clone_cmd = ["git", "clone", "--no-tags"]
    if branch:
        clone_cmd += ["--branch", branch]
    clone_cmd += [resolved, repo_dir]
    try:
        try:
            _run(clone_cmd)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"git clone failed (exit {e.returncode}); check repo URL and token scopes"
            ) from None
        log_out = _run(
            [
                "git", "log", "--pretty=format:%H|%an|%aI|%s",
                f"--since={since.isoformat()}", f"--until={until.isoformat()}",
            ],
            cwd=repo_dir,
        ).decode()
        commits = []
        for line in reversed(log_out.splitlines()):
            hash_, author, date, subject = line.split("|", 3)
            diff = _run(
                ["git", "show", "--format=", "--numstat", "--patch", "--unified=2", hash_],
                cwd=repo_dir,
            )
            if len(diff) > max_diff_bytes:
                diff = diff[:max_diff_bytes] + b"\n... (diff truncated)\n"
            commits.append({
                "hash": hash_[:7],
                "author": author,
                "date": date,
                "message": subject,
                "diff": diff.decode("utf-8", errors="replace"),
            })
        return commits
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()
