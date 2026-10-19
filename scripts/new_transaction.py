"""
Joue une unique transaction fictive et affiche sa reference.
C'est la PREUVE de reprise : apres remediation, cette transaction doit reussir.

Usage : python3 scripts/new_transaction.py
Code de sortie 0 si la transaction aboutit, 1 sinon.
"""
import sys
from common import login, pay


def main():
    try:
        token = login()
    except Exception as e:  # noqa: BLE001
        print(f"KO : authentification impossible ({e})")
        return 1
    status, data = pay(token, amount=9.99)
    if status == 201:
        print(f"OK : transaction reussie, reference {data['reference']} pour {data['amount']} EUR")
        return 0
    print(f"KO : transaction refusee ({status}) : {data.get('detail')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
