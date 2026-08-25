"""LLM audit: chunk commits, call LiteLLM gateway, produce report."""

import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from audit.git_source import collect_commits

DEFAULT_MODEL = "kimi-k2.7-code"
GATEWAY_URL = os.environ.get(
    "LITELLM_BASE_URL", "https://llm-gw.ces.abstractstaging.it/v1/chat/completions"
)
ISSUE_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")
REF_RE = re.compile(r"#(\d{1,6})\b")


def _call(model_id: str, system: str, user: str) -> str:
    api_key = os.environ.get("LITELLM_KEY")
    if not api_key:
        raise RuntimeError("LITELLM_KEY env var is required")
    body = json.dumps({
        "model": model_id,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }).encode()
    req = urllib.request.Request(GATEWAY_URL, data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


def _system_prompt() -> str:
    return (Path(__file__).resolve().parent / "prompts" / "system.md").read_text()


def _render(commit: dict) -> str:
    return f"commit {commit['hash']} by {commit['author']} on {commit['date']}: {commit['message']}\n{commit['diff']}\n"


def chunk_commits(commits: list[dict], max_chars: int = 120_000) -> list[str]:
    chunks: list[str] = []
    current = ""
    for c in commits:
        rendered = _render(c)
        if len(rendered) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(rendered)
        elif len(current) + len(rendered) <= max_chars:
            current += rendered
        else:
            chunks.append(current)
            current = rendered
    if current:
        chunks.append(current)
    return chunks


def origin_refs(commits: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for c in commits:
        keys = ISSUE_RE.findall(c["message"]) or [f"#{n}" for n in REF_RE.findall(c["message"])]
        for k in set(keys):
            counts[k] = counts.get(k, 0) + 1
    return sorted(counts, key=counts.get, reverse=True)


def run_audit(
    repo: str,
    since: datetime,
    until: datetime,
    model_id: str = DEFAULT_MODEL,
    branch: str | None = None,
    lang: str = "english",
) -> str:
    commits = collect_commits(repo, since, until, branch=branch)
    if not commits:
        return "No commits in period."
    chunks = chunk_commits(commits)
    system = _system_prompt()
    header = f"Repository: {repo}\nPeriod: {since:%Y-%m-%d} → {until:%Y-%m-%d}\nReport language: {lang}\n"
    refs = origin_refs(commits)
    if refs:
        header += "Requirement references found in commit messages (origin of the work): " + ", ".join(refs) + "\n"
    if len(chunks) == 1:
        return _call(model_id, system, header + "\n" + chunks[0])
    digests = [
        _call(model_id, system, header + "\n" + chunk + "\nAudit these commits. Follow your output format.")
        for chunk in chunks
    ]
    reduce_prompt = (
        header + "\n" + "---\n".join(digests) + f"\nThese are digests of {len(commits)} commits over the period. "
        "Write the final report. Merge duplicates, re-rank by severity."
    )
    return _call(model_id, system, reduce_prompt)
