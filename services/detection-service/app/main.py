"""
detection-service : detection d'anomalie par machine learning.

Principe : interroge Prometheus toutes les N secondes, construit un vecteur de
caracteristiques du service payment-api, le score avec une Isolation Forest apprise
sur un comportement normal (pas de seuils en dur), et declenche une alerte vers le
moteur de remediation quand l'etat s'ecarte durablement de la normale.

Cas particulier : si le service est injoignable (up == 0), l'indisponibilite est traitee
comme une anomalie forte immediate (signature dediee), sans attendre le modele.

Expose : /health /metrics /state (pour le dashboard) /score (a la demande).
"""
import os
import time
import asyncio
import logging
from collections import deque

import httpx
import numpy as np
import joblib
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","svc":"detection","msg":"%(message)s"}')
log = logging.getLogger("detection")

PROM = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
REMEDIATION_URL = os.getenv("REMEDIATION_URL", "http://remediation-service:8000")
REM_API_KEY = os.getenv("REM_API_KEY", "")
MODEL_PATH = os.getenv("MODEL_PATH", "/models/anomaly.joblib")
INTERVAL = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "15"))
TARGET = "payment-api"

FEATURES = ["req_rate", "error_ratio", "p95_latency", "cpu", "mem_mb", "inflight"]

# Requetes PromQL par caracteristique
QUERIES = {
    "req_rate": f'sum(rate(http_requests_total{{service="{TARGET}"}}[1m]))',
    "error_ratio": (f'sum(rate(http_requests_total{{service="{TARGET}",status=~"5.."}}[1m]))'
                    f' / clamp_min(sum(rate(http_requests_total{{service="{TARGET}"}}[1m])), 0.001)'),
    "p95_latency": (f'histogram_quantile(0.95, sum(rate('
                    f'http_request_duration_seconds_bucket{{service="{TARGET}"}}[1m])) by (le))'),
    "cpu": f'sum(rate(container_cpu_usage_seconds_total{{container_label_com_docker_compose_service="{TARGET}"}}[1m]))',
    "mem_mb": f'sum(container_memory_usage_bytes{{container_label_com_docker_compose_service="{TARGET}"}}) / 1e6',
    "inflight": f'sum(http_inflight_requests{{service="{TARGET}"}})',
    "up": f'max(up{{service="{TARGET}"}})',
}

# Valeurs de repli si une metrique est absente (etat sain par defaut)
DEFAULTS = {"req_rate": 1.0, "error_ratio": 0.0, "p95_latency": 0.1,
            "cpu": 0.1, "mem_mb": 140.0, "inflight": 1.0, "up": 1.0}

app = FastAPI(title="RESILIENCE-ALPHA detection-service", version="1.0.0")

SCORE_G = Gauge("detection_anomaly_score", "Score d'anomalie courant (bas = anormal)")
ANOM_G = Gauge("detection_anomaly_flag", "1 si anomalie detectee, 0 sinon")
ALERTS = Counter("detection_alerts_total", "Alertes envoyees", ["signature"])

STATE = {
    "model_source": "unknown",
    "threshold": -0.60,
    "last": None,
    "history": deque(maxlen=120),
    "open_incident": False,
}
_consecutive = 0
_model = None


# ----------------------------------------------------------------------- modele
def _synthetic_normal(n=4000):
    rng = np.random.default_rng(42)
    req = np.clip(rng.normal(5.0, 1.4, n), 0.2, None)
    p95 = np.clip(0.10 + 0.012 * req + rng.normal(0, 0.02, n), 0.03, None)
    err = np.clip(rng.normal(0.004, 0.004, n), 0.0, 0.05)
    cpu = np.clip(0.03 + 0.03 * req + rng.normal(0, 0.02, n), 0.0, None)
    mem = np.clip(rng.normal(140, 18, n), 80, None)
    inf = np.clip(rng.poisson(np.clip(req * 0.3, 0.1, None)), 0, None).astype(float)
    return np.column_stack([req, err, p95, cpu, mem, inf])


def _fallback_train():
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    X = _synthetic_normal()
    pipe = Pipeline([("scaler", StandardScaler()),
                     ("iforest", IsolationForest(n_estimators=200, contamination=0.02,
                                                 random_state=42, n_jobs=1))])
    pipe.fit(X)
    scores = pipe.score_samples(X)
    meta = {"features": FEATURES, "score_p01_normal": float(np.quantile(scores, 0.01))}
    return {"pipeline": pipe, "meta": meta}


