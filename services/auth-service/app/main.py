"""
auth-service : service d'authentification de PayAlpha.
Emet des jetons JWT a duree limitee pour des comptes fictifs.
Expose /login, /verify, /health et /metrics (Prometheus).

Aucune donnee reelle. Les identifiants sont fictifs et servent la demonstration.
"""
import os
import time
import logging

import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","svc":"auth","msg":"%(message)s"}')
log = logging.getLogger("auth")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_TTL = int(os.getenv("JWT_TTL_SECONDS", "900"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None

app = FastAPI(title="PayAlpha auth-service", version="1.0.0")

REQS = Counter("http_requests_total", "Requetes HTTP", ["service", "method", "path", "status"])
LAT = Histogram("http_request_duration_seconds", "Latence HTTP", ["service", "path"])
LOGIN_FAIL = Counter("auth_login_failed_total", "Echecs d'authentification", ["reason"])


class LoginIn(BaseModel):
    username: str
    password: str


class VerifyIn(BaseModel):
    token: str


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    start = time.perf_counter()
    path = request.url.path
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        REQS.labels("auth", request.method, path, status).inc()
        LAT.labels("auth", path).observe(time.perf_counter() - start)
        raise
    REQS.labels("auth", request.method, path, status).inc()
    LAT.labels("auth", path).observe(time.perf_counter() - start)
    return response


@app.get("/health")
def health():
    db_ok = True
    if engine is not None:
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
        except Exception as e:  # noqa: BLE001
            db_ok = False
            log.warning(f"health db degraded: {e}")
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _find_user(username: str):
    if engine is None:
        return None
    with engine.connect() as c:
        row = c.execute(
            text("SELECT username, password_hash, role FROM auth_users WHERE username = :u"),
            {"u": username},
        ).fetchone()
    return row


@app.post("/login")
def login(body: LoginIn):
    row = _find_user(body.username)
    if row is None:
        LOGIN_FAIL.labels("unknown_user").inc()
        raise HTTPException(status_code=401, detail="identifiants invalides")
    try:
        ok = bcrypt.checkpw(body.password.encode("utf-8"), row.password_hash.encode("utf-8"))
    except ValueError:
        ok = False
    if not ok:
        LOGIN_FAIL.labels("bad_password").inc()
        raise HTTPException(status_code=401, detail="identifiants invalides")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": row.username,
        "role": row.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=JWT_TTL)).timestamp()),
        "iss": "payalpha-auth",
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    log.info(f"login ok user={row.username} role={row.role}")
    return {"access_token": token, "token_type": "bearer", "expires_in": JWT_TTL}


@app.post("/verify")
def verify(body: VerifyIn):
    try:
        claims = jwt.decode(body.token, JWT_SECRET, algorithms=["HS256"], issuer="payalpha-auth")
        return {"valid": True, "sub": claims["sub"], "role": claims.get("role", "user")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="jeton expire")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="jeton invalide")
