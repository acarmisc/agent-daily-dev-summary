"""CLI entry point: python -m audit."""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from audit.llm import DEFAULT_MODEL, run_audit


def main() -> None:
    parser = argparse.ArgumentParser(prog="audit")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--period", choices=["day", "week", "month"], default="day")
    parser.add_argument("--since", type=datetime.fromisoformat)
    parser.add_argument("--until", type=datetime.fromisoformat)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--branch")
    parser.add_argument("--lang", default="english")
    parser.add_argument("--out")
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

    report = run_audit(args.repo, since, until, model_id=args.model, branch=args.branch, lang=args.lang)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
    else:
        sys.stdout.write(report + "\n")


if __name__ == "__main__":
    main()
