"""
Scenario 3 : arret d'un conteneur (panne simulee, chaos engineering).

But : couper brutalement le service payment-api pour simuler une panne. La detection doit
voir l'indisponibilite (up == 0) et la remediation redemarrer le conteneur automatiquement.

Particularite : ce scenario s'execute SUR LE PC HOTE (il agit sur Docker local), a la
difference des scenarios reseau lances depuis le PC Attaquant. C'est une injection de
defaillance maitrisee, pas une intervention corrective (la reprise, elle, reste automatique).

Usage :
  python3 attack/scenarios/container_stop.py            (demande confirmation)
  python3 attack/scenarios/container_stop.py --yes      (sans confirmation)
"""
import subprocess
import sys

SERVICE = "payment-api"


def main():
    auto = "--yes" in sys.argv
    print(f"[CHAOS] Ce scenario va ARRETER le conteneur {SERVICE} (action reversible).")
    print("La remediation automatique doit ensuite le relancer sans intervention humaine.")
    if not auto:
        c = input("Confirmer l'arret ? [tapez OUI] : ")
        if c.strip() != "OUI":
            print("Annule.")
            return 1
    try:
        subprocess.run(["docker", "compose", "stop", SERVICE], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Echec de l'arret : {e}")
        return 1
    print(f"{SERVICE} arrete. Observez le dashboard : detection (indisponible) puis reprise auto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
