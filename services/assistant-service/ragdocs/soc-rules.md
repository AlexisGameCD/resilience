# Fonction SIEM / SOC integree a la supervision

RESILIENCE-ALPHA ne deploie pas un SIEM lourd (Elastic est ecarte pour tenir dans la RAM
du PC Hote). La fonction SOC est assuree par la chaine Loki + Grafana, alimentee par les
journaux de tous les conteneurs (Promtail) et par les metriques Prometheus. Les evenements
de securite du WAF sont tagues (tag resilience-alpha, references MITRE ATT&CK), ce qui rend
la correlation lisible.

## Sources de donnees

| Source | Contenu | Usage SOC |
| --- | --- | --- |
| Loki (via Promtail) | Journaux WAF, payment-api, auth-service, remediation | Detection de motifs, investigation |
| Prometheus | Metriques HTTP, echecs d'auth, etat des conteneurs | Seuils de contexte, correlation temporelle |
| detection-service | Score d'anomalie ML | Signal principal d'incident |

## Regles de correlation (SOC)

Chaque regle associe une observation a une technique MITRE ATT&CK et a une conduite a tenir.

### R1 : exploitation d'une application exposee (T1190)
- Observation : rafale de reponses 403 du WAF taguees attack-lab.
- Requete Loki :
  ```logql
  sum(count_over_time({service="waf"} |= "RESILIENCE-ALPHA" [1m]))
  ```
- Seuil d'attention : plus de 5 blocages en 1 minute.
- Conduite : confirmer la source, verifier l'absence de contournement, surveiller la bascule vers un autre vecteur.

### R2 : force brute sur l'authentification (T1110)
- Observation : hausse des echecs d'authentification.
- Requete Prometheus :
  ```promql
  sum(rate(auth_login_failed_total[1m]))
  ```
- Seuil d'attention : plus de 1 echec/s pendant 1 minute.
- Conduite : envisager un verrouillage temporaire du compte, surveiller la reussite tardive (compromission).

### R3 : deni de service controle (T1498)
- Observation : effondrement du debit utile, latence p95 et taux d'erreur en hausse simultanee.
- Requete Prometheus :
  ```promql
  histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{service="payment-api"}[1m])) by (le))
  ```
- Signal principal : le detection-service bascule le score sous le seuil. La remediation est declenchee.

### R4 : action de reprise executee (traabilite)
- Observation : le moteur de remediation a agi.
- Requete Loki :
  ```logql
  {service="remediation-service"} |= "incident"
  ```
- Conduite : verifier le RTO, confirmer la transaction de preuve, consigner l'incident.

## Distinction disponibilite / compromission

La reponse n'est pas la meme selon la nature de l'incident, conformement au sujet :

| Nature | Signaux | Reponse attendue |
| --- | --- | --- |
| Atteinte a la disponibilite (DoS, panne) | debit, latence, up | Restauration automatique du service |
| Tentative de compromission (injection, exfiltration) | blocages WAF, motifs SQLi, acces anormaux | Blocage au WAF, investigation, PAS seulement un redemarrage |

Un redemarrage ne corrige pas une faille applicative : en cas de compromission, la priorite
est le confinement (blocage de la source, revue des privileges), pas le retour a la
disponibilite. Cette nuance est portee dans le dossier de gouvernance.
