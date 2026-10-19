"""
Genere un trafic nominal de reference sur PayAlpha.
Sert deux usages :
  1. alimenter l'observabilite pour que le modele de detection apprenne un comportement normal ;
  2. verifier que le metier fonctionne de bout en bout.

Usage : python3 scripts/seed_traffic.py [nombre] [pause_secondes]
"""
import random
import sys
import time

from common import login, pay

N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
PAUSE = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8

USERS = [("alice", "Demo#2026", "FR76-FAKE-0001"), ("bob", "Demo#2026", "FR76-FAKE-0002")]
MERCHANTS = ["FR76-FAKE-9001", "FR76-FAKE-9002"]


def main():
    ok, ko = 0, 0
    for i in range(N):
        user, pwd, src = random.choice(USERS)
        try:
            token = login(user, pwd)
            status, data = pay(token, src=src, dst=random.choice(MERCHANTS), amount=round(random.uniform(2, 40), 2))
            if status == 201:
                ok += 1
            else:
                ko += 1
        except Exception as e:  # noqa: BLE001
            ko += 1
            print(f"[{i}] erreur : {e}")
        # Rythme irregulier pour imiter un trafic realiste
        time.sleep(PAUSE * random.uniform(0.5, 1.5))
        if (i + 1) % 20 == 0:
            print(f"progression {i+1}/{N} : {ok} reussies, {ko} echouees")
    print(f"Termine : {ok} transactions reussies, {ko} echecs.")


if __name__ == "__main__":
    main()
