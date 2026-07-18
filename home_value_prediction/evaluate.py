"""Regression evaluation helpers."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def compute_metrics(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    return {"rmse": rmse, "mae": mae, "r2": r2, "mape": mape}


def format_metrics(metrics: dict) -> str:
    return (
        f"RMSE: ${metrics['rmse']:,.0f}\n"
        f"MAE:  ${metrics['mae']:,.0f}\n"
        f"R2:   {metrics['r2']:.4f}\n"
        f"MAPE: {metrics['mape']:.2f}%"
    )
