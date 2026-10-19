# Checklist de demonstration live

Soutenance locale : dix minutes (cinq de presentation et demo, cinq d'echange).
Finale nationale : cinq minutes (une minute de pitch, une minute de Clip Chrono, trois
minutes de demo live depuis le PC Hote).

## Avant la soutenance (pre-vol)

- [ ] PC Hote : Docker Desktop (WSL2) demarre, `make up` lance, tous les conteneurs sains (`make ps`).
- [ ] Modele de detection present (`ml/model/anomaly.joblib`) ou `make train` execute.
- [ ] Trafic de reference injecte (`make seed`) pour que le modele ait une base saine.
- [ ] Verification de bout en bout OK (`make verify`).
- [ ] PC Attaquant connecte au point d'acces du groupe (RESILIENCE-G<n>), `GATEWAY_URL` exporte.
- [ ] Facultatif : Ollama demarre et modeles telecharges (assistant RAG).
- [ ] Dashboard (8082), front (8081) et Grafana (3000) ouverts dans des onglets.
- [ ] Clip Chrono pret a diffuser en secours.

## Repartition des roles (a adapter)

- Pilote demo : lance la sequence et commente.
- Operateur attaquant : declenche le scenario depuis le PC Attaquant.
- Narrateur gouvernance : relie la demo a EBIOS, PCA/PRA, NIS2/DORA.
- Support technique : surveille les conteneurs, prêt à diffuser le clip si besoin.

## Sequence de demonstration (3 minutes)

1. Etat normal : jouer une transaction (`make demo-normal`), montrer le dashboard vert.
2. Incident : depuis le PC Attaquant, lancer un scenario (`make attack-load` ou `make attack-stop`).
3. Detection : montrer le score d'anomalie basculer sur le dashboard.
4. Remediation : montrer la chronologie d'incident (action, redemarrage) sans toucher au clavier.
5. Preuve : rejouer une transaction (`make demo-normal`), montrer le retour au vert et la reference.

## A ne pas faire

- Aucune intervention corrective humaine entre la detection et la reprise : sinon 0/5 sur l'axe remediation.
- Ne pas viser le reseau du campus, un autre groupe ou un service tiers : perimetre strictement limite a notre SI.
- Ne pas confondre disponibilite et compromission : un redemarrage ne corrige pas une faille applicative.

## Si quelque chose derape

- Service lent a redemarrer : laisser la remediation finir, le RTO vise est inferieur a 120 s.
- Attaque sans effet visible : augmenter la duree ou la concurrence (`make attack-load 60 60`).
- Probleme materiel : diffuser le Clip Chrono et commenter la sequence.
