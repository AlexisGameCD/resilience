# Portainer et Semaphore : cockpit et automatisation

RESILIENCE-ALPHA s'appuie sur trois outils d'exploitation complementaires :

- Ansible : le contenu d'automatisation (playbooks de deploiement et de reprise).
- Semaphore : l'interface, l'API et l'historique d'execution au-dessus d'Ansible.
- Portainer : le cockpit de gestion et de visualisation des conteneurs.

Ils remplacent le docker-socket-proxy (retire) et l'appel manuel d'Ansible en ligne de commande.

Important : Portainer est installe SEPAREMENT (hors de la stack). C'est lui qui deploie la
stack RESILIENCE-ALPHA et qui la gere ensuite. Il n'apparait donc pas dans
`docker-compose.yml`. Le moteur de remediation appelle son API via le PC Hote
(`host.docker.internal:9000`).

## Le double chemin de remediation

| Chemin | Outil | Role | Effet sur le RTO |
| --- | --- | --- | --- |
| Rapide | API Portainer | Redemarre le conteneur degrade | Quasi instantane, RTO court |
| Audite | API Semaphore (Ansible) | Trace horodatee + verification metier | Hors chemin critique (best-effort) |

Le moteur de remediation agit d'abord vite (Portainer), puis depose une trace auditable
dans Semaphore. Si Semaphore n'est pas configure, l'audit est simplement ignore et la
reprise fonctionne quand meme.

## Acces et ports

| Service | URL | Usage |
| --- | --- | --- |
| Portainer | http://localhost:9000 | Cockpit (installe separement), deploie et gere la stack |
| Semaphore | http://localhost:3001 | Automatisation Ansible, historique des taches |

## Mise en route de Portainer (standalone)

Si Portainer n'est pas encore installe, le lancer en conteneur autonome :

```bash
docker volume create portainer_data
docker run -d -p 9000:9000 -p 9443:9443 --name portainer --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:2.21.4
```

Puis definir le compte admin dans les minutes qui suivent (sinon Portainer se verrouille
par securite : il faut alors `docker restart portainer` et recommencer). Au besoin :

```bash
PORTAINER_PASSWORD='votre_mot_de_passe' sh infra/portainer/init.sh
```

Pour la remediation, deux options d'authentification :
- renseigner `PORTAINER_USER` et `PORTAINER_PASSWORD` dans `.env` (simple), ou
- creer un jeton d'API (My account > Access tokens) et le mettre dans `PORTAINER_API_KEY` (prefere).

Verifier l'identifiant de l'environnement Docker local dans votre Portainer (menu
Environments) et le reporter dans `PORTAINER_ENDPOINT_ID` (souvent 1).

## Deployer la stack RESILIENCE-ALPHA via Portainer

La stack contient des services construits sur place (`build:`) et des montages relatifs.
La methode fiable est donc le deploiement par depot Git (Portainer clone le depot et
construit les images). Le web editor et l'upload simple ne suffisent pas ici (pas de
contexte de build ni de fichiers annexes).

1. Pousser le projet sur un depot Git accessible par Portainer (GitHub, GitLab, ou une
   forge interne). Un depot prive fonctionne en ajoutant des identifiants dans Portainer.
2. Dans Portainer : Stacks > Add stack > Name = `resilience-alpha`.
3. Choisir la methode Repository :
   - Repository URL : l'URL de votre depot
   - Reference : la branche (par exemple `refs/heads/main`)
   - Compose path : `docker-compose.yml`
4. Dans Environment variables, coller le contenu de `.env` (ou charger le fichier).
   Points importants : `PORTAINER_URL=http://host.docker.internal:9000`,
   `PORTAINER_ENDPOINT_ID`, et les identifiants Portainer/Semaphore.
5. Deployer. Portainer clone le depot, construit les images et demarre les 16 services.

Bonus : comme la stack est deployee depuis un clone Git, le montage
`.:/tmp/semaphore/project` de Semaphore est deja un depot Git. Aucun `git init`
supplementaire n'est necessaire.

Alternative sans Git (moins propre) : construire les images sur le PC Hote avec
`docker compose build`, puis deployer une stack dont les services referencent ces images
(remplacer les blocs `build:` par `image:`). A reserver si le depot Git n'est pas une option.

## Mise en route de Semaphore

Semaphore clone les playbooks via Git. Le projet est monte en lecture seule dans le
conteneur (`/tmp/semaphore/project`). Assurez-vous que le projet est un depot Git :

```bash
git init && git add . && git commit -m "init"   # si ce n'est pas deja un depot clone
```

Puis lancer le bootstrap (depuis le PC Hote, apres `make up`) :

```bash
SEMAPHORE_ADMIN_PASSWORD='...' python3 infra/semaphore/bootstrap.py
```

Le script cree le projet, le depot local, l'inventaire, l'environnement et le template
`Remediation-Audit`. Reportez les valeurs affichees dans `.env` :

```
SEMAPHORE_API_TOKEN=...
SEMAPHORE_PROJECT_ID=...
SEMAPHORE_TEMPLATE_ID=...
```

Puis relancez le remediation-service : `docker compose up -d remediation-service`.

### Procedure manuelle (si le bootstrap echoue selon la version)

Dans l'UI Semaphore : creer un projet, une cle de type None, un depot
(`file:///tmp/semaphore/project`, branche `main`), un inventaire statique
(`localhost ansible_connection=local`), un environnement vide, puis un template
pointant sur `infra/ansible/playbooks/remediate.yml`. Noter les identifiants de projet
et de template, et generer un jeton dans My account > API Tokens.

### Tests reguliers (esprit DORA)

Planifiez le template `Remediation-Audit` (action=verify) dans Semaphore pour une
verification periodique de resilience. Chaque execution laisse une trace horodatee,
utile comme preuve de tests reguliers.

## Securite

Portainer et Semaphore sont des interfaces d'administration puissantes. Pour respecter la
consigne du sujet (ne pas ouvrir d'admin a n'importe quel composant) :

- ne pas exposer ces interfaces au-dela du reseau du groupe ;
- utiliser un compte de service dedie et un jeton d'acces limite pour la remediation ;
- changer les mots de passe par defaut avant toute demonstration ;
- conserver les jetons hors du depot (fichier `.env`, non committe).
