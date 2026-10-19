# Durcissement de la plateforme

Mesures appliquees dans RESILIENCE-ALPHA, reliees aux referentiels (ANSSI, CIS Docker
Benchmark, ISO 27001 A.8, OWASP). Le principe directeur est le moindre privilege : un
composant ne doit disposer que de ce qui lui est strictement necessaire.

## Mesures appliquees

| Domaine | Mesure | Reference |
| --- | --- | --- |
| Exposition reseau | WAF, front, dashboard, Grafana, Portainer et Semaphore publient un port ; base, secrets, observabilite et remediation restent internes | ISO 27001 A.8.20, CIS Docker 5 |
| Conteneurs | Utilisateur non root dans chaque service applicatif (uid >= 10000) | CIS Docker 4.1 |
| Images | Images slim et versions epinglees ; pas de latest | CIS Docker 4.2 |
| Acces Docker | Le moteur de remediation agit par API Portainer (restart) et Semaphore (Ansible), avec jeton scope ; jamais le socket brut ni de shell | ANSSI, moindre privilege |
| Interfaces d'admin | Portainer et Semaphore protegees par authentification, cantonnees au reseau du groupe, mots de passe par defaut changes | ISO 27001 A.8.2, A.8.5 |
| Montages | Fichiers de configuration montes en lecture seule (:ro) | CIS Docker 5.12 |
| Filtrage applicatif | WAF ModSecurity + OWASP CRS en amont des API | OWASP, ISO 27001 A.8.26 |
| Authentification | JWT a duree de vie courte (900 s), signature verifiee | OWASP ASVS |
| Secrets | Vault a l'execution, SOPS au repos, rien en clair dans le depot | ISO 27001 A.8.24 |
| Journalisation | Centralisation Loki, correlation SIEM, limites de taille des logs | ISO 27001 A.8.15 |
| Surface d'admin | Aucune interface d'administration ouverte aux autres composants | Sujet, moindre privilege |

## Renforcement supplementaire (override)

Le fichier `docker-compose.hardening.yml` ajoute une couche de durcissement activable :

```bash
docker compose -f docker-compose.yml -f security/hardening/docker-compose.hardening.yml up -d
```

Il applique : `no-new-privileges`, abandon de toutes les capacites Linux
(`cap_drop: ALL`), et systeme de fichiers racine en lecture seule la ou c'est possible.

## Points de vigilance (limites assumees)

- Vault en mode dev (jeton racine fixe) : a remplacer par un Vault scelle en production.
- TLS non active entre composants internes : acceptable sur un reseau de labo isole,
  a activer (mTLS) en contexte industriel.
- Le moteur de remediation conserve un privilege eleve (redemarrage de conteneurs) :
  c'est le compromis central, encadre par des API authentifiees (Portainer, Semaphore),
  des jetons scopes et l'absence de shell. Portainer et Semaphore etant des interfaces
  d'administration puissantes, leur acces doit rester strictement controle.
