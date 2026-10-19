"""
Tests d'integration sur la plateforme en fonctionnement.
Necessitent que la stack soit demarree (make up). Sinon les tests sont ignores.

Lancer : pytest tests/test_integration.py
Variables : GATEWAY_URL (defaut http://localhost:8080), DASHBOARD_URL (defaut http://localhost:8082)
"""
import os
import json
import urllib.request
import urllib.error
import pytest

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")
DASHBOARD = os.getenv("DASHBOARD_URL", "http://localhost:8082")


def _req(method, url, body=None, headers=None, timeout=8):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read().decode()
            return r.status, (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as e:
        payload = e.read().decode()
        try:
            return e.code, json.loads(payload)
        except json.JSONDecodeError:
            return e.code, {"raw": payload}
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"plateforme non joignable : {e}")


def test_health():
    status, data = _req("GET", f"{GATEWAY}/health")
    assert status == 200
    assert data.get("status") == "ok"


def test_login_and_payment():
    status, data = _req("POST", f"{GATEWAY}/login",
                        {"username": "alice", "password": "Demo#2026"})
    assert status == 200
    token = data["access_token"]
    status, tx = _req("POST", f"{GATEWAY}/payments",
                      {"src_iban": "FR76-FAKE-0001", "dst_iban": "FR76-FAKE-9001", "amount": 3.14},
                      headers={"Authorization": f"Bearer {token}"})
    assert status == 201
    assert tx["status"] == "posted"


def test_payment_requires_auth():
    status, _ = _req("POST", f"{GATEWAY}/payments",
                     {"src_iban": "FR76-FAKE-0001", "dst_iban": "FR76-FAKE-9001", "amount": 1})
    assert status == 401


def test_waf_blocks_sql_injection():
    status, _ = _req("POST", f"{GATEWAY}/payments",
                     {"src_iban": "FR76-FAKE-0001' OR '1'='1", "dst_iban": "x", "amount": 1})
    assert status in (403, 413)


def test_dashboard_detection_reachable():
    status, data = _req("GET", f"{DASHBOARD}/api/detection/state")
    assert status == 200
    assert "threshold" in data
