"""
Tests unitaires du modele de detection (hors infrastructure).
Verifient que le modele distingue un etat sain d'un etat anormal.

Lancer : pytest tests/test_model.py
"""
import os
import numpy as np
import joblib
import pytest

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "model", "anomaly.joblib")
FEATURES = ["req_rate", "error_ratio", "p95_latency", "cpu", "mem_mb", "inflight"]


@pytest.fixture(scope="module")
def pipeline():
    if not os.path.exists(MODEL_PATH):
        pytest.skip("modele absent : lancer `make train` d'abord")
    bundle = joblib.load(MODEL_PATH)
    return bundle["pipeline"]


def test_normal_is_not_anomaly(pipeline):
    normal = np.array([[5.0, 0.004, 0.16, 0.18, 140, 2]])
    assert pipeline.predict(normal)[0] == 1


def test_saturation_is_anomaly(pipeline):
    # latence et erreurs tres hautes, charge anormale
    anom = np.array([[25.0, 0.6, 3.2, 0.95, 320, 40]])
    assert pipeline.predict(anom)[0] == -1


def test_anomaly_score_lower_than_normal(pipeline):
    normal = np.array([[5.0, 0.004, 0.16, 0.18, 140, 2]])
    anom = np.array([[25.0, 0.6, 3.2, 0.95, 320, 40]])
    assert pipeline.score_samples(anom)[0] < pipeline.score_samples(normal)[0]
