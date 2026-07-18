"""Synthetic housing data generator.

Used when no real dataset (e.g. a Zillow / county-assessor export) is
available. The generator produces features similar to Kaggle's King County
house-sales dataset and derives a price from a plausible, non-linear
combination of those features plus noise, so that a trained model has real
structure to learn.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# zipcode -> (base multiplier, center lat, center long)
_ZIPCODE_PROFILES = {
    "98001": (0.85, 47.30, -122.25),
    "98004": (1.90, 47.62, -122.20),
    "98006": (1.45, 47.56, -122.14),
    "98033": (1.55, 47.68, -122.20),
    "98040": (1.85, 47.56, -122.23),
    "98052": (1.30, 47.67, -122.12),
    "98059": (1.05, 47.49, -122.15),
    "98074": (1.20, 47.62, -122.05),
    "98103": (1.35, 47.70, -122.34),
    "98115": (1.25, 47.68, -122.29),
    "98118": (0.95, 47.54, -122.28),
    "98122": (1.15, 47.61, -122.30),
    "98144": (1.10, 47.58, -122.29),
    "98146": (0.80, 47.50, -122.34),
    "98168": (0.75, 47.48, -122.26),
    "98177": (1.15, 47.73, -122.37),
    "98198": (0.78, 47.38, -122.32),
    "98199": (1.50, 47.65, -122.40),
}

_ZIPCODES = list(_ZIPCODE_PROFILES.keys())


def generate_synthetic_housing_data(n_samples: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic housing dataset with a realistic price signal."""
    rng = np.random.default_rng(seed)

    bedrooms = rng.integers(1, 7, n_samples)
    bathrooms = np.round(rng.uniform(1, 4.5, n_samples) * 2) / 2
    sqft_living = rng.integers(500, 6000, n_samples)
    sqft_lot = rng.integers(1000, 43000, n_samples)
    floors = rng.choice([1, 1.5, 2, 2.5, 3], n_samples, p=[0.4, 0.15, 0.3, 0.1, 0.05])
    waterfront = rng.choice([0, 1], n_samples, p=[0.97, 0.03])
    view = rng.choice([0, 1, 2, 3, 4], n_samples, p=[0.6, 0.15, 0.13, 0.08, 0.04])
    condition = rng.integers(1, 6, n_samples)
    grade = rng.integers(3, 13, n_samples)
    sqft_above = np.round(sqft_living * rng.uniform(0.6, 1.0, n_samples)).astype(int)
    sqft_basement = sqft_living - sqft_above
    yr_built = rng.integers(1900, 2024, n_samples)
    has_renovation = rng.random(n_samples) < 0.2
    yr_renovated = np.where(has_renovation, rng.integers(yr_built + 1, 2025, n_samples), 0)
    school_rating = rng.integers(1, 11, n_samples)
    crime_index = rng.uniform(0, 100, n_samples)

    zipcode_idx = rng.integers(0, len(_ZIPCODES), n_samples)
    zipcode = np.array(_ZIPCODES)[zipcode_idx]
    multipliers = np.array([_ZIPCODE_PROFILES[z][0] for z in zipcode])
    center_lat = np.array([_ZIPCODE_PROFILES[z][1] for z in zipcode])
    center_long = np.array([_ZIPCODE_PROFILES[z][2] for z in zipcode])
    lat = center_lat + rng.normal(0, 0.01, n_samples)
    long = center_long + rng.normal(0, 0.01, n_samples)
    distance_to_city_km = np.abs(rng.normal(15, 8, n_samples)).clip(0.5, 60)

    effective_age = 2024 - np.maximum(yr_built, yr_renovated)
    age_penalty = np.clip(effective_age, 0, 80) * 400

    base_price = (
        45_000
        + sqft_living * 165
        + sqft_lot * 0.6
        + bedrooms * 6_000
        + bathrooms * 11_000
        + grade * 14_000
        + view * 9_000
        + waterfront * 220_000
        + school_rating * 4_500
        - crime_index * 550
        - distance_to_city_km * 900
        - age_penalty
        + (condition - 3) * 5_000
    )
    price = base_price * multipliers
    price = price * rng.normal(1.0, 0.08, n_samples)  # multiplicative noise
    price = np.clip(price, 60_000, None)

    df = pd.DataFrame(
        {
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "sqft_living": sqft_living,
            "sqft_lot": sqft_lot,
            "floors": floors,
            "waterfront": waterfront,
            "view": view,
            "condition": condition,
            "grade": grade,
            "sqft_above": sqft_above,
            "sqft_basement": sqft_basement,
            "yr_built": yr_built,
            "yr_renovated": yr_renovated,
            "zipcode": zipcode,
            "lat": lat,
            "long": long,
            "distance_to_city_km": distance_to_city_km,
            "school_rating": school_rating,
            "crime_index": crime_index,
            "price": np.round(price, -2),
        }
    )
    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic housing data")
    parser.add_argument("--n-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="data/synthetic_housing.csv")
    args = parser.parse_args()

    import os

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    data = generate_synthetic_housing_data(args.n_samples, args.seed)
    data.to_csv(args.out, index=False)
    print(f"Wrote {len(data)} rows to {args.out}")
