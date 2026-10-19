# PROJECT RESILIENCE-ALPHA : architecture de la plateforme

> Consortium Workshop2026-M2-Gn. Document technique de référence.
> Plateforme de paiement fictive "PayAlpha" et chaîne de cyber-résilience à reprise autonome.

## 1. Principe directeur

La plateforme doit démontrer une chaîne complète : un service métier critique (paiement
fictif) subit un incident de sécurité provoqué dans un environnement isolé, l'anomalie est
identifiée par un modèle de machine learning (et non par de simples seuils fixes), une
décision de remédiation est prise puis exécutée automatiquement, et le retour à un état
utilisable est prouvé par une nouvelle transaction fictive réussie. Aucune intervention
humaine corrective pendant la séquence.

Les cinq piliers du sujet sont présents et interconnectés :

| Pilier | Composants livrés | Rôle dans la chaîne |
| --- | --- | --- |
| DEV | payment-api, auth-service, web-front, remediation-service, dashboard | Fait vivre le métier et pilote la reprise |
| INFRA | Docker Compose, Ansible, Semaphore, Portainer, Prometheus, Grafana, Loki | Déploie, observe, rétablit de façon reproductible |
| IA / DATA | detection-service (ML), assistant-service (RAG local) | Identifie l'anomalie, assiste l'opérateur |
| CYBER | WAF ModSecurity, fonction SIEM, Vault + SOPS, durcissement | Éprouve et protège la plateforme |
| TRANSFORMATION | EBIOS RM, PCA/PRA, analyse NIS2/DORA | Justifie les choix et cadre la résilience |

## 2. Vue d'ensemble des composants

```mermaid
flowchart TB
    subgraph attaquant["PC Attaquant (réseau du groupe)"]
        ATK["Scénarios d'injection de défaillance\n(saturation, requêtes malformées, arrêt conteneur)"]
    end

    subgraph hote["PC Hote : plateforme conteneurisee"]
        direction TB
        subgraph ingress["Zone exposee (publiee avec discernement)"]
            WAF["WAF ModSecurity + OWASP CRS\n:8080"]
            FRONT["web-front (UI paiement)\n:8081"]
            DASH["dashboard supervision React/Tailwind\n:8082"]
            GRAF["Grafana\n:3000"]
        end

        subgraph metier["Zone metier (interne, non exposee)"]
            AUTH["auth-service (JWT)"]
            API["payment-api"]
            DB[("PostgreSQL\ncomptes, transactions")]
        end

        subgraph resilience["Zone resilience (interne)"]
            DET["detection-service\nML anomalie"]
            REM["remediation-service\nmoteur de reprise"]
            PORT["Portainer (hors stack)\ncockpit + API, deploie la stack"]
            SEMA["Semaphore\nAnsible + audit"]
        end

        subgraph obs["Observabilite (interne)"]
            PROM["Prometheus"]
            LOKI["Loki + Promtail"]
            CAD["cAdvisor / node-exporter"]
        end

        subgraph secu["Secrets"]
            VAULT["Vault (secrets runtime)"]
        end

        subgraph ia["IA locale (PC IA facultatif)"]
            ASSIST["assistant-service RAG\nLangChain + Chroma"]
            OLLAMA["Ollama (modele <= 8B)"]
        end
    end

    ATK -->|trafic HTTP| WAF
    ATK -.->|chaos: stop conteneur| API
    FRONT -->|/api| WAF
    WAF --> API
    WAF --> AUTH
    API --> AUTH
    API --> DB
    API -->|/metrics| PROM
    AUTH -->|/metrics| PROM
    WAF -->|/metrics| PROM
    CAD --> PROM
    API -->|logs| LOKI
    WAF -->|logs journalises| LOKI
    PROM --> DET
    LOKI --> DET
    DET -->|alerte scoree| REM
    REM -->|chemin rapide: restart| PORT
    PORT -->|API Docker| API
    REM -->|chemin audite: tache Ansible| SEMA
    SEMA -->|verification HTTP| WAF
    REM -->|etat incident| DASH
    PROM --> GRAF
    LOKI --> GRAF
    DET --> DASH
    API --> VAULT
    AUTH --> VAULT
    ASSIST --> OLLAMA
    ASSIST -->|lecture seule| LOKI
    DASH --> ASSIST
```

Les interfaces internes (base de données, Prometheus, Loki, Vault, moteur de remédiation)
ne sont pas publiées sur le réseau du groupe. Le WAF, le front de paiement, le dashboard de
supervision et Grafana exposent un port. Les cockpits d'exploitation Portainer et Semaphore
exposent aussi une interface d'administration : elles sont protégées par authentification,
restent cantonnées au réseau du groupe, et la remédiation les appelle avec un jeton scopé.
Le dashboard et le front embarquent un reverse proxy nginx : le navigateur ne dialogue
qu'avec leur origine, qui relaie vers les services internes. C'est l'application concrète de
la consigne "publier avec discernement".

