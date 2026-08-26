"""Publish audit reports to a knowledge repo via the GitLab commits API.

The knowledge repo's own CI (S3 sync + Bedrock ingestion) picks the file up
from there — this module only writes markdown, nothing else.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


def report_filename(year: int, week: int) -> str:
    return f"dev-log-{year}-W{week:02d}.md"


def build_commit_body(
    existing: str | None, file_path: str, content: str, message: str
) -> dict:
    """Commit body appending `content` to an existing weekly file (or creating it)."""
    if existing is not None and existing.strip():
        content = existing.rstrip() + "\n\n---\n\n" + content
    return {
        "branch": None,  # filled by caller
        "commit_message": message,
        "actions": [
            {
                "action": "update" if existing is not None else "create",
                "file_path": file_path,
                "content": content,
            }
        ],
    }


class KnowledgePublisher:
    """Minimal GitLab API client scoped to one knowledge project."""

    def __init__(
        self,
        base_url: str,
        token: str,
        project: str,
        prefix: str = "mds",
        branch: str = "main",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project_enc = urllib.parse.quote(project, safe="")
        self.prefix = prefix.strip("/")
        self.branch = branch

    def _request(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            f"{self.base_url}/api/v4{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "PRIVATE-TOKEN": self.token,
                "Content-Type": "application/json",
            },
            method=method,
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else {}

    def _raw_file(self, file_path: str) -> str | None:
        enc = urllib.parse.quote(file_path, safe="")
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/v4/projects/{self.project_enc}"
                f"/repository/files/{enc}/raw?ref={urllib.parse.quote(self.branch)}",
                headers={"PRIVATE-TOKEN": self.token},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def publish(self, filename: str, content: str, message: str) -> dict:
        file_path = f"{self.prefix}/{filename}" if self.prefix else filename
        existing = self._raw_file(file_path)
        body = build_commit_body(existing, file_path, content, message)
        body["branch"] = self.branch
        body["start_branch"] = self.branch
        result = self._request(
            "POST", f"/projects/{self.project_enc}/repository/commits", body
        )
        return {
            "file_path": file_path,
            "action": body["actions"][0]["action"],
            "commit_web_url": (result.get("commit_web_url") or ""),
        }


def publisher_from_env() -> tuple[KnowledgePublisher | None, list[str]]:
    """Build a publisher from KB_* env vars; returns (publisher, missing)."""
    missing = []
    project = os.environ.get("KB_GITLAB_PROJECT", "").strip()
    if not project:
        missing.append("KB_GITLAB_PROJECT")
        return None, missing
    token_env = os.environ.get("KB_GITLAB_TOKEN_ENV", "GITLAB_TOKEN")
    token = os.environ.get(token_env, "").strip()
    if not token:
        missing.append(token_env)
        return None, missing
    base_url = os.environ.get(
        "KB_GITLAB_URL", os.environ.get("GITLAB_URL", "https://gitlab.com")
    ).rstrip("/")
    return (
        KnowledgePublisher(
            base_url,
            token,
            project,
            prefix=os.environ.get("KB_PREFIX", "mds"),
            branch=os.environ.get("KB_BRANCH", "main"),
        ),
        [],
    )
