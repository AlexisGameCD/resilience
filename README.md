# PROJECT RESILIENCE-ALPHA

Demonstrateur de cyber-resilience a reprise autonome. Une plateforme de paiement fictive
(PayAlpha) conteneurisee encaisse un incident provoque dans un environnement isole, le
detecte par machine learning, le remedie automatiquement, et prouve la reprise par une
nouvelle transaction fictive reussie. Aucune intervention humaine corrective.

> Consortium Workshop2026-M2-Gn. Remplacer `n` par le numero de votre groupe.
> Donnees entierement fictives. Aucune donnee bancaire reelle.

## Les cinq piliers

- DEV : microservices FastAPI (paiement, authentification), moteur de remediation, dashboard React/Tailwind.
- INFRA : Docker Compose, Ansible (via Semaphore), Portainer, observabilite Prometheus / Grafana / Loki.
- IA / DATA : detection d'anomalie par Isolation Forest (sans seuils en dur), assistant RAG local (Ollama + LangChain).
- CYBER : WAF ModSecurity + OWASP CRS, fonction SIEM/SOC, secrets Vault + SOPS, durcissement.
- TRANSFORMATION : EBIOS RM, PCA/PRA, analyse NIS2/DORA (voir le dossier d'ingenierie).

## Prerequis (PC Hote)

- Windows 10/11, droits admin, virtualisation activee.
- Docker Desktop avec WSL2. 16 Go de RAM recommandes.
- Python 3.10+ (pour les scripts de demonstration).
- Facultatif (assistant RAG) : Ollama, avec `ollama pull llama3.1:8b` et `ollama pull nomic-embed-text`.

## Arborescence

```
Workshop2026-M2-Gn/
  docker-compose.yml        orchestration des 16 services
  Makefile                  raccourcis d'exploitation
  .env.example              variables (a copier en .env)
  docs/                     architecture, API, runbook, modele de menaces
  services/                 microservices (payment-api, auth, detection, remediation, assistant, dashboard, web-front)
  infra/                    ansible + observabilite (prometheus, grafana, loki, promtail) + waf + vault
  ml/                       entrainement et modele de detection
  security/                 siem, secrets (vault + sops), durcissement
  attack/                   scenarios d'injection de defaillance controlee
  scripts/                  trafic de reference, transaction de preuve, verification
  tests/                    tests unitaires (modele) et d'integration (plateforme)
```

## Demarrage rapide

```bash
# 1. Preparer l'environnement
make init                 # cree .env depuis l'exemple (adapter les secrets)

# 2. Entrainer le modele de detection (ou utiliser celui fourni dans ml/model/)
make train

# 3. Demarrer toute la plateforme
make up

# 4. Injecter un trafic nominal de reference (etat sain)
make seed

# 5. Verifier la sante de bout en bout
make verify
```

Alternative reproductible via Ansible :

```bash
cd infra/ansible && ansible-playbook playbooks/deploy.yml
```

## Points d'acces

| Interface | URL | Role |
| --- | --- | --- |
| Front paiement | http://localhost:8081 | Initier une transaction fictive |
| Dashboard supervision | http://localhost:8082 | Etat, score, incidents, assistant |
| Grafana | http://localhost:3000 | Metriques et SOC (admin / voir .env) |
| API (via WAF) | http://localhost:8080 | Entree filtree des API |
| Portainer | http://localhost:9000 | Cockpit installe separement, deploie et gere la stack |
| Semaphore | http://localhost:3001 | Automatisation Ansible, historique d'audit |

Deux facons de deployer la stack :

- en ligne de commande : `make up` ;
- via Portainer (recommande ici) : Portainer est installe separement et deploie cette stack
  depuis un depot Git. Procedure complete dans `docs/portainer-semaphore.md`.

Mise en route des cockpits :

```bash
make portainer-init    # initialise l'admin de votre Portainer standalone
make semaphore-boot    # cree le projet et le template d'audit Semaphore
```

## Comptes fictifs

| Identifiant | Mot de passe | Role |
| --- | --- | --- |
| alice | Demo#2026 | user |
| bob | Demo#2026 | user |
| ops | Ops#2026 | operator |

## Derouler la demonstration

```bash
# Etat normal : une transaction reussit, le dashboard est vert
make demo-normal

# Depuis le PC Attaquant, provoquer un incident (au choix)
export GATEWAY_URL="http://<IP_DU_PC_HOTE>:8080"
make attack-load          # saturation controlee -> payment-api_degraded
make attack-malformed     # requetes hostiles -> bloquees par le WAF (SOC)

# Ou, sur le PC Hote, simuler une panne (chaos)
make attack-stop          # arret d'un conteneur -> payment-api_unavailable

# Observer le dashboard : detection (rouge) -> remediation -> reprise (vert)
# Prouver la reprise : une nouvelle transaction fictive aboutit
make demo-normal
```

Le detail de la scene (60 s) est dans `docs/clip-chrono.md` et la checklist de demo dans
`docs/checklist-demo.md`.

## Tests

```bash
pip install -r tests/requirements.txt
pytest tests/test_model.py          # unitaire, hors infrastructure
pytest tests/test_integration.py    # necessite la stack demarree
```

## Securite et perimetre

- Toutes les actions offensives sont limitees a notre SI fictif et a nos machines autorisees.
- Les reseaux du campus, les autres consortiums et les services tiers sont hors perimetre.
- Aucun secret en clair dans l'archive : voir `security/secrets/`.
- Exposition maitrisee : base, secrets, observabilite interne et moteur de remediation ne publient aucun port.

## Limites assumees

Ce depot est un demonstrateur de labo, pas une plateforme de production. Les principales
limites (Vault en mode dev, TLS interne non active, privilege du moteur de remediation,
qualite du modele <= 8B) sont documentees dans `security/hardening/hardening.md` et dans le
dossier d'ingenierie et de gouvernance.
