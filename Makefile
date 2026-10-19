# PROJECT RESILIENCE-ALPHA : raccourcis d'exploitation
# Usage : make <cible>. Voir le README pour le detail.

SHELL := /bin/bash

.PHONY: help init train up down logs ps seed demo-normal verify attack-load attack-malformed attack-stop reset

help:
	@echo "Cibles disponibles :"
	@echo "  init            Copier .env.example vers .env (si absent)"
	@echo "  train           Entrainer le modele de detection d'anomalie"
	@echo "  up              Demarrer toute la plateforme"
	@echo "  down            Arreter la plateforme"
	@echo "  portainer-init  Initialiser l'admin Portainer (cockpit conteneurs)"
	@echo "  semaphore-boot  Bootstrap Semaphore (projet, depot, template d'audit)"
	@echo "  ps              Etat des conteneurs"
	@echo "  logs            Suivre les logs agreges"
	@echo "  seed            Injecter les comptes et le trafic nominal de reference"
	@echo "  demo-normal     Jouer une transaction fictive reussie"
	@echo "  verify          Verifier la sante de bout en bout"
	@echo "  attack-load     Scenario : saturation controlee de l'API"
	@echo "  attack-malformed Scenario : requetes malformees (bloquees par le WAF)"
	@echo "  attack-stop     Scenario : arret d'un conteneur (chaos)"
	@echo "  reset           Tout arreter et purger les volumes (destructif)"

init:
	@test -f .env || (cp .env.example .env && echo ".env cree depuis .env.example : adaptez les secrets.")

train:
	python3 ml/train/train_anomaly.py

portainer-init:
	sh infra/portainer/init.sh

semaphore-boot:
	python3 infra/semaphore/bootstrap.py

up:
	docker compose up -d --build

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=100

seed:
	python3 scripts/seed_traffic.py

demo-normal:
	python3 scripts/new_transaction.py

verify:
	python3 scripts/verify_health.py

attack-load:
	python3 attack/scenarios/load_flood.py

attack-malformed:
	python3 attack/scenarios/malformed_requests.py

attack-stop:
	python3 attack/scenarios/container_stop.py

reset:
	@echo "ATTENTION : action destructrice (suppression des volumes de donnees)."
	@read -p "Confirmer la purge complete ? [tapez OUI] : " c; \
	if [ "$$c" = "OUI" ]; then docker compose down -v; echo "Purge effectuee."; \
	else echo "Annule."; fi
