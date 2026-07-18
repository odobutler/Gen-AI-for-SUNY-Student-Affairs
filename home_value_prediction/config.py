"""Shared column definitions for the home value prediction pipeline."""

TARGET_COLUMN = "price"

NUMERIC_FEATURES = [
    "bedrooms",
    "bathrooms",
    "sqft_living",
    "sqft_lot",
    "sqft_above",
    "sqft_basement",
    "floors",
    "view",
    "condition",
    "grade",
    "yr_built",
    "yr_renovated",
    "lat",
    "long",
    "distance_to_city_km",
    "school_rating",
    "crime_index",
]

CATEGORICAL_FEATURES = [
    "zipcode",
    "waterfront",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Sensible defaults used by predict.py when a caller omits a field.
DEFAULT_FEATURE_VALUES = {
    "bedrooms": 3,
    "bathrooms": 2.0,
    "sqft_living": 1800,
    "sqft_lot": 6000,
    "sqft_above": 1500,
    "sqft_basement": 300,
    "floors": 1.0,
    "waterfront": 0,
    "view": 0,
    "condition": 3,
    "grade": 7,
    "yr_built": 1990,
    "yr_renovated": 0,
    "zipcode": "98001",
    "lat": 47.44,
    "long": -122.29,
    "distance_to_city_km": 15.0,
    "school_rating": 6,
    "crime_index": 40,
}
