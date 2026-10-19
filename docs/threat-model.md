# Modele de menaces (synthese)

Vue synthetique des menaces retenues pour PayAlpha. L'analyse structuree complete (EBIOS
Risk Manager) figure dans le dossier d'ingenierie et de gouvernance.

## Biens essentiels

| Bien essentiel | Besoin de securite prioritaire |
| --- | --- |
| Service de paiement (disponibilite du traitement) | Disponibilite |
| Integrite des transactions et des soldes | Integrite |
| Journaux et traabilite | Integrite, disponibilite |
| Secrets (cle JWT, acces base) | Confidentialite |

## Sources de risque et evenements redoutes

| Source | Evenement redoute | Impact | Besoin touche |
| --- | --- | --- | --- |
| Attaquant externe | Deni de service sur l'API de paiement | Interruption du service | Disponibilite |
| Attaquant externe | Injection applicative (SQLi) | Alteration ou fuite de donnees fictives | Integrite, confidentialite |
| Attaquant externe | Tentative d'exfiltration | Divulgation de donnees | Confidentialite |
| Defaillance technique | Plantage d'un conteneur | Interruption du service | Disponibilite |
| Acteur interne / outil | Abus du moteur de remediation | Elevation de privileges | Integrite |

## Mesures en regard (vue defense en profondeur)

| Menace | Mesure preventive | Mesure de detection | Mesure de reprise |
| --- | --- | --- | --- |
| DoS | Limites de ressources, relance rapide | Detection ML (latence, erreurs) | Redemarrage automatique |
| Injection | WAF + CRS, validation des entrees | Tags SOC, journaux Loki | Blocage, investigation |
| Panne | Healthchecks, redondance applicative | up == 0 | Redemarrage automatique |
| Abus remediation | API Portainer/Semaphore scopees, moindre privilege, pas de shell | Journaux remediation + historique Semaphore | Revue de la table de decision |

## Perimetre et hypotheses

- Environnement isole (reseau du groupe), donnees fictives.
- Le PC Attaquant ne vise que notre SI.
- Les menaces hors perimetre (chaine d'approvisionnement, acces physique au campus) sont
  citees mais non traitees dans la demonstration de quatre jours.
