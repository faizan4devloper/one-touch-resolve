# Container image for the One Touch Resolve supervisor agent,
# deployed to Amazon Bedrock AgentCore Runtime.
FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SIMULATE_CHANNELS=false

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code (agent + channels + shared model).
COPY agent/ ./agent/
COPY channels/ ./channels/
COPY shared/ ./shared/

# AgentCore Runtime invokes the entrypoint exposed in agent/runtime.py.
EXPOSE 8080
CMD ["python", "-m", "agent.runtime"]
