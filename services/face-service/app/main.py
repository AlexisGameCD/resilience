"""
face-service : reconnaissance faciale legere du back-office RESILIENCE-ALPHA.

Role : apres la saisie de l'identifiant, confirmer l'identite de l'utilisateur a partir
d'une image capturee par la camera du PC Hote (via le navigateur). IA legere 100% CPU :
detecteur de visage Haar + reconnaisseur LBPH (OpenCV contrib). Aucun modele externe a
telecharger, aucun GPU.

Habilitations : enrolement et revocation administres (jeton admin). Les empreintes LBPH
sont stockees dans un volume et revocables.

Anti-abus : apres un echec, une seule nouvelle tentative, puis blocage de 5 minutes par
identifiant (conforme a la consigne additionnelle 1).

Garde-fous : le service ecrit uniquement ses propres donnees faciales, n'a aucun acces
privilegie au systeme et ne manipule aucun secret applicatif.
"""
import os
import json
import time
import base64
import shutil
import logging
import threading

import numpy as np
import cv2
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format='{"ts":"%(asctime)s","lvl":"%(levelname)s","svc":"face","msg":"%(message)s"}')
log = logging.getLogger("face")

DATA_DIR = os.getenv("FACE_DATA_DIR", "/data/faces")
CASCADE_PATH = os.getenv("FACE_CASCADE", "/app/haarcascade_frontalface_default.xml")
THRESHOLD = float(os.getenv("FACE_LBPH_THRESHOLD", "70"))    # LBPH : distance, plus bas = plus proche
MAX_FAILS = int(os.getenv("FACE_MAX_FAILS", "2"))            # 1 essai + 1 reprise avant blocage
LOCK_SECONDS = int(os.getenv("FACE_LOCK_SECONDS", "300"))    # 5 minutes
FACE_SIZE = int(os.getenv("FACE_SIZE", "200"))
ADMIN_TOKEN = os.getenv("FACE_ADMIN_TOKEN", "admin-resilience-2026")

os.makedirs(DATA_DIR, exist_ok=True)
USERS_FILE = os.path.join(DATA_DIR, "users.json")

app = FastAPI(title="RESILIENCE-ALPHA face-service", version="1.0.0")

VERIFY = Counter("face_verify_total", "Verifications faciales", ["result"])
ENROLL = Counter("face_enroll_total", "Enrolements")
USERS_G = Gauge("face_enrolled_users", "Utilisateurs habilites et enroles")

_cascade = cv2.CascadeClassifier(CASCADE_PATH)
_lock = threading.Lock()
_model = None            # cv2.face.LBPHFaceRecognizer
_label_to_user = {}      # int -> identifiant
_attempts = {}           # identifiant -> {"fails": int, "locked_until": float}


# --------------------------------------------------------------------- stockage
def _load_users():
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(users):
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    os.replace(tmp, USERS_FILE)


def _user_dir(username):
    safe = "".join(c for c in username if c.isalnum() or c in "-_.") or "x"
    return os.path.join(DATA_DIR, "u_" + safe)


# ----------------------------------------------------------------- image/visage
def _decode_image(b64):
    if not b64:
        raise HTTPException(400, "image manquante")
    if b64.strip().startswith("data:") and "," in b64:
        b64 = b64.split(",", 1)[1]
    try:
        raw = base64.b64decode(b64)
        arr = np.frombuffer(raw, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("decodage impossible")
        return img
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"image invalide : {e}")


