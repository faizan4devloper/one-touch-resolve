# One Touch Resolve — developer convenience targets.
.PHONY: help install test demo ui synth deploy deploy-agent sync prereqs clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install Python deps + CDK node deps
	pip install -r requirements.txt
	cd infra && npm install

test:  ## Run the unit + integration tests (56)
	python -m pytest -q

demo:  ## Run the full multi-party journey offline (timed simulation)
	SIMULATE_CHANNELS=true python scripts/measure_e2e.py

ui:  ## Start the local UI + API (:8080 phone/API, :8081 dashboard)
	./start.sh

synth:  ## CDK synth (validate the infrastructure)
	cd infra && npx cdk synth >/dev/null && echo "synth OK"

deploy:  ## Deploy the AWS infrastructure via CDK
	cd infra && npx cdk deploy

sync:  ## Regenerate the AgentCore bundled packages from src/
	./scripts/sync_agent_src.sh

deploy-agent: sync  ## Deploy the supervisor to Bedrock AgentCore Runtime
	cd deployment/coeagent && agentcore deploy --yes

prereqs:  ## Validate .env + AWS access (non-destructive)
	./scripts/check_prereqs.sh

clean:  ## Remove build artifacts and caches
	rm -rf infra/cdk.out .sim_output .pytest_cache
	rm -rf deployment/coeagent/app/coe_supervisor/coe_agent \
	       deployment/coeagent/app/coe_supervisor/coe_channels \
	       deployment/coeagent/app/coe_supervisor/coe_shared
	find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete
