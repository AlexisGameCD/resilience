"""
remediation-service : moteur de reprise autonome de RESILIENCE-ALPHA.

Chaine : recoit une alerte scoree du detection-service, selectionne les actions dans une
table de decision versionnee (playbooks.yml), puis applique un DOUBLE CHEMIN :
  1. chemin rapide : redemarrage du conteneur via l'API Portainer (reprise quasi instantanee) ;
  2. chemin audite : declenchement d'une tache Ansible via l'API Semaphore (trace best-effort).
Il PROUVE enfin la reprise par une nouvelle transaction fictive de bout en bout, et
enregistre une chronologie d'incident horodatee exposee au dashboard.

Principe de moindre privilege : le moteur ne dispose d'aucun shell. Il appelle des API
authentifiees et scopees (Portainer, Semaphore), jamais le socket Docker brut. Seul /alerts
(protege par cle) declenche une action, et seules les actions du playbook sont possibles.
"""
import os
import time
import asyncio
import logging
import uuid
import json
from collections import deque

import yaml
import httpx
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","svc":"remediation","msg":"%(message)s"}')
log = logging.getLogger("remediation")

PLAYBOOK_PATH = os.getenv("PLAYBOOK_PATH", "/app/playbooks.yml")
REM_API_KEY = os.getenv("REM_API_KEY", "")
PAYMENT_INTERNAL = os.getenv("PAYMENT_INTERNAL_URL", "http://payment-api:8000")
VERIFY_USER = os.getenv("VERIFY_USER", "alice")
VERIFY_PASS = os.getenv("VERIFY_PASS", "Demo#2026")
VERIFY_SRC = os.getenv("VERIFY_SRC", "FR76-FAKE-0001")
VERIFY_DST = os.getenv("VERIFY_DST", "FR76-FAKE-9001")

# Chemin rapide : Portainer
PORTAINER_URL = os.getenv("PORTAINER_URL", "http://portainer:9000")
PORTAINER_USER = os.getenv("PORTAINER_USER", "")
PORTAINER_PASSWORD = os.getenv("PORTAINER_PASSWORD", "")
PORTAINER_API_KEY = os.getenv("PORTAINER_API_KEY", "")
PORTAINER_EID = os.getenv("PORTAINER_ENDPOINT_ID", "1")

# Chemin audite : Semaphore
AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "true").lower() == "true"
SEMAPHORE_URL = os.getenv("SEMAPHORE_URL", "http://semaphore:3000")
SEMAPHORE_TOKEN = os.getenv("SEMAPHORE_API_TOKEN", "")
SEMAPHORE_PROJECT_ID = os.getenv("SEMAPHORE_PROJECT_ID", "")
SEMAPHORE_TEMPLATE_ID = os.getenv("SEMAPHORE_TEMPLATE_ID", "")

app = FastAPI(title="RESILIENCE-ALPHA remediation-service", version="2.0.0")

REM_TOTAL = Counter("remediation_runs_total", "Remediation declenchees", ["signature", "result"])
RTO_H = Histogram("remediation_rto_seconds", "Temps de reprise observe (s)",
                  buckets=[5, 10, 20, 30, 45, 60, 90, 120, 180, 300])
OPEN_G = Gauge("remediation_incident_open", "1 si un incident est en cours")
AUDIT_C = Counter("remediation_audit_total", "Taches d'audit Semaphore", ["result"])

PLAYBOOK = {}
INCIDENTS = deque(maxlen=50)
_lock = asyncio.Lock()


class Alert(BaseModel):
    service: str
    signature: str
    score: float
    features: dict = {}
    ts: float | None = None


def load_playbook():
    global PLAYBOOK
    with open(PLAYBOOK_PATH) as f:
        PLAYBOOK = yaml.safe_load(f)
    log.info(f"playbook charge : version {PLAYBOOK.get('version')}, "
             f"{len(PLAYBOOK.get('signatures', {}))} signatures")


