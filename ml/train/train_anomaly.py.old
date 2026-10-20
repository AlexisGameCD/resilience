"""
Entrainement du modele de detection d'anomalie de RESILIENCE-ALPHA.

Approche : apprentissage NON supervise d'un comportement normal (pas de seuils en dur).
Le modele apprend la "forme" du trafic sain a partir d'un jeu de reference, puis signale
tout etat qui s'en ecarte. On utilise une Isolation Forest, robuste et peu gourmande,
adaptee au materiel du PC Hote.

Vecteur de caracteristiques (ordre fige, voir FEATURES) :
  req_rate      requetes/s sur payment-api
  error_ratio   part de reponses 5xx
  p95_latency   latence p95 (s)
  cpu           usage CPU du conteneur payment-api (coeurs)
  mem_mb        memoire utilisee (Mo)
  inflight      requetes simultanees en cours

Sortie : ml/model/anomaly.joblib (pipeline StandardScaler + IsolationForest + meta).

Usage : python3 ml/train/train_anomaly.py
"""
import os
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

FEATURES = ["req_rate", "error_ratio", "p95_latency", "cpu", "mem_mb", "inflight"]
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
MODEL_DIR = os.path.join(HERE, "..", "model")
RNG = np.random.default_rng(42)


def generate_normal(n=4000):
    """Genere un echantillon de trafic sain, aux correlations plausibles."""
    req_rate = np.clip(RNG.normal(5.0, 1.4, n), 0.2, None)
    # latence qui monte legerement avec la charge
    p95 = np.clip(0.10 + 0.012 * req_rate + RNG.normal(0, 0.02, n), 0.03, None)
    error_ratio = np.clip(RNG.normal(0.004, 0.004, n), 0.0, 0.05)
    cpu = np.clip(0.03 + 0.03 * req_rate + RNG.normal(0, 0.02, n), 0.0, None)
    mem_mb = np.clip(RNG.normal(140, 18, n), 80, None)
    inflight = np.clip(RNG.poisson(np.clip(req_rate * 0.3, 0.1, None)), 0, None).astype(float)
    df = pd.DataFrame({
        "req_rate": req_rate, "error_ratio": error_ratio, "p95_latency": p95,
        "cpu": cpu, "mem_mb": mem_mb, "inflight": inflight,
    })
    return df[FEATURES]


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)

    df = generate_normal()
    baseline_csv = os.path.join(DATA_DIR, "baseline.csv")
    df.to_csv(baseline_csv, index=False)
    print(f"Jeu de reference ecrit : {baseline_csv} ({len(df)} lignes)")

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("iforest", IsolationForest(
            n_estimators=200, contamination=0.02, random_state=42, n_jobs=1)),
    ])
    pipe.fit(df.values)

    # Seuil de reference : score moyen sur le jeu sain, pour l'affichage operateur.
    scores = pipe.named_steps["iforest"].score_samples(
        pipe.named_steps["scaler"].transform(df.values))
    meta = {
        "features": FEATURES,
        "trained_on": len(df),
        "score_mean_normal": float(np.mean(scores)),
        "score_p01_normal": float(np.quantile(scores, 0.01)),
        "sklearn_contract": "predict == -1 => anomalie ; score_samples bas => anormal",
    }
    model_path = os.path.join(MODEL_DIR, "anomaly.joblib")
    joblib.dump({"pipeline": pipe, "meta": meta}, model_path)
    with open(os.path.join(MODEL_DIR, "anomaly.meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Modele ecrit : {model_path}")
    print(f"Meta : {json.dumps(meta, indent=2)}")


if __name__ == "__main__":
    main()
