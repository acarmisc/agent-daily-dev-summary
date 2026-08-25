"""CLI entry point: python -m audit."""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from audit.llm import DEFAULT_MODEL, run_audit


def md_to_slack(md: str) -> str:
    md = re.sub(r"^#{1,6}\s*(.+?)\s*$", r"*\1*", md, flags=re.M)
    md = re.sub(r"\*\*(.+?)\*\*", r"*\1*", md)
    return md.strip()


def post_slack(webhook: str, text: str) -> None:
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        webhook, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"slack post failed: {resp.status}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="audit")
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--period", choices=["day", "week", "month"], default="day")
    parser.add_argument("--since", type=datetime.fromisoformat)
    parser.add_argument("--until", type=datetime.fromisoformat)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--branch")
    parser.add_argument("--lang", default="english")
    args = parser.parse_args()

    deltas = {"day": timedelta(days=1), "week": timedelta(days=7), "month": timedelta(days=30)}
    delta = deltas[args.period]
    if args.since and args.until:
        since, until = args.since, args.until
    elif args.since:
        since, until = args.since, args.since + delta
    elif args.until:
        since, until = args.until - delta, args.until
    else:
        until = datetime.now(timezone.utc)
        since = until - delta

    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    failures = []
    for repo in args.repo:
        print(f"auditing {repo} ...", file=sys.stderr)
        try:
            report = run_audit(repo, since, until, model_id=args.model, branch=args.branch, lang=args.lang)
            sys.stdout.write(report + "\n")
            if webhook:
                post_slack(
                    webhook,
                    md_to_slack(f"# Audit — {repo}\n_{since:%Y-%m-%d} → {until:%Y-%m-%d}_\n\n{report}"),
                )
        except Exception as e:
            failures.append((repo, e))
            print(f"FAILED {repo}: {e}", file=sys.stderr)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