def load_model():
    global _model
    try:
        bundle = joblib.load(MODEL_PATH)
        STATE["model_source"] = "fichier pre-entraine"
        log.info("modele charge depuis le fichier")
    except Exception as e:  # noqa: BLE001
        log.warning(f"chargement du modele impossible ({e}) : repli par auto-entrainement")
        bundle = _fallback_train()
        STATE["model_source"] = "auto-entraine (repli)"
    _model = bundle["pipeline"]
    STATE["threshold"] = float(bundle["meta"].get("score_p01_normal", -0.60))


# ----------------------------------------------------------------------- prometheus
async def _query(client, promql):
    try:
        r = await client.get(f"{PROM}/api/v1/query", params={"query": promql}, timeout=5.0)
        data = r.json()
        res = data.get("data", {}).get("result", [])
        if not res:
            return None
        val = float(res[0]["value"][1])
        if np.isnan(val) or np.isinf(val):
            return None
        return val
    except Exception:  # noqa: BLE001
        return None


async def collect(client):
    feats = {}
    for key, q in QUERIES.items():
        v = await _query(client, q)
        feats[key] = DEFAULTS[key] if v is None else v
    return feats


def classify(feats):
    """Retourne (is_anomaly, signature, score)."""
    if feats["up"] < 0.5:
        return True, f"{TARGET}_unavailable", -1.0
    vec = np.array([[feats[f] for f in FEATURES]])
    score = float(_model.score_samples(vec)[0])
    pred = int(_model.predict(vec)[0])
    is_anom = (pred == -1) or (score < STATE["threshold"])
    if not is_anom:
        return False, "nominal", score
    if feats["error_ratio"] > 0.2 or feats["p95_latency"] > 1.0:
        sig = f"{TARGET}_degraded"
    else:
        sig = f"{TARGET}_anomaly"
    return True, sig, score


async def send_alert(client, signature, score, feats):
    payload = {"service": TARGET, "signature": signature, "score": round(score, 4),
               "features": {k: round(v, 4) for k, v in feats.items()}, "ts": time.time()}
    headers = {"X-API-Key": REM_API_KEY} if REM_API_KEY else {}
    try:
        await client.post(f"{REMEDIATION_URL}/alerts", json=payload, headers=headers, timeout=20.0)
        ALERTS.labels(signature).inc()
        log.info(f"alerte envoyee signature={signature} score={score:.3f}")
    except Exception as e:  # noqa: BLE001
        log.error(f"envoi d'alerte impossible : {e}")


async def detection_loop():
    global _consecutive
    async with httpx.AsyncClient() as client:
        while True:
            try:
                feats = await collect(client)
                is_anom, sig, score = classify(feats)
                SCORE_G.set(score)
                ANOM_G.set(1 if is_anom else 0)
                entry = {"ts": time.time(), "score": round(score, 4),
                         "anomaly": is_anom, "signature": sig,
                         "features": {k: round(v, 3) for k, v in feats.items()}}
                STATE["last"] = entry
                STATE["history"].append(entry)

                if is_anom:
                    _consecutive += 1
                    # Debounce : 2 cycles consecutifs avant d'alerter, pas de re-alerte si incident ouvert
                    if _consecutive >= 2 and not STATE["open_incident"]:
                        STATE["open_incident"] = True
                        await send_alert(client, sig, score, feats)
                else:
                    _consecutive = 0
                    STATE["open_incident"] = False
            except Exception as e:  # noqa: BLE001
                log.error(f"boucle de detection : {e}")
            await asyncio.sleep(INTERVAL)


@app.on_event("startup")
async def startup():
    load_model()
    asyncio.create_task(detection_loop())


@app.get("/health")
def health():
    return {"status": "ok", "model": STATE["model_source"], "threshold": STATE["threshold"]}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/state")
def state():
    return {
        "model_source": STATE["model_source"],
        "threshold": STATE["threshold"],
        "open_incident": STATE["open_incident"],
        "last": STATE["last"],
        "history": list(STATE["history"]),
    }


@app.get("/score")
async def score_now():
    async with httpx.AsyncClient() as client:
        feats = await collect(client)
    is_anom, sig, score = classify(feats)
    return {"anomaly": is_anom, "signature": sig, "score": round(score, 4), "features": feats}
