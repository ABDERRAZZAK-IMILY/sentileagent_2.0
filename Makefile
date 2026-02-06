# ============================================
# SentinelAgent Makefile
# ============================================

.PHONY: help setup start stop restart status logs update backup restore reset clean test shell

# Default target
.DEFAULT_GOAL := help

# Colors
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
NC := \033[0m

help: ## Show this help message
	@echo "$(GREEN)SentinelAgent Management Commands$(NC)"
	@echo "=================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}'

setup: ## Initial setup of SentinelAgent
	@echo "$(GREEN)Setting up SentinelAgent...$(NC)"
	@./scripts/setup.sh

start: ## Start all services
	@echo "$(GREEN)Starting services...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)Services started!$(NC)"
	@echo "Dashboard: http://localhost:4200"
	@echo "API: http://localhost:8080"

stop: ## Stop all services
	@echo "$(YELLOW)Stopping services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)Services stopped!$(NC)"

restart: ## Restart all services
	@echo "$(YELLOW)Restarting services...$(NC)"
	@docker-compose restart
	@echo "$(GREEN)Services restarted!$(NC)"

status: ## Show service status
	@docker-compose ps

logs: ## View logs for all services
	@docker-compose logs -f

logs-backend: ## View backend logs
	@docker-compose logs -f backend

logs-frontend: ## View frontend logs
	@docker-compose logs -f frontend

update: ## Update all services to latest version
	@echo "$(GREEN)Updating services...$(NC)"
	@docker-compose pull
	@docker-compose build --no-cache
	@docker-compose up -d
	@echo "$(GREEN)Services updated!$(NC)"

backup: ## Backup database and configuration
	@echo "$(GREEN)Creating backup...$(NC)"
	@./scripts/manage.sh backup

restore: ## Restore from backup (usage: make restore FILE=backup.tar.gz)
	@if [ -z "$(FILE)" ]; then \
		echo "$(YELLOW)Usage: make restore FILE=backup.tar.gz$(NC)"; \
		exit 1; \
	fi
	@./scripts/manage.sh restore $(FILE)

reset: ## Reset all data (WARNING: Destructive!)
	@echo "$(RED)WARNING: This will delete ALL data!$(NC)"
	@./scripts/manage.sh reset

clean: ## Clean up Docker resources
	@echo "$(YELLOW)Cleaning up Docker resources...$(NC)"
	@docker system prune -f
	@echo "$(GREEN)Cleanup completed!$(NC)"

test: ## Run health checks
	@echo "$(GREEN)Running health checks...$(NC)"
	@./scripts/manage.sh test

shell-backend: ## Open shell in backend container
	@docker-compose exec backend /bin/sh

shell-mongodb: ## Open MongoDB shell
	@docker-compose exec mongodb mongosh -u sentinel -p sentinel_password --authenticationDatabase admin sentinelagent

shell-redis: ## Open Redis CLI
	@docker-compose exec redis redis-cli

build: ## Build all Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	@docker-compose build
	@echo "$(GREEN)Build completed!$(NC)"

dev-backend: ## Run backend in development mode
	@cd backend && ./mvnw spring-boot:run -Dspring-boot.run.profiles=local

dev-frontend: ## Run frontend in development mode
	@cd frontend && npm start

dev-agent: ## Run agent in development mode
	@cd agentTopic && go run agent.go

install-backend: ## Install backend dependencies
	@cd backend && ./mvnw clean install -DskipTests

install-frontend: ## Install frontend dependencies
	@cd frontend && npm install

install-agent: ## Install agent dependencies
	@cd agentTopic && go mod download

lint-backend: ## Run backend linting
	@cd backend && ./mvnw checkstyle:check

lint-frontend: ## Run frontend linting
	@cd frontend && npm run lint

test-backend: ## Run backend tests
	@cd backend && ./mvnw test

test-frontend: ## Run frontend tests
	@cd frontend && npm test

# Development shortcuts
dev: dev-backend ## Alias for dev-backend

install: install-backend install-frontend ## Install all dependencies
