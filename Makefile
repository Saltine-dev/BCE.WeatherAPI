# Weather API Makefile
.PHONY: help install test deploy clean local-setup local-start package

# Variables
ENVIRONMENT ?= dev
PYTHON := python3
AWS_REGION ?= us-east-1
STACK_NAME := weather-aggregator-$(ENVIRONMENT)

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Weather API Makefile$(NC)"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables:"
	@echo "  ENVIRONMENT=$(ENVIRONMENT) (current)"
	@echo "  AWS_REGION=$(AWS_REGION) (current)"

install: ## Install all dependencies
	@echo "$(BLUE)Installing dependencies...$(NC)"
	$(PYTHON) -m pip install --upgrade pip
	pip install -r requirements-dev.txt
	cd src/lambdas/weather_collector && pip install -r requirements.txt
	cd src/lambdas/weather_api && pip install -r requirements.txt
	@echo "$(GREEN)Dependencies installed successfully!$(NC)"

test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	pytest tests/unit/ -v --cov=src --cov-report=term-missing
	@echo "$(GREEN)Tests completed!$(NC)"

test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	pytest tests/integration/ -v
	@echo "$(GREEN)Integration tests completed!$(NC)"

lint: ## Run code linting
	@echo "$(BLUE)Running linters...$(NC)"
	flake8 src/ tests/ --max-line-length=120 --ignore=E203,W503
	black --check src/ tests/
	mypy src/ --ignore-missing-imports
	@echo "$(GREEN)Linting completed!$(NC)"

format: ## Format code with black
	@echo "$(BLUE)Formatting code...$(NC)"
	black src/ tests/
	@echo "$(GREEN)Code formatted!$(NC)"

package: ## Package Lambda functions
	@echo "$(BLUE)Packaging Lambda functions...$(NC)"
	rm -rf build
	mkdir -p build/lambdas
	
	@echo "Packaging Weather Collector..."
	cd src/lambdas/weather_collector && \
		pip install -r requirements.txt -t temp/ && \
		cp *.py temp/ && \
		cd temp && zip -r ../../../../build/lambdas/weather-collector.zip . && \
		cd .. && rm -rf temp
	
	@echo "Packaging Weather API..."
	cd src/lambdas/weather_api && \
		pip install -r requirements.txt -t temp/ && \
		cp *.py temp/ && \
		cd temp && zip -r ../../../../build/lambdas/weather-api.zip . && \
		cd .. && rm -rf temp
	
	@echo "$(GREEN)Lambda functions packaged!$(NC)"

deploy: package ## Deploy to AWS
	@echo "$(BLUE)Deploying to $(ENVIRONMENT) environment...$(NC)"
	chmod +x scripts/deploy.sh
	./scripts/deploy.sh $(ENVIRONMENT)
	@echo "$(GREEN)Deployment completed!$(NC)"

deploy-ci: ## Deploy using GitHub Actions (push to main)
	@echo "$(BLUE)Triggering CI/CD deployment...$(NC)"
	git add .
	git commit -m "Deploy to $(ENVIRONMENT)"
	git push origin main
	@echo "$(GREEN)CI/CD deployment triggered!$(NC)"

local-setup: ## Set up local development environment
	@echo "$(BLUE)Setting up local development...$(NC)"
	chmod +x scripts/local-dev.sh
	./scripts/local-dev.sh setup
	@echo "$(GREEN)Local setup completed!$(NC)"

local-start: ## Start local API server
	@echo "$(BLUE)Starting local API server...$(NC)"
	./scripts/local-dev.sh start

local-test: ## Test local API endpoints
	@echo "$(BLUE)Testing local API endpoints...$(NC)"
	./scripts/local-dev.sh test

local-invoke: ## Invoke weather collector locally
	@echo "$(BLUE)Invoking weather collector locally...$(NC)"
	./scripts/local-dev.sh invoke

local-stop: ## Stop local services
	@echo "$(BLUE)Stopping local services...$(NC)"
	./scripts/local-dev.sh stop
	@echo "$(GREEN)Local services stopped!$(NC)"

