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


def generate_normal(n=6000):
    """Genere un echantillon de trafic sain couvrant trois regimes reels :
    repos, trafic leger et trafic soutenu. Ainsi le modele considere aussi
    l'etat au repos comme normal et ne reagit qu'aux vrais ecarts."""
    a = n // 3
    b = n // 3
    c = n - a - b
    req_rate = np.concatenate([
        RNG.uniform(0.05, 0.6, a),   # repos (peu ou pas de trafic)
        RNG.uniform(0.6, 3.0, b),    # trafic leger
        RNG.uniform(3.0, 9.0, c),    # trafic soutenu
    ])
    RNG.shuffle(req_rate)
    # Caracteristiques correlees a la charge.
    p95 = np.clip(0.006 + 0.014 * req_rate + RNG.normal(0, 0.008, n), 0.003, None)
    error_ratio = np.clip(RNG.normal(0.003, 0.004, n), 0.0, 0.04)
    cpu = np.clip(0.07 + 0.02 * req_rate + RNG.normal(0, 0.012, n), 0.02, None)
    mem_mb = np.clip(RNG.normal(140, 15, n), 90, None)
    inflight = np.clip(RNG.poisson(np.clip(0.7 + 0.3 * req_rate, 0.2, None)), 0, None).astype(float)
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
            n_estimators=250, contamination=0.01, random_state=42, n_jobs=1)),
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
