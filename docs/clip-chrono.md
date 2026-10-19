# Clip Chrono : script de scene (60 secondes, sans coupe)

Objectif : montrer en une sequence continue l'attaque, l'apparition de l'anomalie, la
reaction du systeme et la verification du service retabli. La capture doit etre realisee
sans coupe permettant de masquer une action manuelle. Les titres et sous-titres sont
autorises pour rendre la demonstration comprehensible.

## Preparation (avant de lancer l'enregistrement)

- Plateforme demarree et trafic de reference injecte (make up, make seed).
- Deux zones visibles a l'ecran : le dashboard de supervision (http://localhost:8082) et un terminal sur le PC Attaquant.
- Capture d'ecran continue (par exemple OBS) a 1080p, 30 images/s.
- Repeter la sequence une fois a blanc pour tenir les 60 secondes.

## Decoupage seconde par seconde

| Temps | A l'ecran | Titre a afficher |
| --- | --- | --- |
| 0 a 8 s | Front de paiement : une transaction fictive reussit. Dashboard vert. | "Etat normal : le service fonctionne" |
| 8 a 20 s | PC Attaquant : lancement du scenario (make attack-load ou attack-stop). | "Incident provoque depuis le PC Attaquant" |
| 20 a 33 s | Dashboard : le score d'anomalie bascule, l'etat passe au rouge. | "Detection par machine learning" |
| 33 a 48 s | Dashboard : la chronologie d'incident montre l'action et le redemarrage. | "Remediation automatique, sans intervention" |
| 48 a 58 s | Nouvelle transaction fictive : succes. Dashboard repasse au vert. | "Reprise prouvee : nouvelle transaction reussie" |
| 58 a 60 s | Plan final fixe sur le dashboard vert. | "RESILIENCE-ALPHA" |

## Points de vigilance

- Ne jamais couper la capture entre l'attaque et la reprise : c'est la continuite qui prouve l'autonomie.
- Aucune main sur le clavier entre la detection et la verification : la reprise doit etre automatique.
- Garder le dashboard lisible a distance (zoom suffisant, contrastes).
- Si Ollama n'est pas disponible, l'assistant affiche un message ; cela n'affecte pas la chaine de reprise.

## Montage

- Ajouter les titres en surimpression en post-production (autorise).
- Ne pas accelerer ni masquer un segment : la lecture doit rester fidele a la realite.
- Exporter en MP4, 60 secondes maximum, sous le nom Workshop2026-M2-G<n>-VidChrono.mp4.