def _extract_face(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    crop = cv2.resize(gray[y:y + h, x:x + w], (FACE_SIZE, FACE_SIZE))
    return cv2.equalizeHist(crop)


# ------------------------------------------------------------------ modele LBPH
def _retrain():
    """Reconstruit le modele LBPH a partir des echantillons des utilisateurs habilites."""
    global _model, _label_to_user
    users = _load_users()
    samples, labels, label_to_user = [], [], {}
    next_label = 0
    for username, meta in users.items():
        if not meta.get("enabled", True):
            continue
        d = _user_dir(username)
        files = [os.path.join(d, f) for f in os.listdir(d)] if os.path.isdir(d) else []
        files = [f for f in files if f.endswith(".png")]
        if not files:
            continue
        label = next_label
        next_label += 1
        label_to_user[label] = username
        for f in files:
            im = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
            if im is None:
                continue
            if im.shape != (FACE_SIZE, FACE_SIZE):
                im = cv2.resize(im, (FACE_SIZE, FACE_SIZE))
            samples.append(im)
            labels.append(label)
    if samples:
        model = cv2.face.LBPHFaceRecognizer_create()
        model.train(samples, np.array(labels))
        _model = model
    else:
        _model = None
    _label_to_user = label_to_user
    USERS_G.set(len(label_to_user))
    log.info(f"modele reconstruit : {len(label_to_user)} utilisateurs, {len(samples)} echantillons")


# --------------------------------------------------------------------- schemas
class EnrollIn(BaseModel):
    username: str
    role: str | None = "operateur"
    images: list[str]


class VerifyIn(BaseModel):
    username: str
    image: str


def _check_admin(token):
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(401, "jeton administrateur invalide")


# ---------------------------------------------------------------------- routes
@app.on_event("startup")
def _startup():
    with _lock:
        _retrain()


@app.get("/health")
def health():
    return {"status": "ok", "cascade": not _cascade.empty(),
            "model": _model is not None, "users": len(_label_to_user)}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/enroll")
def enroll(body: EnrollIn, x_admin_token: str | None = Header(default=None)):
    """Enrole (ou complete) un utilisateur a partir de plusieurs images. Reserve admin."""
    _check_admin(x_admin_token)
    username = body.username.strip()
    if not username:
        raise HTTPException(400, "identifiant vide")
    d = _user_dir(username)
    os.makedirs(d, exist_ok=True)
    added = 0
    with _lock:
        existing = len([f for f in os.listdir(d) if f.endswith(".png")])
        for b64 in body.images:
            face = _extract_face(_decode_image(b64))
            if face is None:
                continue
            cv2.imwrite(os.path.join(d, f"sample_{existing + added:03d}.png"), face)
            added += 1
        if added == 0:
            raise HTTPException(422, "aucun visage detecte dans les images fournies")
        users = _load_users()
        meta = users.get(username, {})
        meta.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        meta["role"] = body.role or meta.get("role", "operateur")
        meta["enabled"] = meta.get("enabled", True)
        meta["samples"] = existing + added
        users[username] = meta
        _save_users(users)
        _retrain()
    ENROLL.inc()
    log.info(f"enrolement {username} : +{added} visages ({existing + added} au total)")
    return {"username": username, "faces_added": added, "samples_total": existing + added}


@app.post("/verify")
def verify(body: VerifyIn):
    """Verifie un visage pour un identifiant donne, avec anti-abus (blocage 5 min)."""
    username = body.username.strip()
    now = time.time()
    st = _attempts.get(username, {"fails": 0, "locked_until": 0.0})

    if st["locked_until"] > now:
        VERIFY.labels("bloque").inc()
        return {"recognized": False, "locked": True, "retry_after": int(st["locked_until"] - now),
                "attempts_left": 0, "confidence": None, "reason": "bloque"}

    face = _extract_face(_decode_image(body.image))
    meta = _load_users().get(username)

    recognized, confidence, reason = False, None, "non_reconnu"
    if face is None:
        reason = "aucun_visage"
    elif meta is None:
        reason = "non_enrole"
    elif not meta.get("enabled", True):
        reason = "desactive"
    elif _model is None:
        reason = "modele_vide"
    else:
        label, dist = _model.predict(face)
        confidence = round(float(dist), 1)
        if _label_to_user.get(label) == username and dist <= THRESHOLD:
            recognized, reason = True, "ok"

    if recognized:
        _attempts.pop(username, None)
        VERIFY.labels("ok").inc()
        return {"recognized": True, "locked": False, "retry_after": 0,
                "attempts_left": MAX_FAILS, "confidence": confidence, "reason": "ok"}

    st["fails"] = st.get("fails", 0) + 1
    locked = st["fails"] >= MAX_FAILS
    if locked:
        st["locked_until"] = now + LOCK_SECONDS
        st["fails"] = 0
    _attempts[username] = st
    VERIFY.labels("bloque" if locked else reason).inc()
    return {"recognized": False, "locked": locked,
            "retry_after": LOCK_SECONDS if locked else 0,
            "attempts_left": 0 if locked else (MAX_FAILS - st["fails"]),
            "confidence": confidence, "reason": reason}


@app.get("/users")
def list_users(x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    users = _load_users()
    now = time.time()
    out = []
    for u, m in users.items():
        st = _attempts.get(u, {})
        out.append({"username": u, "role": m.get("role"), "enabled": m.get("enabled", True),
                    "samples": m.get("samples", 0), "created_at": m.get("created_at"),
                    "locked": st.get("locked_until", 0) > now})
    return {"users": sorted(out, key=lambda x: x["username"])}


@app.post("/users/{username}/enabled")
def set_enabled(username: str, enabled: bool = True, x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    with _lock:
        users = _load_users()
        if username not in users:
            raise HTTPException(404, "utilisateur inconnu")
        users[username]["enabled"] = enabled
        _save_users(users)
        _retrain()
    return {"username": username, "enabled": enabled}


@app.delete("/users/{username}")
def delete_user(username: str, x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    with _lock:
        users = _load_users()
        users.pop(username, None)
        _save_users(users)
        d = _user_dir(username)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
        _attempts.pop(username, None)
        _retrain()
    return {"deleted": username}


@app.post("/unlock/{username}")
def unlock(username: str, x_admin_token: str | None = Header(default=None)):
    """Leve manuellement un blocage (admin)."""
    _check_admin(x_admin_token)
    _attempts.pop(username, None)
    return {"unlocked": username}
