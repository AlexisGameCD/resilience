# Runbook : incident et reprise PayAlpha

Document d'exploitation. Il decrit la conduite a tenir face a un incident et le
fonctionnement de la reprise automatique. Il alimente aussi l'assistant RAG.

## 1. Comprendre la chaine

1. Le detection-service lit les metriques toutes les 15 s et score l'etat du service.
2. Un ecart durable (2 cycles) ou une indisponibilite declenche une alerte vers la remediation.
3. La remediation choisit une action dans `playbooks.yml`, l'execute, puis verifie la reprise par une transaction fictive.
4. Le dashboard affiche l'etat avant, pendant et apres.

## 2. Signatures et actions

| Signature | Sens | Action automatique | Verification |
| --- | --- | --- | --- |
| payment-api_unavailable | Conteneur arrete ou plante | Demarrage puis redemarrage | Transaction fictive reussie |
| payment-api_degraded | Charge hostile ou saturation | Redemarrage (libere les ressources) | Transaction fictive reussie |
| payment-api_anomaly | Ecart comportemental | Redemarrage de precaution | Transaction fictive reussie |

## 3. Verifier manuellement (si besoin)

```bash
# Etat global
docker compose ps
make verify

# Dernier incident vu par la remediation
curl -s http://localhost:8082/api/remediation/incidents | python3 -m json.tool

# Score courant de la detection
curl -s http://localhost:8082/api/detection/state | python3 -m json.tool
```

## 4. Si la reprise automatique echoue

La reprise automatique est le point decisif du sujet : aucune intervention corrective
humaine n'est admise pendant la demonstration. Si elle echoue malgre tout en conditions
reelles, la conduite hors demonstration est :

1. Confirmer la nature : atteinte a la disponibilite ou compromission (voir SOC).
2. Disponibilite : relancer le service concerne via le playbook Ansible `remediate.yml`.
3. Compromission : NE PAS se limiter a un redemarrage. Bloquer la source au WAF, isoler, investiguer les journaux (Loki), puis restaurer.
4. Consigner l'incident (horodatage, signature, action, RTO).

## 5. Distinction essentielle

Un conteneur qui redemarre ne prouve pas la reprise. La preuve est une nouvelle
transaction fictive qui aboutit de bout en bout. C'est ce que verifie la remediation et ce
que montre le dashboard.
