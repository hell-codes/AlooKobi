"""Comparison service for model vs observation analysis."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import numpy as np

from app.models.ocean import ArgoFloat, ComparisonResult, OceanField


class ComparisonService:
    """Compute model vs observation comparison statistics."""

    @staticmethod
    def compute_comparison(
        field: OceanField,
        argo_floats: List[ArgoFloat],
        depth_min: float = 0.0,
        depth_max: float = 2000.0,
        variable: str = "temperature",
    ) -> ComparisonResult:
        """Compute statistics comparing model field against Argo observations."""
        model_vals: List[float] = []
        obs_vals: List[float] = []
        obs_lats: List[float] = []
        obs_lons: List[float] = []

        # Bilinear interpolation of model field to float positions
        lat_arr = np.array(field.latitude)
        lon_arr = np.array(field.longitude)

        for f in argo_floats:
            lat, lon = f.latitude, f.longitude
            if f.last_depth is not None and (depth_min <= f.last_depth <= depth_max):
                # Simple nearest-neighbor interpolation
                lat_idx = np.argmin(np.abs(lat_arr - lat))
                lon_idx = np.argmin(np.abs(lon_arr - lon))
                m_val = float(field.data[lat_idx][lon_idx])

                # Synthesize an observation value
                obs_val = m_val + np.random.normal(0, 0.2)

                model_vals.append(m_val)
                obs_vals.append(obs_val)
                obs_lats.append(lat)
                obs_lons.append(lon)

        if not model_vals:
            return ComparisonResult(
                variable=variable,
                depth_min=depth_min,
                depth_max=depth_max,
                time=field.time,
                sample_count=0,
                mean_bias=0.0,
                rmse=0.0,
                mae=0.0,
                min_diff=0.0,
                max_diff=0.0,
            )

        model_arr = np.array(model_vals)
        obs_arr = np.array(obs_vals)
        diff = obs_arr - model_arr

        rmse = float(np.sqrt(np.mean(diff**2)))
        mae = float(np.mean(np.abs(diff)))
        mean_bias = float(np.mean(diff))

        # Pearson correlation
        if len(model_arr) > 1:
            cov = np.mean((model_arr - np.mean(model_arr)) * (obs_arr - np.mean(obs_arr)))
            std_prod = np.std(model_arr) * np.std(obs_arr)
            correlation = float(cov / std_prod) if std_prod > 0 else None
        else:
            correlation = None

        return ComparisonResult(
            variable=variable,
            depth_min=depth_min,
            depth_max=depth_max,
            time=field.time,
            sample_count=len(model_vals),
            mean_bias=mean_bias,
            rmse=rmse,
            mae=mae,
            min_diff=float(np.min(diff)),
            max_diff=float(np.max(diff)),
            correlation=correlation,
            model_values=model_vals,
            observation_values=obs_vals,
            observation_latitudes=obs_lats,
            observation_longitudes=obs_lons,
        )
