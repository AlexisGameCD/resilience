# Documentation des API

Toutes les API métier sont servies via le WAF (`http://<hote>:8080`). Les services internes
(detection, remediation, assistant) sont exposes au navigateur via le reverse proxy du
dashboard (`http://<hote>:8082/api/...`), jamais directement.

Chaque service FastAPI publie aussi son schema OpenAPI interactif sur `/docs` (Swagger) et
`/openapi.json`.

## payment-api (via WAF, port 8080)

| Methode | Chemin | Auth | Description |
| --- | --- | --- | --- |
| POST | /login | non | Authentifie un compte fictif, renvoie un JWT |
| POST | /payments | JWT | Initie une transaction fictive |
| GET | /payments/{reference} | non | Consulte une transaction |
| GET | /accounts/{iban} | non | Consulte un compte fictif |
| GET | /stats | non | Compteurs de transactions |
| GET | /health | non | Etat de sante |
| GET | /metrics | non | Metriques Prometheus |

Exemple :

```bash
TOKEN=$(curl -s http://localhost:8080/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"Demo#2026"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8080/payments \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"src_iban":"FR76-FAKE-0001","dst_iban":"FR76-FAKE-9001","amount":12.50}'
```

## auth-service (interne)

| Methode | Chemin | Description |
| --- | --- | --- |
| POST | /login | Emet un JWT (HS256, TTL 900 s) |
| POST | /verify | Verifie un jeton |
| GET | /health, /metrics | Sante et metriques |

## detection-service (via dashboard : /api/detection)

| Methode | Chemin | Description |
| --- | --- | --- |
| GET | /state | Score courant, seuil, historique, incident ouvert |
| GET | /score | Score a la demande |
| GET | /health, /metrics | Sante et metriques |

## remediation-service (via dashboard : /api/remediation)

| Methode | Chemin | Auth | Description |
| --- | --- | --- | --- |
| POST | /alerts | cle X-API-Key | Recoit une alerte et declenche la reprise |
| GET | /incidents | non | Liste des incidents et chronologie |
| GET | /state | non | Incident courant |
| GET | /health, /metrics | non | Sante et metriques |

## assistant-service (via dashboard : /api/assistant)

| Methode | Chemin | Description |
| --- | --- | --- |
| POST | /ask | Question operateur, reponse RAG avec sources |
| POST | /reindex | Reconstruit la base documentaire |
| GET | /health, /metrics | Sante et metriques |