update-secrets: ## Update API keys in AWS Secrets Manager
	@echo "$(BLUE)Updating API keys in Secrets Manager...$(NC)"
	@if [ ! -f config/api-keys.json ]; then \
		echo "$(RED)Error: config/api-keys.json not found!$(NC)"; \
		echo "Copy config/api-keys.template.json to config/api-keys.json and add your keys"; \
		exit 1; \
	fi
	aws secretsmanager update-secret \
		--secret-id $(STACK_NAME)-api-keys \
		--secret-string file://config/api-keys.json \
		--region $(AWS_REGION)
	@echo "$(GREEN)API keys updated!$(NC)"

logs-collector: ## View weather collector logs
	@echo "$(BLUE)Viewing weather collector logs...$(NC)"
	aws logs tail /aws/lambda/$(STACK_NAME)-collector --follow --region $(AWS_REGION)

logs-api: ## View API logs
	@echo "$(BLUE)Viewing API logs...$(NC)"
	aws logs tail /aws/lambda/$(STACK_NAME)-api --follow --region $(AWS_REGION)

invoke-collector: ## Manually invoke weather collector
	@echo "$(BLUE)Invoking weather collector...$(NC)"
	aws lambda invoke \
		--function-name $(STACK_NAME)-collector \
		--invocation-type Event \
		--region $(AWS_REGION) \
		output.json
	@echo "$(GREEN)Weather collector invoked!$(NC)"

test-api: ## Test deployed API endpoints
	@echo "$(BLUE)Testing deployed API endpoints...$(NC)"
	@API_ENDPOINT=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
		--output text \
		--region $(AWS_REGION)); \
	echo "API Endpoint: $$API_ENDPOINT"; \
	echo ""; \
	echo "Testing /health:"; \
	curl -s $$API_ENDPOINT/health | python3 -m json.tool; \
	echo ""; \
	echo "Testing /weather/sources:"; \
	curl -s $$API_ENDPOINT/weather/sources | python3 -m json.tool | head -20

status: ## Check deployment status
	@echo "$(BLUE)Checking deployment status...$(NC)"
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query "Stacks[0].{Status:StackStatus,Timestamp:LastUpdatedTime}" \
		--output table \
		--region $(AWS_REGION) 2>/dev/null || echo "$(RED)Stack not found$(NC)"
	@echo ""
	@API_ENDPOINT=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
		--output text \
		--region $(AWS_REGION) 2>/dev/null); \
	if [ ! -z "$$API_ENDPOINT" ]; then \
		echo "API Health Check:"; \
		curl -s $$API_ENDPOINT/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'  Status: {data.get(\"status\", \"unknown\")}'); print(f'  Last Update: {data.get(\"data\", {}).get(\"last_update\", \"N/A\")}')"; \
	fi

metrics: ## View CloudWatch metrics
	@echo "$(BLUE)Fetching CloudWatch metrics...$(NC)"
	@echo "Lambda Invocations (last 24h):"
	@aws cloudwatch get-metric-statistics \
		--namespace AWS/Lambda \
		--metric-name Invocations \
		--dimensions Name=FunctionName,Value=$(STACK_NAME)-collector \
		--start-time $$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
		--end-time $$(date -u +%Y-%m-%dT%H:%M:%S) \
		--period 3600 \
		--statistics Sum \
		--region $(AWS_REGION) \
		--query "Datapoints[*].[Timestamp,Sum]" \
		--output table

clean: ## Clean build artifacts
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	rm -rf build/
	rm -rf .aws-sam/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -f output.json
	rm -f template-local.yaml
	rm -f .env.local
	@echo "$(GREEN)Cleanup completed!$(NC)"

destroy: ## Destroy AWS infrastructure
	@echo "$(RED)WARNING: This will delete all AWS resources!$(NC)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(BLUE)Deleting CloudFormation stack...$(NC)"; \
		aws cloudformation delete-stack --stack-name $(STACK_NAME) --region $(AWS_REGION); \
		echo "$(YELLOW)Stack deletion initiated. Use 'make status' to check progress.$(NC)"; \
	else \
		echo "$(GREEN)Destruction cancelled.$(NC)"; \
	fi

.DEFAULT_GOAL := help
