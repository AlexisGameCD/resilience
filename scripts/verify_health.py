"""
Verifie la sante de bout en bout de PayAlpha :
  1. l'API repond (via le WAF) ;
  2. une transaction fictive aboutit.

Usage : python3 scripts/verify_health.py
Code de sortie 0 si tout est vert, 1 sinon.
"""
import sys
from common import health, login, pay


def main():
    status, data = health()
    if status != 200:
        print(f"KO : /health renvoie {status} ({data.get('detail')})")
        return 1
    print(f"OK : service en bonne sante ({data})")
    try:
        token = login()
        s, d = pay(token, amount=1.00)
        if s == 201:
            print(f"OK : transaction de controle reussie, reference {d['reference']}")
            return 0
        print(f"KO : transaction de controle refusee ({s}) : {d.get('detail')}")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"KO : chaine metier indisponible ({e})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
