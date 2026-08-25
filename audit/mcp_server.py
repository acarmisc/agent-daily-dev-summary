"""MCP server exposing the commit audit as a tool (for kagent / any MCP client)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from audit.llm import run_audit

DELTAS = {"day": timedelta(days=1), "week": timedelta(days=7), "month": timedelta(days=30)}

SECRETS_DIR = os.environ.get("AUDIT_SECRETS_DIR")
if SECRETS_DIR and Path(SECRETS_DIR).is_dir():
    for f in Path(SECRETS_DIR).iterdir():
        os.environ.setdefault(f.name, f.read_text().strip())

mcp = MCPServer("commit-audit")


@mcp.tool()
def audit_repo(
    repo: str,
    period: str = "day",
    since: str | None = None,
    until: str | None = None,
    branch: str | None = None,
    lang: str | None = None,
) -> str:
    """Audit commits of a git repo over a period and return an honest markdown report.

    Args:
        repo: https clone URL (github.com uses GITHUB_TOKEN, *gitlab* hosts use GITLAB_TOKEN)
        period: day | week | month
        since: optional ISO date; if set without until, end = since + period
        until: optional ISO date overriding period end
        branch: optional branch name (default branch if omitted)
        lang: report language, e.g. english, italian
    """
    delta = DELTAS[period]
    until_dt = datetime.fromisoformat(until).replace(tzinfo=timezone.utc) if until else datetime.now(timezone.utc)
    since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc) if since else until_dt - delta
    kwargs = {}
    if branch:
        kwargs["branch"] = branch
    if lang:
        kwargs["lang"] = lang
    return run_audit(repo, since_dt, until_dt, **kwargs)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
