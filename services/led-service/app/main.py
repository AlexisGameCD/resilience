"""
led-service : etat logique de la LED bicolore du back-office RESILIENCE-ALPHA.

Le back-office POST l'etat a chaque transition d'authentification ; le simulateur a
l'ecran et l'objet connecte ESP8266 interrogent GET /state et affichent le motif
correspondant. Les etats temporises (vert fixe 30 s, rouge fixe 30 s, rouge clignotant
10 fois) expirent automatiquement cote serveur, ce qui garde le peripherique simple :
il se contente d'afficher l'etat courant.

Etats acceptes (POST par le back-office) :
  off            LED eteinte (defaut)
  green_blink    vert clignotant (identite reconnue, en attente du mot de passe)
  green_30s      vert fixe 30 s puis extinction (mot de passe valide)
  red_blink_10   rouge clignotant ~10 fois puis extinction (mauvais mot de passe)
  red_30s        rouge fixe 30 s puis extinction (visage non reconnu)
"""
import os
import time
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","svc":"led","msg":"%(message)s"}')
log = logging.getLogger("led")

BLINK_MS = int(os.getenv("LED_BLINK_MS", "500"))
# Duree des etats temporises (secondes) ; les autres restent jusqu'au prochain POST.
DURATIONS = {"green_30s": 30.0, "red_30s": 30.0, "red_blink_10": BLINK_MS / 1000.0 * 10}
ALLOWED = {"off", "green_blink", "green_30s", "red_30s", "red_blink_10"}
DISPLAY = {"off": "off", "green_blink": "green_blink", "green_30s": "green_on",
           "red_30s": "red_on", "red_blink_10": "red_blink"}

app = FastAPI(title="RESILIENCE-ALPHA led-service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
CHANGES = Counter("led_state_changes_total", "Changements d'etat de la LED", ["mode"])

_state = {"mode": "off", "since": time.time()}


def _display():
    mode = _state["mode"]
    elapsed = time.time() - _state["since"]
    dur = DURATIONS.get(mode)
    if dur is not None and elapsed > dur:
        return "off", mode, elapsed
    return DISPLAY[mode], mode, elapsed


class StateIn(BaseModel):
    mode: str


@app.get("/health")
def health():
    d, _, _ = _display()
    return {"status": "ok", "display": d, "mode": _state["mode"]}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/state")
def set_state(body: StateIn):
    if body.mode not in ALLOWED:
        raise HTTPException(400, f"etat inconnu : {body.mode}")
    _state["mode"] = body.mode
    _state["since"] = time.time()
    CHANGES.labels(body.mode).inc()
    log.info(f"etat LED -> {body.mode}")
    d, _, _ = _display()
    return {"ok": True, "mode": body.mode, "display": d}


@app.get("/state")
def get_state():
    """Etat d'affichage courant, interroge par le simulateur et par l'ESP8266."""
    d, mode, elapsed = _display()
    return {"display": d, "mode": mode, "elapsed_ms": int(elapsed * 1000), "blink_ms": BLINK_MS}