## 3. Flux metier nominal (transaction reussie)

```mermaid
sequenceDiagram
    participant U as web-front
    participant W as WAF (CRS)
    participant A as payment-api
    participant S as auth-service
    participant D as PostgreSQL
    participant P as Prometheus

    U->>W: POST /api/login (identifiants fictifs)
    W->>S: requete filtree
    S-->>U: JWT (via WAF)
    U->>W: POST /api/payments (JWT, montant, beneficiaire)
    W->>A: requete filtree
    A->>S: verification du jeton
    A->>D: debit/credit atomique (transaction SQL)
    D-->>A: commit
    A-->>U: 201 Created (reference transaction)
    A->>P: metriques (latence, code, debit)
```

Point de contrôle métier : une transaction n'est "réussie" que si elle est committée en
base et renvoie une référence. Un conteneur qui redémarre ne prouve rien tant qu'une
nouvelle transaction de bout en bout n'a pas abouti. Le dashboard matérialise donc trois
états : avant l'incident, pendant la perturbation, après la remédiation.

## 4. Chaine de detection et de remediation autonome

```mermaid
sequenceDiagram
    participant ATK as PC Attaquant
    participant API as payment-api
    participant PROM as Prometheus
    participant DET as detection-service (ML)
    participant REM as remediation-service
    participant PORT as Portainer
    participant SEMA as Semaphore
    participant DASH as dashboard

    ATK->>API: injection de defaillance controlee
    API->>PROM: degradation visible (latence, taux d'erreur)
    loop toutes les 15 s
        DET->>PROM: lecture des metriques
        DET->>DET: score d'anomalie (IsolationForest)
    end
    DET->>REM: alerte (service, score, signature)
    REM->>REM: selection du playbook (table de decision)
    REM->>PORT: chemin rapide : restart conteneur (API Portainer)
    REM->>SEMA: chemin audite : tache Ansible (best-effort)
    REM->>API: verification metier (nouvelle transaction)
    REM->>DASH: mise a jour timeline incident
    Note over REM,DASH: etat: detecte -> remedie -> verifie
```

La décision de remédiation suit une table explicite (signature d'incident vers action),
versionnée et auditable. Le moteur ne dispose pas d'un accès shell au système : il agit par
des API authentifiées et scopées. Le chemin rapide passe par l'API Portainer (redémarrage
du conteneur, RTO court) ; le chemin audité déclenche une tâche Ansible via l'API Semaphore,
qui laisse une trace horodatée. Aucun socket Docker brut, aucune interface d'administration
accessible aux autres composants.

## 5. Objectifs de continuite (synthese, detail dans le PCA/PRA)

| Service | Criticite | RTO vise (reprise auto) | RPO vise |
| --- | --- | --- | --- |
| payment-api | Vitale | < 120 s | 0 (transactions committees) |
| auth-service | Vitale | < 120 s | 0 |
| PostgreSQL | Vitale | < 180 s | < 5 min (sauvegarde demo) |
| dashboard / observabilite | Importante | < 300 s | sans objet |
| assistant RAG | Support | best effort | sans objet |

Ces valeurs sont des cibles de démonstration sur un périmètre maîtrisé, pas des engagements
de production. Le PCA/PRA explicite les scénarios couverts et les risques résiduels.

## 6. Choix structurants (resume)

| Decision | Option retenue | Justification | Compromis assume |
| --- | --- | --- | --- |
| Langage services | Python / FastAPI | Unifie API, ML et remediation ; rapide sur un sprint 4 jours | Moins performant que Go sous charge extreme |
| Detection | ML non supervise (IsolationForest) sur metriques | Pas de seuils en dur ; apprend un comportement normal | Sensible a la qualite du baseline |
| Acces remediation | Portainer (rapide) + Semaphore/Ansible (audite) | Reprise rapide + trace auditable ; pas de socket brut | Deux interfaces d'admin a proteger (jetons scopes) |
| Secrets | Vault (runtime) + SOPS (depot) | Separation secrets dynamiques / au repos | Vault en mode dev pour la demo |
| SIEM | Loki + Grafana alerting + regles de correlation | Compatible RAM du PC Hote (Elastic ecarte) | Correlation moins riche qu'un SIEM dedie |
| Assistant | Ollama local + LangChain + Chroma | Souverain, sans secret envoye a un tiers | Qualite limitee par un modele <= 8B |

Le détail de chaque décision, les limites constatées et ce que l'équipe ferait différemment
en contexte industriel figurent dans le dossier d'ingénierie et de gouvernance.
