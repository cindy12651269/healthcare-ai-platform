.PHONY: up down restart logs ps build clean
# Project Settings
PROJECT_NAME=healthcare-ai-platform
COMPOSE=docker-compose

# Core Commands

## Build all services
build:
	$(COMPOSE) build

## Start all services (API + Postgres + Redis)
up:
	$(COMPOSE) up -d --build

## Stop all services
down:
	$(COMPOSE) down

## Restart all services
restart:
	$(COMPOSE) down
	$(COMPOSE) up -d --build

## Show running services
ps:
	$(COMPOSE) ps

## Show API logs
logs:
	$(COMPOSE) logs -f api

## Clean all containers, networks, and volumes (DANGEROUS)
clean:
	$(COMPOSE) down -v --remove-orphans
