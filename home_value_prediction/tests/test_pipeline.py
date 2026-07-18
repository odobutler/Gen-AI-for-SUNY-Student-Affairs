import numpy as np
from sklearn.model_selection import train_test_split

from home_value_prediction.config import FEATURE_COLUMNS, TARGET_COLUMN
from home_value_prediction.data_generator import generate_synthetic_housing_data
from home_value_prediction.evaluate import compute_metrics
from home_value_prediction.predict import predict_one
from home_value_prediction.train import build_pipeline


def test_synthetic_data_has_expected_shape():
    df = generate_synthetic_housing_data(n_samples=200, seed=1)
    assert len(df) == 200
    for col in FEATURE_COLUMNS + [TARGET_COLUMN]:
        assert col in df.columns
    assert (df[TARGET_COLUMN] > 0).all()


def test_pipeline_trains_and_predicts_reasonably():
    df = generate_synthetic_housing_data(n_samples=800, seed=1)
    X, y = df[FEATURE_COLUMNS], df[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=1)

    pipeline = build_pipeline("rf", random_state=1)
    pipeline.fit(X_train, y_train)
    preds = pipeline.predict(X_test)

    metrics = compute_metrics(y_test, preds)
    assert metrics["r2"] > 0.5

    single_record = X_test.iloc[0].to_dict()
    price = predict_one(pipeline, single_record)
    assert np.isfinite(price)
    assert price > 0


def test_predict_one_fills_missing_fields_with_defaults():
    df = generate_synthetic_housing_data(n_samples=300, seed=2)
    X, y = df[FEATURE_COLUMNS], df[TARGET_COLUMN]
    pipeline = build_pipeline("rf", random_state=2)
    pipeline.fit(X, y)

    price = predict_one(pipeline, {"bedrooms": 5, "zipcode": "98004"})
    assert np.isfinite(price)
    assert price > 0
