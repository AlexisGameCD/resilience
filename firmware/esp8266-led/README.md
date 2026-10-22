# Objet connecte ESP8266 : LED bicolore RESILIENCE-ALPHA

Firmware PlatformIO (ouvrable dans **JetBrains CLion** avec le plugin PlatformIO) pour un
ESP8266 qui reproduit sur une LED bicolore l'etat de l'authentification du back-office.

## Role

L'ESP8266 se connecte au point d'acces de la solution, interroge `led-service`
(`GET /state`) toutes les 300 ms et pilote la LED :

| Etat renvoye | LED |
| --- | --- |
| `off` | eteinte |
| `green_blink` | vert clignotant (identite reconnue, attente du mot de passe) |
| `green_on` | vert fixe (acces accorde, 30 s) |
| `red_blink` | rouge clignotant (mot de passe refuse, ~10 fois) |
| `red_on` | rouge fixe (visage non reconnu, 30 s) |

Les durees sont gerees par le serveur : l'objet ne fait qu'afficher, il reste simple et sans etat.

## Materiel

- Une carte **ESP8266** (NodeMCU v2, ou Wemos D1 mini).
- Une **LED bicolore rouge/vert, 3 broches, cathode commune** (ou deux LED separees).
- Deux resistances **220 a 330 ohm**.

## Cablage

```
 anode VERTE  --[ 220-330 ohm ]--> D1 (GPIO5)
 anode ROUGE  --[ 220-330 ohm ]--> D2 (GPIO4)
 cathode commune ------------------> GND
```

Pour une Wemos D1 mini, les alias D1/D2 sont identiques. Si votre LED est a cathode commune
cote +, inversez la logique dans `applyDisplay()` (HIGH/LOW).

## Configuration

Dans `platformio.ini`, adapter les `build_flags` :

```
-D WIFI_SSID=\"RESILIENCE-G3\"              ; votre point d'acces
-D WIFI_PASS=\"votre_mot_de_passe\"
-D LED_SERVICE_URL=\"http://192.168.137.1:8085/state\"   ; IP du PC Hote, port publie de led-service
```

L'IP est celle du PC Hote sur le point d'acces (commande `ipconfig`, adaptateur du hotspot).

## Compilation et televersement (CLion + PlatformIO)

1. CLion : **File > Open** puis selectionner ce dossier `firmware/esp8266-led` (PlatformIO le detecte via `platformio.ini`).
2. Brancher l'ESP8266 en USB.
3. Barre PlatformIO : **Build** (compile) puis **Upload** (televerse).
4. **Monitor** (115200 baud) affiche l'IP obtenue et confirme la connexion.

En ligne de commande equivalente : `pio run -t upload` puis `pio device monitor`.

## Verification

Une fois l'objet connecte et la stack lancee, declenchez le flux dans le back-office :
la LED suit chaque transition (vert clignotant, vert fixe, rouge clignotant, rouge fixe).
Le meme comportement est visible sans materiel sur le simulateur `http://localhost:8083/led.html`.
