import os

from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Get Bedrock model client using IAM credentials.

    Defaults to Amazon Nova Pro (fast, low-cost tool-calling) — the model the
    One Touch Resolve uses. Override with BEDROCK_MODEL_ID.
    """
    return BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
