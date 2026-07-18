"""Helpers for saving/loading trained pipelines and their metrics."""

from __future__ import annotations

import json
import os
from typing import Any

import joblib


def save_pipeline(pipeline: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    joblib.dump(pipeline, path)


def load_pipeline(path: str) -> Any:
    return joblib.load(path)


def save_metrics(metrics: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)
