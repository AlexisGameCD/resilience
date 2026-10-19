# Gestion des secrets

Objectif du rendu : aucun secret en clair dans l'archive livree. Deux mecanismes
complementaires repondent a deux besoins distincts.

## 1. Secrets au repos dans le depot : SOPS

Les valeurs sensibles versionnees (le cas echeant) sont chiffrees avec SOPS (cle age),
jamais en clair. Le fichier `.sops.yaml` definit les regles de chiffrement ; seuls les
champs sensibles (`password`, `secret`, `token`, `key`) sont chiffres, ce qui garde le
reste lisible en revue.

```bash
# Chiffrer un fichier de secrets
sops --encrypt security/secrets/secrets.example.yaml > security/secrets/secrets.enc.yaml

# Dechiffrer au besoin (jamais committe en clair)
sops --decrypt security/secrets/secrets.enc.yaml
```

`.gitignore` exclut tout fichier dechiffre (`*.dec.yaml`).

## 2. Secrets a l'execution : HashiCorp Vault

En fonctionnement, les secrets dynamiques (mot de passe de base, cle de signature JWT)
sont destines a Vault. En demonstration, Vault tourne en mode dev et le script de
bootstrap y charge les valeurs. Le `.env` ne sert qu'au tout premier amorcage et n'est
jamais committe (exclu par `.gitignore`).

```bash
# Charger les secrets de demo dans Vault (depuis le PC Hote)
docker compose exec -e POSTGRES_PASSWORD -e JWT_SECRET vault \
  sh /vault-bootstrap.sh
```

## Limites assumees (demonstration)

- Vault tourne en mode dev (jeton racine fixe) : adapte a un labo, pas a la production.
- En production, chaque service recupererait son secret au demarrage via l'API Vault
  (AppRole), avec rotation automatique. Ce point figure dans les limites du dossier.
- Les identifiants de demonstration (comptes fictifs) sont documentes volontairement :
  aucune donnee reelle n'est manipulee.

## Rotation

| Secret | Mecanisme cible | Frequence recommandee |
| --- | --- | --- |
| Cle JWT | Vault, rotation + revocation | 90 jours ou sur incident |
| Mot de passe base | Vault dynamic secrets | 30 jours |
| Cle API remediation | Vault | sur incident |
