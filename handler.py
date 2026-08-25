"""AWS Bedrock AgentCore Runtime entrypoint (optional extra)."""

from datetime import datetime, timedelta, timezone

from audit.llm import run_audit

DELTAS = {"day": timedelta(days=1), "week": timedelta(days=7), "month": timedelta(days=30)}


def audit(payload: dict) -> dict:
    repo = payload["repo"]
    until = datetime.now(timezone.utc)
    since = until - DELTAS[payload.get("period", "day")]
    model = payload.get("model")
    kwargs = {k: v for k in ("branch", "lang") if (v := payload.get(k))}
    report = (
        run_audit(repo, since, until, **kwargs)
        if not model
        else run_audit(repo, since, until, model_id=model, **kwargs)
    )
    return {"report": report}


try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict) -> dict:
        return audit(payload)
except ImportError:
    app = None
