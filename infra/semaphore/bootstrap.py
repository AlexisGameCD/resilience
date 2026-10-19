"""
Bootstrap Semaphore pour RESILIENCE-ALPHA (via l'API, best-effort).

Cree le projet, une cle "none", le depot local (file://), un inventaire localhost, un
environnement et le template "Remediation-Audit" qui lance remediate.yml (action=verify).
Affiche en fin de course le jeton d'API, l'identifiant de projet et de template a reporter
dans .env (SEMAPHORE_API_TOKEN, SEMAPHORE_PROJECT_ID, SEMAPHORE_TEMPLATE_ID).

Prerequis : la stack est demarree, Semaphore accessible (http://localhost:3001), et le
projet est un depot Git (git init + commit) pour que Semaphore puisse le cloner.

Usage : python3 infra/semaphore/bootstrap.py
Les identifiants admin sont lus dans l'environnement (SEMAPHORE_ADMIN / SEMAPHORE_ADMIN_PASSWORD).
Les versions de Semaphore peuvent differer : en cas d'echec, suivez la procedure manuelle
decrite dans docs/portainer-semaphore.md.
"""
import os
import sys
import json
import httpx

URL = os.getenv("SEMAPHORE_URL", "http://localhost:3001")
ADMIN = os.getenv("SEMAPHORE_ADMIN", "admin")
PASSWORD = os.getenv("SEMAPHORE_ADMIN_PASSWORD", "change_me_demo_only")
BRANCH = os.getenv("SEMAPHORE_GIT_BRANCH", "main")
# Semaphore clone les playbooks depuis le depot GitHub du projet
GIT_URL = os.getenv("SEMAPHORE_GIT_URL", "https://github.com/<votre-compte>/<votre-depot>.git")


def main():
    c = httpx.Client(base_url=URL, timeout=10.0)

    # 1. Connexion (cookie de session)
    r = c.post("/api/auth/login", json={"auth": ADMIN, "password": PASSWORD})
    if r.status_code not in (200, 204):
        print(f"ERREUR connexion Semaphore ({r.status_code}): {r.text}")
        print("Verifiez les identifiants admin et que Semaphore est demarre.")
        sys.exit(1)
    print("Connexion OK.")

    def post(path, payload, label):
        rr = c.post(path, json=payload)
        if rr.status_code not in (200, 201, 204):
            print(f"  [!] {label} : code {rr.status_code} : {rr.text[:200]}")
            return None
        data = rr.json() if rr.content else {}
        print(f"  [+] {label} : id={data.get('id')}")
        return data

    # 2. Jeton d'API (pour le moteur de remediation)
    tok = post("/api/user/tokens", {}, "jeton d'API")
    token_id = tok.get("id") if tok else None

    # 3. Projet
    proj = post("/api/projects", {"name": "RESILIENCE-ALPHA", "alert": False}, "projet")
    if not proj:
        print("Abandon : projet non cree.")
        sys.exit(1)
    pid = proj["id"]

    # 4. Cle "none"
    key = post(f"/api/project/{pid}/keys",
               {"name": "none", "type": "none", "project_id": pid}, "cle none")
    kid = key.get("id") if key else None

    # 5. Depot local (le projet est monte en lecture seule dans le conteneur)
    repo = post(f"/api/project/{pid}/repositories",
                {"name": "github", "project_id": pid,
                 "git_url": GIT_URL, "git_branch": BRANCH,
                 "ssh_key_id": kid}, "depot github")
    rid = repo.get("id") if repo else None

    # 6. Inventaire localhost
    inv = post(f"/api/project/{pid}/inventory",
               {"name": "hote-local", "project_id": pid, "type": "static",
                "inventory": "[hote]\nlocalhost ansible_connection=local\n",
                "ssh_key_id": kid, "become_key_id": kid}, "inventaire")
    invid = inv.get("id") if inv else None

    # 7. Environnement
    env = post(f"/api/project/{pid}/environment",
               {"name": "default", "project_id": pid, "json": "{}", "env": "{}"}, "environnement")
    envid = env.get("id") if env else None

    # 8. Template de remediation (audit)
    tpl = post(f"/api/project/{pid}/templates",
               {"project_id": pid, "name": "Remediation-Audit", "app": "ansible",
                "playbook": "infra/ansible/playbooks/remediate.yml",
                "inventory_id": invid, "repository_id": rid, "environment_id": envid,
                "arguments": "[]", "type": ""}, "template Remediation-Audit")
    tid = tpl.get("id") if tpl else None

    print("\n=== A reporter dans votre fichier .env ===")
    print(f"SEMAPHORE_API_TOKEN={token_id or '<creez un jeton dans l UI>'}")
    print(f"SEMAPHORE_PROJECT_ID={pid}")
    print(f"SEMAPHORE_TEMPLATE_ID={tid or '<id du template>'}")
    print("\nAstuce : planifiez le template Remediation-Audit dans l UI pour une verification")
    print("periodique de resilience (tests reguliers, esprit DORA).")


if __name__ == "__main__":
    main()
