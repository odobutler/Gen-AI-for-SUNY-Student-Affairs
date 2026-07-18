"""Train a home-value regression model.

Examples
--------
Train on synthetic data (no real dataset needed for a demo run):
    python -m home_value_prediction.train --synthetic-samples 5000

Train on a real CSV export (e.g. county assessor / Zillow-style data) that
has the columns listed in home_value_prediction/config.py plus a `price`
column:
    python -m home_value_prediction.train --data data/my_housing_data.csv
"""

from __future__ import annotations

import argparse

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

from .config import FEATURE_COLUMNS, TARGET_COLUMN
from .data_generator import generate_synthetic_housing_data
from .evaluate import compute_metrics, format_metrics
from .model_utils import save_metrics, save_pipeline
from .preprocessing import build_preprocessor

MODEL_FACTORIES = {
    "rf": lambda seed: RandomForestRegressor(
        n_estimators=300, max_depth=None, min_samples_leaf=2, n_jobs=-1, random_state=seed
    ),
    "gbr": lambda seed: GradientBoostingRegressor(
        n_estimators=300, learning_rate=0.05, max_depth=3, random_state=seed
    ),
}


def load_data(args: argparse.Namespace) -> pd.DataFrame:
    if args.data:
        df = pd.read_csv(args.data)
        missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in df.columns]
        if missing:
            raise ValueError(f"Input data is missing required columns: {missing}")
        return df
    return generate_synthetic_housing_data(n_samples=args.synthetic_samples, seed=args.random_state)


def build_pipeline(model_name: str, random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("model", MODEL_FACTORIES[model_name](random_state)),
        ]
    )


def select_best_model(X_train, y_train, random_state: int, cv: int = 5) -> str:
    """Pick the model with the best mean cross-validated R2."""
    best_name, best_score = None, -float("inf")
    for name in MODEL_FACTORIES:
        pipeline = build_pipeline(name, random_state)
        scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="r2", n_jobs=-1)
        mean_score = scores.mean()
        print(f"  [{name}] cross-val R2: {mean_score:.4f} (+/- {scores.std():.4f})")
        if mean_score > best_score:
            best_name, best_score = name, mean_score
    return best_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a home value prediction model")
    parser.add_argument("--data", type=str, default=None, help="Path to a CSV housing dataset")
    parser.add_argument("--synthetic-samples", type=int, default=5000)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--model", choices=["rf", "gbr", "auto"], default="auto", help="Regressor to train"
    )
    parser.add_argument("--model-out", type=str, default="models/home_value_model.joblib")
    parser.add_argument("--metrics-out", type=str, default="models/metrics.json")
    args = parser.parse_args()

    print("Loading data...")
    df = load_data(args)
    print(f"  {len(df)} rows loaded.")

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.random_state
    )

    if args.model == "auto":
        print("Selecting best model via cross-validation...")
        model_name = select_best_model(X_train, y_train, args.random_state)
        print(f"  Selected: {model_name}")
    else:
        model_name = args.model

    pipeline = build_pipeline(model_name, args.random_state)
    print(f"Training {model_name} on {len(X_train)} rows...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    metrics = compute_metrics(y_test, y_pred)
    metrics["model"] = model_name
    print("\nHoldout evaluation:")
    print(format_metrics(metrics))

    save_pipeline(pipeline, args.model_out)
    save_metrics(metrics, args.metrics_out)
    print(f"\nSaved model to {args.model_out}")
    print(f"Saved metrics to {args.metrics_out}")


if __name__ == "__main__":
    main()
