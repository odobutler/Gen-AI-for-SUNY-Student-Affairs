# Home Value Prediction

A Zillow-Zestimate-style home value prediction pipeline in Python: synthetic
(or real) housing data in, a trained regression model out, with a CLI for
scoring individual homes or batches.

## Features

- **Data**: `home_value_prediction/data_generator.py` generates a synthetic
  but realistic housing dataset (bedrooms, bathrooms, square footage, lot
  size, zipcode, school rating, crime index, distance to city center, etc.)
  with a non-linear, zipcode-adjusted price signal. Swap in a real CSV export
  (e.g. a county assessor or MLS extract) with the same columns at any time.
- **Preprocessing**: `preprocessing.py` builds a scikit-learn
  `ColumnTransformer` that imputes, scales numeric features, and one-hot
  encodes categorical ones (zipcode, waterfront).
- **Training**: `train.py` trains a `RandomForestRegressor` or
  `GradientBoostingRegressor` (or auto-selects the better one via
  cross-validation), evaluates on a holdout set (RMSE, MAE, R2, MAPE), and
  saves the fitted pipeline with `joblib`.
- **Prediction**: `predict.py` loads a saved pipeline and predicts a price
  for a single home (JSON input, missing fields fall back to sensible
  defaults) or a batch of homes (CSV in, CSV of predictions out).

## Setup

```bash
pip install -r requirements.txt
```

## Train a model

Using generated synthetic data (good for trying the pipeline immediately):

```bash
python -m home_value_prediction.train --synthetic-samples 5000
```

Using your own dataset (must contain the feature columns listed in
`home_value_prediction/config.py` plus a `price` column):

```bash
python -m home_value_prediction.train --data data/my_housing_data.csv
```

This prints cross-validated model comparison, holdout metrics, and writes:

- `models/home_value_model.joblib` — the fitted pipeline
- `models/metrics.json` — evaluation metrics

## Predict a home's value

```bash
python -m home_value_prediction.predict --input home_value_prediction/example_home.json
```

Or inline:

```bash
python -m home_value_prediction.predict --json '{"bedrooms": 4, "bathrooms": 2.5, "sqft_living": 2400, "zipcode": "98052"}'
```

Batch scoring:

```bash
python -m home_value_prediction.predict --input-csv homes.csv --output-csv predictions.csv
```

## Run tests

```bash
pytest home_value_prediction/tests
```

## Project layout

```
home_value_prediction/
  config.py            # feature column definitions and defaults
  data_generator.py     # synthetic housing data generator
  preprocessing.py      # sklearn ColumnTransformer pipeline
  train.py              # training CLI
  predict.py             # prediction CLI
  evaluate.py            # metric computation
  model_utils.py         # save/load helpers for the pipeline and metrics
  example_home.json      # sample input for predict.py
  tests/                 # pytest smoke tests
```
