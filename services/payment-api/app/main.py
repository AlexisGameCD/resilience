"""
payment-api : API metier de PayAlpha (plateforme de paiement fictive).

Fonctions :
  POST /login            delegue l'authentification a auth-service, renvoie un JWT
  POST /payments         initie une transaction fictive (JWT requis)
  GET  /payments/{ref}   consulte une transaction
  GET  /accounts/{iban}  consulte un compte fictif
  GET  /stats            compteurs recents (pour le dashboard)
  GET  /health /metrics  sante et metriques Prometheus

Aucune donnee reelle. Le moteur agit uniquement sur des comptes fictifs.
"""
import os
import time
import logging
from decimal import Decimal

import jwt
import httpx
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","svc":"payment-api","msg":"%(message)s"}')
log = logging.getLogger("payment-api")

DATABASE_URL = os.getenv("DATABASE_URL", "")
AUTH_URL = os.getenv("AUTH_URL", "http://auth-service:8000")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)

app = FastAPI(title="PayAlpha payment-api", version="1.0.0")

REQS = Counter("http_requests_total", "Requetes HTTP", ["service", "method", "path", "status"])
LAT = Histogram("http_request_duration_seconds", "Latence HTTP", ["service", "path"])
TX_OK = Counter("payment_tx_success_total", "Transactions reussies")
TX_KO = Counter("payment_tx_failed_total", "Transactions echouees", ["reason"])
INFLIGHT = Gauge("http_inflight_requests", "Requetes en cours", ["service"])


class PaymentIn(BaseModel):
    src_iban: str = Field(..., examples=["FR76-FAKE-0001"])
    dst_iban: str = Field(..., examples=["FR76-FAKE-9001"])
    amount: Decimal = Field(..., gt=0, examples=[12.50])


class LoginIn(BaseModel):
    username: str
    password: str


def _normalize_path(request: Request) -> str:
    # Regroupe les chemins parametres pour limiter la cardinalite des metriques
    p = request.url.path
    if p.startswith("/payments/"):
        return "/payments/{ref}"
    if p.startswith("/accounts/"):
        return "/accounts/{iban}"
    return p


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    path = _normalize_path(request)
    INFLIGHT.labels("payment-api").inc()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        REQS.labels("payment-api", request.method, path, status).inc()
        LAT.labels("payment-api", path).observe(time.perf_counter() - start)
        INFLIGHT.labels("payment-api").dec()
        raise
    REQS.labels("payment-api", request.method, path, status).inc()
    LAT.labels("payment-api", path).observe(time.perf_counter() - start)
    INFLIGHT.labels("payment-api").dec()
    return response


@app.get("/health")
def health():
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return {"status": "ok", "db": True}
    except Exception as e:  # noqa: BLE001
        log.warning(f"health degraded: {e}")
        raise HTTPException(status_code=503, detail="base indisponible")


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/login")
def login(body: LoginIn):
    try:
        r = httpx.post(f"{AUTH_URL}/login", json=body.model_dump(), timeout=5.0)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="service d'authentification indisponible")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="identifiants invalides")
    return r.json()


def _require_user(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="jeton manquant")
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer="payalpha-auth")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="jeton expire")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="jeton invalide")


@app.post("/payments", status_code=201)
def create_payment(body: PaymentIn, authorization: str | None = Header(default=None)):
    _require_user(authorization)
    amount = Decimal(body.amount).quantize(Decimal("0.01"))
    try:
        with engine.begin() as c:
            # Verrouillage des comptes concernes pour une operation atomique
            src = c.execute(
                text("SELECT iban_fake, balance FROM accounts WHERE iban_fake=:i FOR UPDATE"),
                {"i": body.src_iban},
            ).fetchone()
            dst = c.execute(
                text("SELECT iban_fake, balance FROM accounts WHERE iban_fake=:i FOR UPDATE"),
                {"i": body.dst_iban},
            ).fetchone()
            if src is None or dst is None:
                TX_KO.labels("unknown_account").inc()
                raise HTTPException(status_code=404, detail="compte fictif inconnu")
            if src.balance < amount:
                TX_KO.labels("insufficient_funds").inc()
                raise HTTPException(status_code=422, detail="solde insuffisant")
            c.execute(text("UPDATE accounts SET balance = balance - :a WHERE iban_fake=:i"),
                      {"a": amount, "i": body.src_iban})
            c.execute(text("UPDATE accounts SET balance = balance + :a WHERE iban_fake=:i"),
                      {"a": amount, "i": body.dst_iban})
            ref = c.execute(
                text("""INSERT INTO transactions (src_iban, dst_iban, amount, status)
                        VALUES (:s, :d, :a, 'posted') RETURNING reference"""),
                {"s": body.src_iban, "d": body.dst_iban, "a": amount},
            ).fetchone()
        TX_OK.inc()
        log.info(f"tx ok ref={ref.reference} amount={amount}")
        return {"reference": str(ref.reference), "status": "posted", "amount": str(amount)}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        TX_KO.labels("internal").inc()
        log.error(f"tx internal error: {e}")
        raise HTTPException(status_code=500, detail="erreur de traitement")


@app.get("/payments/{reference}")
def get_payment(reference: str):
    with engine.connect() as c:
        row = c.execute(
            text("SELECT reference, src_iban, dst_iban, amount, status, created_at FROM transactions WHERE reference=:r"),
            {"r": reference},
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="transaction inconnue")
    return {
        "reference": str(row.reference), "src_iban": row.src_iban, "dst_iban": row.dst_iban,
        "amount": str(row.amount), "status": row.status, "created_at": row.created_at.isoformat(),
    }


@app.get("/accounts/{iban}")
def get_account(iban: str):
    with engine.connect() as c:
        row = c.execute(text("SELECT owner, iban_fake, balance FROM accounts WHERE iban_fake=:i"), {"i": iban}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="compte inconnu")
    return {"owner": row.owner, "iban_fake": row.iban_fake, "balance": str(row.balance)}


@app.get("/stats")
def stats():
    with engine.connect() as c:
        last_min = c.execute(
            text("SELECT count(*) FROM transactions WHERE created_at > now() - interval '1 minute'")
        ).scalar()
        total = c.execute(text("SELECT count(*) FROM transactions")).scalar()
    return {"tx_last_minute": int(last_min), "tx_total": int(total)}
