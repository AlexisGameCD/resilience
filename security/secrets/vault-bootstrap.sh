#!/usr/bin/env sh
# Charge les secrets de demonstration dans Vault (mode dev).
# A executer dans le conteneur vault :
#   docker compose exec -e POSTGRES_PASSWORD -e JWT_SECRET -e REM_API_KEY vault sh /vault-bootstrap.sh
set -eu

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-root-demo-token}"

# Active un moteur KV v2 dedie (idempotent)
vault secrets enable -path=payalpha kv-v2 2>/dev/null || true

vault kv put payalpha/db      password="${POSTGRES_PASSWORD:-change_me_demo_only}"
vault kv put payalpha/jwt     secret="${JWT_SECRET:-change_me}"
vault kv put payalpha/remediation api_key="${REM_API_KEY:-change_me_internal_only}"

echo "Secrets de demonstration charges dans Vault sous payalpha/*."
echo "En production, les services liraient ces valeurs via AppRole au demarrage."
