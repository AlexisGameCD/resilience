# Consigne additionnelle 1 : authentification renforcee du back-office

Reconnaissance faciale par camera du PC Hote apres la saisie de l'identifiant, puis mot de
passe, avec une LED bicolore (ESP8266) qui suit l'etat. Cette note decrit l'architecture,
l'installation, le flux et la conformite a la consigne.

## Architecture

Trois nouveaux services, plus un firmware, greffes sur la stack existante sans la modifier.

| Composant | Role |
| --- | --- |
| `face-service` | IA legere de reconnaissance faciale (OpenCV Haar + LBPH, 100 % CPU). Enrolement, verification, habilitations, anti-abus. |
| `back-office` | Page gardee (nginx) : flux identifiant puis visage puis mot de passe, console d'habilitations, indicateur LED. Port 8083. |
| `led-service` | Etat logique de la LED, interroge par le simulateur et par l'ESP8266. Port 8085. |
| `firmware/esp8266-led` | Projet PlatformIO (CLion) pour l'objet connecte qui pilote la LED physique. |

### Deux decisions techniques importantes

1. **La camera passe par le navigateur** (`getUserMedia`), pas par un conteneur. Docker
   Desktop (Windows comme Mac) ne permet pas de brancher une camera USB dans un conteneur.
   Le navigateur tourne sur le PC Hote, donc la camera est bien sur le PC Hote comme exige.
   Le navigateur capture une image et l'envoie a `face-service` pour la reconnaissance.
   **Consequence** : ouvrir le back-office en `http://localhost:8083` sur le PC Hote. Le
   navigateur refuse l'acces camera sur une adresse IP non securisee, mais l'autorise sur
   `localhost`.

2. **IA legere, sans telechargement** : detecteur de visage Haar (embarque dans l'image) et
   reconnaisseur LBPH d'OpenCV. Pas de GPU, pas de modele externe, build reproductible.

## Installation

1. Copier dans le depot les dossiers livres : `services/face-service`, `services/led-service`,
   `services/back-office`, `firmware/esp8266-led`, et cette note `docs/`.
2. Remplacer `docker-compose.yml` par la version fournie (deja fusionnee), ou appliquer
   `AJOUTS-docker-compose.txt` a la main.
3. Ajouter a `.env` et `.env.example` les variables de `AJOUTS-env.txt`.
4. Construire et lancer :
   ```
   docker compose build face-service led-service back-office
   docker compose up -d
   ```
   Sous Portainer : renseigner les variables dans la section Environment variables de la
   stack, puis redeployer. La premiere build de `face-service` telecharge OpenCV (quelques
   minutes).

## Amorcage : enroler le premier visage

La reconnaissance ne connait personne au depart. On enrole via la console d'habilitations,
protegee par le jeton admin (pas par le visage, pour eviter le probleme de l'oeuf et la poule).

1. Ouvrir `http://localhost:8083` sur le PC Hote, onglet **Habilitations**.
2. Saisir le `FACE_ADMIN_TOKEN` (valeur du `.env`), cliquer **Charger la liste**.
3. Saisir un identifiant (ex. `alice`, un compte qui existe deja dans `auth_users`), choisir un
   role, **Demarrer la camera**, **Capturer** 5 photos sous des angles legerement differents,
   puis **Enregistrer l'enrolement**.
4. La personne apparait dans la table des habilitees. Elle peut desormais passer le flux d'acces.

## Le flux d'acces et la LED

| Etape | Action | LED |
| --- | --- | --- |
| Depart | Page chargee | eteinte |
| 1 | Saisie de l'identifiant, camera active | eteinte |
| 2 reconnu | Visage reconnu, passage au mot de passe | vert clignotant |
| 2 non reconnu | Identifiant vide, camera eteinte apres 30 s, nouvelle saisie | rouge fixe 30 s |
| 3 valide | Back-office ouvert | vert fixe 30 s puis eteint |
| 3 invalide | Reprise de toute l'identification | rouge clignotant 10x puis eteint |
| Abus | 2e echec de reconnaissance : blocage 5 min | eteinte |

La LED est visible a trois endroits : la pastille en haut du back-office, le simulateur plein
ecran `http://localhost:8083/led.html`, et l'objet ESP8266 reel une fois flashe.

## Conformite a la consigne

| Exigence | Reponse |
| --- | --- |
| Camera activee apres l'identifiant | Flux a etapes, `getUserMedia` sur le PC Hote |
| Reconnu : saisie du mot de passe | Etape mot de passe debloquee, validee par `auth-service` |
| Non reconnu : identifiant vide, camera eteinte | Reinitialisation apres le rouge fixe 30 s |
| 1 reprise puis blocage 5 min | `face-service` : 2 echecs, blocage 300 s |
| Camera obligatoirement sur le PC Hote | Navigateur sur le PC Hote (`localhost`) |
| IA legere de reconnaissance sur le PC Hote | Conteneur `face-service`, OpenCV Haar + LBPH |
| Gestion integree, habilitations completes | Onglet Habilitations : enroler, lister, activer, revoquer |
| ESP8266 PlatformIO + CLion, LED bicolore, WiFi | `firmware/esp8266-led` + simulateur a l'ecran |
| LED eteinte par defaut | Etat `off` au chargement |
| Reconnu : vert clignotant jusqu'au mot de passe | `green_blink` |
| Mot de passe valide : vert fixe 30 s puis back dispo | `green_30s` + back-office affiche |
| Mot de passe faux : rouge 10x puis reprise | `red_blink_10` + reinitialisation |
| Non reconnu : rouge fixe 30 s avant extinction | `red_30s` + camera coupee apres le compte a rebours |

## A tester sur le PC Hote

- Build des trois conteneurs sans erreur (`docker compose build`).
- `http://localhost:8083/led.html` : la LED reagit quand on force un etat
  (`curl -X POST http://localhost:8083/api/led/state -H "Content-Type: application/json" -d '{"mode":"green_blink"}'`).
- Enrolement d'un visage via la console, puis acces reconnu.
- Trois visages differents : regler `FACE_LBPH_THRESHOLD` si trop strict ou trop permissif.

## Limites assumees (a mentionner a l'oral)

- Reconnaissance LBPH : robuste en conditions d'eclairage stables ; un seuil reglable gere le
  compromis faux positifs / faux negatifs. Montee en gamme possible vers un modele a embeddings
  (SFace) sans changer l'architecture.
- Jeton admin : controle de niveau demonstration pour la console d'habilitations ; en production
  il serait remplace par une authentification administrateur a part entiere.
- Blocage anti-abus : en memoire (remis a zero au redemarrage du service), suffisant pour la demo.
