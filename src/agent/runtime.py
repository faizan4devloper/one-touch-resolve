"""AgentCore Runtime entrypoint.

This is the container entrypoint deployed to Amazon Bedrock AgentCore Runtime.
It exposes the supervisor agent behind the AgentCore ``@app.entrypoint`` contract.
When the ``bedrock_agentcore`` SDK is unavailable (local/simulation) it falls back
to a plain callable so the module stays importable.
"""

from __future__ import annotations

from typing import Any

try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp  # type: ignore

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        from agent.supervisor import handle_inbound

        return handle_inbound(payload)

    if __name__ == "__main__":
        app.run()

except ImportError:  # local / simulation
    def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        from agent.supervisor import handle_inbound

        return handle_inbound(payload)
