# Scenarios d'injection de defaillance controlee

Ces scenarios servent un seul but : provoquer un incident observable sur NOTRE propre SI
fictif, afin de declencher la detection et la reprise automatique. C'est l'esprit chaos
engineering du sujet, pas de l'outillage offensif reutilisable.

## Perimetre strict (regles de securite)

- Cible unique : notre plateforme PayAlpha fictive, sur nos machines autorisees.
- Interdits : les reseaux du campus, les autres consortiums, tout service tiers ou accessible sur Internet.
- Aucune donnee reelle. Les comptes et transactions sont fictifs.
- Toute action pouvant sortir du perimetre doit etre interrompue et signalee au coach.

## Les trois scenarios

| Scenario | Lance depuis | Effet provoque | Signature detectee | Reponse attendue | MITRE |
| --- | --- | --- | --- | --- | --- |
| `load_flood.py` | PC Attaquant | Saturation controlee (latence et erreurs en hausse) | payment-api_degraded | Relance du service, reprise | T1498 |
| `malformed_requests.py` | PC Attaquant | Requetes hostiles (SQLi, traversee, outil offensif) | blocage WAF + tag SOC | Blocage au WAF, investigation | T1190 |
| `container_stop.py` | PC Hote (chaos) | Arret d'un conteneur (panne simulee) | payment-api_unavailable | Redemarrage automatique | panne/disponibilite |

## Configuration

Les scenarios reseau visent le WAF du PC Hote :

```bash
export GATEWAY_URL="http://<IP_DU_PC_HOTE>:8080"
```

## Rappel sur la distinction des reponses

Le flood et la panne sont des atteintes a la disponibilite : la bonne reponse est la
restauration automatique. Les requetes malformees relevent d'une tentative de
compromission : la bonne reponse est le blocage et l'investigation, pas un simple
redemarrage. Cette distinction est au coeur de l'evaluation.