# --------------------------------------------------------------- client Portainer
class Portainer:
    def __init__(self):
        self._jwt = None

    def _headers(self):
        if PORTAINER_API_KEY:
            return {"X-API-Key": PORTAINER_API_KEY}
        if self._jwt:
            return {"Authorization": f"Bearer {self._jwt}"}
        return {}

    def _login(self, client):
        if PORTAINER_API_KEY:
            return
        r = client.post(f"{PORTAINER_URL}/api/auth",
                        json={"Username": PORTAINER_USER, "Password": PORTAINER_PASSWORD}, timeout=6.0)
        r.raise_for_status()
        self._jwt = r.json()["jwt"]

    def _find_container_id(self, client, service):
        url = f"{PORTAINER_URL}/api/endpoints/{PORTAINER_EID}/docker/containers/json?all=1"
        r = client.get(url, headers=self._headers(), timeout=6.0)
        if r.status_code == 401 and not PORTAINER_API_KEY:
            self._login(client)
            r = client.get(url, headers=self._headers(), timeout=6.0)
        r.raise_for_status()
        for c in r.json():
            if c.get("Labels", {}).get("com.docker.compose.service") == service:
                return c["Id"]
        return None

    def container_action(self, service, action):
        """action in {restart, start}. Retourne (ok, message)."""
        with httpx.Client() as client:
            try:
                if not PORTAINER_API_KEY and not self._jwt:
                    self._login(client)
                cid = self._find_container_id(client, service)
                if not cid:
                    return False, f"conteneur introuvable pour {service}"
                url = f"{PORTAINER_URL}/api/endpoints/{PORTAINER_EID}/docker/containers/{cid}/{action}?t=10"
                r = client.post(url, headers=self._headers(), timeout=20.0)
                if r.status_code in (204, 304):
                    return True, f"{action} de {service} via Portainer"
                return False, f"Portainer a renvoye {r.status_code} sur {action} de {service}"
            except Exception as e:  # noqa: BLE001
                return False, f"echec Portainer ({action} {service}) : {e}"

    def ping(self):
        with httpx.Client() as client:
            try:
                r = client.get(f"{PORTAINER_URL}/api/system/status", timeout=4.0)
                return r.status_code == 200
            except Exception:  # noqa: BLE001
                return False


portainer = Portainer()


def do_action(action):
    atype = action.get("type")
    service = action.get("service")
    if atype in ("restart", "start"):
        return portainer.container_action(service, atype)
    return False, f"action inconnue : {atype}"


# --------------------------------------------------------------- audit Semaphore
async def semaphore_audit(client, incident):
    """Declenche une tache Ansible d'audit via Semaphore. Best-effort, non bloquant."""
    if not (AUDIT_ENABLED and SEMAPHORE_TOKEN and SEMAPHORE_PROJECT_ID and SEMAPHORE_TEMPLATE_ID):
        return None
    try:
        body = {
            "template_id": int(SEMAPHORE_TEMPLATE_ID),
            "debug": False,
            "dry_run": False,
            "environment": json.dumps({
                "action": "verify",
                "target_service": incident["service"],
                "incident_id": incident["id"],
            }),
        }
        r = await client.post(
            f"{SEMAPHORE_URL}/api/project/{SEMAPHORE_PROJECT_ID}/tasks",
            headers={"Authorization": f"Bearer {SEMAPHORE_TOKEN}"},
            json=body, timeout=8.0,
        )
        if r.status_code in (200, 201, 204):
            task = r.json() if r.content else {}
            AUDIT_C.labels("ok").inc()
            return task.get("id")
        AUDIT_C.labels("http_error").inc()
        log.warning(f"audit Semaphore : code {r.status_code}")
        return None
    except Exception as e:  # noqa: BLE001
        AUDIT_C.labels("error").inc()
        log.warning(f"audit Semaphore indisponible : {e}")
        return None


# --------------------------------------------------------------- verification metier
async def verify_business(client):
    try:
        r = await client.post(f"{PAYMENT_INTERNAL}/login",
                              json={"username": VERIFY_USER, "password": VERIFY_PASS}, timeout=5.0)
        if r.status_code != 200:
            return False, f"login KO ({r.status_code})"
        token = r.json()["access_token"]
        r2 = await client.post(f"{PAYMENT_INTERNAL}/payments",
                               headers={"Authorization": f"Bearer {token}"},
                               json={"src_iban": VERIFY_SRC, "dst_iban": VERIFY_DST, "amount": 1.00},
                               timeout=5.0)
        if r2.status_code == 201:
            return True, f"transaction de preuve reussie, reference {r2.json()['reference']}"
        return False, f"transaction refusee ({r2.status_code})"
    except Exception as e:  # noqa: BLE001
        return False, f"verification indisponible : {e}"


