"""Utilitaires partages par les scripts de demonstration (stdlib uniquement)."""
import json
import os
import urllib.request
import urllib.error

# Point d'entree des API : toujours via le WAF (jamais directement payment-api)
GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")


def _request(method, url, body=None, headers=None, timeout=8.0):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read().decode()
            return r.status, (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as e:
        payload = e.read().decode()
        try:
            return e.code, json.loads(payload)
        except json.JSONDecodeError:
            return e.code, {"detail": payload}
    except urllib.error.URLError as e:
        return 0, {"detail": str(e.reason)}


def login(username="alice", password="Demo#2026"):
    status, data = _request("POST", f"{GATEWAY}/login", {"username": username, "password": password})
    if status != 200:
        raise RuntimeError(f"login echoue ({status}): {data.get('detail')}")
    return data["access_token"]


def pay(token, src="FR76-FAKE-0001", dst="FR76-FAKE-9001", amount=12.50):
    return _request("POST", f"{GATEWAY}/payments",
                    {"src_iban": src, "dst_iban": dst, "amount": amount},
                    headers={"Authorization": f"Bearer {token}"})


def health():
    return _request("GET", f"{GATEWAY}/health")
