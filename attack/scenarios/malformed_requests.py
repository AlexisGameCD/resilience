"""
Scenario 2 : requetes hostiles (tentative de compromission).

But : envoyer des requetes malformees typiques (injection SQL, traversee de repertoire,
outil offensif) et verifier que le WAF les BLOQUE et les journalise. Demontre la couche
defensive et alimente la correlation SOC (tag resilience-alpha / MITRE).

Perimetre : notre SI fictif uniquement, via le WAF du PC Hote.

Usage :
  export GATEWAY_URL="http://<IP_DU_PC_HOTE>:8080"
  python3 attack/scenarios/malformed_requests.py
"""
import os
import json
import urllib.request
import urllib.error

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")

# Chaque entree est une requete conçue pour etre bloquee par le WAF (CRS + regles custom).
CASES = [
    ("Injection SQL dans le corps",
     "POST", "/payments",
     {"src_iban": "FR76-FAKE-0001' OR '1'='1", "dst_iban": "x", "amount": 1},
     {"Content-Type": "application/json"}),
    ("Traversee de repertoire dans l'URL",
     "GET", "/accounts/../../etc/passwd", None, {}),
    ("Outil offensif annonce (User-Agent)",
     "GET", "/health", None, {"User-Agent": "resilience-redteam/1.0"}),
    ("Clause DROP TABLE",
     "POST", "/payments",
     {"src_iban": "x; DROP TABLE transactions;--", "dst_iban": "y", "amount": 1},
     {"Content-Type": "application/json"}),
]


def send(method, path, body, headers):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{GATEWAY}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        return f"erreur reseau ({e})"


def main():
    print(f"[SCOPE] cible = {GATEWAY} (notre SI fictif).")
    print("Envoi de requetes hostiles ; le WAF doit repondre 403 (blocage).\n")
    blocked = 0
    for label, method, path, body, headers in CASES:
        status = send(method, path, body, headers)
        is_blocked = status in (403, 413)
        blocked += 1 if is_blocked else 0
        verdict = "BLOQUE par le WAF" if is_blocked else f"NON bloque (code {status})"
        print(f"  - {label:40s} -> {verdict}")
    print(f"\nBilan : {blocked}/{len(CASES)} requetes bloquees.")
    print("Consultez le tableau SOC (Grafana) : les evenements apparaissent tagues resilience-alpha.")


if __name__ == "__main__":
    main()
