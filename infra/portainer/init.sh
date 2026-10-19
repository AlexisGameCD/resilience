#!/usr/bin/env sh
# Initialise le compte admin Portainer juste apres le premier demarrage.
# A lancer dans les minutes qui suivent "docker compose up" (fenetre d'init Portainer).
#
# Usage :
#   PORTAINER_PASSWORD='motdepasse_min_12_caracteres' sh infra/portainer/init.sh
set -eu

URL="${PORTAINER_URL:-http://localhost:9000}"
USER="${PORTAINER_USER:-admin}"
PASS="${PORTAINER_PASSWORD:?Definissez PORTAINER_PASSWORD (12 caracteres minimum)}"

echo "Initialisation de l'admin Portainer sur ${URL}..."
code=$(curl -s -o /tmp/portainer_init.json -w "%{http_code}" \
  -X POST "${URL}/api/users/admin/init" \
  -H "Content-Type: application/json" \
  -d "{\"Username\":\"${USER}\",\"Password\":\"${PASS}\"}") || true

if [ "$code" = "200" ]; then
  echo "Compte admin cree."
  echo "Creez ensuite un jeton d'API dans l'UI (My account > Access tokens) et reportez-le"
  echo "dans PORTAINER_API_KEY du fichier .env, ou laissez le couple user/mot de passe."
else
  echo "Reponse ${code} : l'admin existe peut-etre deja, ou la fenetre d'init est fermee."
  echo "Dans ce cas, connectez-vous sur ${URL} et gerez l'admin depuis l'UI."
fi
