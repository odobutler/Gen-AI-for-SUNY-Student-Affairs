"""Predict a home's value using a trained pipeline.

Examples
--------
Single home from a JSON file (missing fields fall back to sensible defaults):
    python -m home_value_prediction.predict --input example_home.json

Single home from inline JSON:
    python -m home_value_prediction.predict --json '{"bedrooms": 4, "bathrooms": 2.5, "sqft_living": 2400, "zipcode": "98052"}'

Batch predictions from a CSV of homes:
    python -m home_value_prediction.predict --input-csv homes.csv --output-csv predictions.csv
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from .config import DEFAULT_FEATURE_VALUES, FEATURE_COLUMNS
from .model_utils import load_pipeline


def _fill_defaults(record: dict) -> dict:
    filled = dict(DEFAULT_FEATURE_VALUES)
    unknown = [k for k in record if k not in FEATURE_COLUMNS]
    if unknown:
        raise ValueError(f"Unknown feature(s): {unknown}")
    filled.update(record)
    return filled


def predict_one(pipeline, record: dict) -> float:
    filled = _fill_defaults(record)
    df = pd.DataFrame([filled])[FEATURE_COLUMNS]
    return float(pipeline.predict(df)[0])


def predict_batch(pipeline, df: pd.DataFrame) -> pd.Series:
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {missing}")
    return pd.Series(pipeline.predict(df[FEATURE_COLUMNS]), index=df.index, name="predicted_price")


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict a home's value")
    parser.add_argument("--model", type=str, default="models/home_value_model.joblib")
    parser.add_argument("--input", type=str, default=None, help="Path to a JSON file for one home")
    parser.add_argument("--json", type=str, default=None, help="Inline JSON for one home")
    parser.add_argument("--input-csv", type=str, default=None, help="CSV of homes for batch scoring")
    parser.add_argument("--output-csv", type=str, default=None, help="Where to write batch predictions")
    args = parser.parse_args()

    pipeline = load_pipeline(args.model)

    if args.input_csv:
        df = pd.read_csv(args.input_csv)
        predictions = predict_batch(pipeline, df)
        result = df.copy()
        result["predicted_price"] = predictions
        if args.output_csv:
            result.to_csv(args.output_csv, index=False)
            print(f"Wrote {len(result)} predictions to {args.output_csv}")
        else:
            print(result.to_string(index=False))
        return

    if args.input:
        with open(args.input) as f:
            record = json.load(f)
    elif args.json:
        record = json.loads(args.json)
    else:
        parser.error("Provide one of --input, --json, or --input-csv")
        return

    price = predict_one(pipeline, record)
    print(f"Predicted home value: ${price:,.0f}")


if __name__ == "__main__":
    main()