def select_actions(signature):
    sigs = PLAYBOOK.get("signatures", {})
    if signature in sigs:
        return sigs[signature]["actions"], sigs[signature].get("description", "")
    d = PLAYBOOK.get("default", {})
    return d.get("actions", []), d.get("description", "action par defaut")


async def handle_incident(alert: Alert):
    inc = {
        "id": str(uuid.uuid4())[:8],
        "service": alert.service,
        "signature": alert.signature,
        "score": alert.score,
        "features": alert.features,
        "detected_at": alert.ts or time.time(),
        "steps": [],
        "status": "acting",
        "rto_seconds": None,
        "audit_task": None,
    }
    INCIDENTS.appendleft(inc)
    OPEN_G.set(1)
    t0 = time.time()
    log.info(f"incident {inc['id']} signature={alert.signature} score={alert.score}")

    actions, desc = select_actions(alert.signature)
    inc["decision"] = desc

    # 1. Chemin rapide : Portainer
    for action in actions:
        ok, msg = do_action(action)
        inc["steps"].append({"ts": time.time(), "type": "action", "detail": msg, "ok": ok})
        log.info(f"incident {inc['id']} action : {msg} (ok={ok})")

    async with httpx.AsyncClient() as client:
        # 2. Chemin audite : Semaphore (best-effort, n'affecte pas le RTO)
        task_id = await semaphore_audit(client, inc)
        if task_id is not None:
            inc["audit_task"] = task_id
            inc["steps"].append({"ts": time.time(), "type": "audit",
                                 "detail": f"tache d'audit Semaphore #{task_id} declenchee", "ok": True})

        # 3. Verification de reprise
        inc["status"] = "verifying"
        timeout = PLAYBOOK.get("verification", {}).get("health_timeout_seconds", 60)
        resolved = False
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                h = await client.get(f"{PAYMENT_INTERNAL}/health", timeout=4.0)
                if h.status_code == 200:
                    ok, msg = await verify_business(client)
                    inc["steps"].append({"ts": time.time(), "type": "verification", "detail": msg, "ok": ok})
                    if ok:
                        resolved = True
                        break
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(3)

    inc["rto_seconds"] = round(time.time() - t0, 1)
    if resolved:
        inc["status"] = "resolved"
        RTO_H.observe(inc["rto_seconds"])
        REM_TOTAL.labels(alert.signature, "resolved").inc()
        log.info(f"incident {inc['id']} resolu en {inc['rto_seconds']} s")
    else:
        inc["status"] = "failed"
        REM_TOTAL.labels(alert.signature, "failed").inc()
        log.error(f"incident {inc['id']} non resolu dans le delai imparti")
    OPEN_G.set(0)
    return inc


@app.on_event("startup")
def startup():
    load_playbook()


@app.get("/health")
def health():
    ok = portainer.ping()
    return {"status": "ok" if ok else "degraded",
            "portainer": ok, "audit_enabled": AUDIT_ENABLED,
            "playbook_version": PLAYBOOK.get("version")}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/alerts", status_code=202)
async def alerts(alert: Alert, x_api_key: str | None = Header(default=None)):
    if REM_API_KEY and x_api_key != REM_API_KEY:
        raise HTTPException(status_code=401, detail="cle d'appel invalide")
    if _lock.locked():
        raise HTTPException(status_code=409, detail="remediation deja en cours")
    async with _lock:
        inc = await handle_incident(alert)
    return {"incident": inc}


@app.get("/incidents")
def incidents():
    return {"incidents": list(INCIDENTS)}


@app.get("/state")
def state():
    current = INCIDENTS[0] if INCIDENTS else None
    return {"open": bool(current and current["status"] in ("acting", "verifying")),
            "current": current, "count": len(INCIDENTS)}
