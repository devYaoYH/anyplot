"""Differential Privacy engine and schema masking for Sanctum.

This module provides the core privacy-preserving functionality:
- Schema masking: Convert real column names to hashed identifiers
- Differential Privacy: Add calibrated noise to statistical queries
- Histogram generation: Create DP-protected histogram bins
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class MaskedColumn:
    """Represents a masked column with its original name hidden."""

    masked_name: str
    dtype: str
    # Original name stored locally but never exposed to the agent
    _original_name: str = field(repr=False)

    def to_dict(self) -> dict:
        """Return dict for serialization (excludes original name)."""
        return {"masked_name": self.masked_name, "dtype": self.dtype}


class SchemaMapper:
    """Manages bidirectional mapping between masked and original column names."""

    def __init__(self, salt: str | None = None):
        """Initialize with optional salt for deterministic hashing in tests."""
        self._salt = salt or secrets.token_hex(8)
        self._masked_to_original: dict[str, str] = {}
        self._original_to_masked: dict[str, str] = {}

    def _hash_column_name(self, name: str) -> str:
        """Create a deterministic hash for a column name."""
        hash_input = f"{self._salt}:{name}".encode()
        hash_digest = hashlib.sha256(hash_input).hexdigest()[:8]
        return f"col_{hash_digest}"

    def add_column(self, original_name: str) -> str:
        """Add a column mapping and return the masked name."""
        if original_name in self._original_to_masked:
            return self._original_to_masked[original_name]

        masked_name = self._hash_column_name(original_name)
        self._masked_to_original[masked_name] = original_name
        self._original_to_masked[original_name] = masked_name
        return masked_name

    def get_original(self, masked_name: str) -> str | None:
        """Get the original column name from a masked name."""
        return self._masked_to_original.get(masked_name)

    def get_masked(self, original_name: str) -> str | None:
        """Get the masked name from an original column name."""
        return self._original_to_masked.get(original_name)

    def get_reverse_mapping(self) -> dict[str, str]:
        """Get mapping from masked names to original names."""
        return dict(self._masked_to_original)

    def get_forward_mapping(self) -> dict[str, str]:
        """Get mapping from original names to masked names."""
        return dict(self._original_to_masked)


def extract_masked_schema(
    df: pd.DataFrame, salt: str | None = None
) -> tuple[dict[str, MaskedColumn], SchemaMapper]:
    """Extract a masked schema from a DataFrame.

    Returns mapping of masked_name -> MaskedColumn. The original column names
    are stored in MaskedColumn._original_name but never sent to the agent.

    Args:
        df: The DataFrame to extract schema from
        salt: Optional salt for deterministic hashing (for testing)

    Returns:
        Tuple of (masked schema dict, SchemaMapper for reverse lookups)
    """
    mapper = SchemaMapper(salt=salt)
    schema: dict[str, MaskedColumn] = {}

    for col in df.columns:
        col_str = str(col)
        masked_name = mapper.add_column(col_str)
        dtype_str = _pandas_dtype_to_string(df[col].dtype)

        schema[masked_name] = MaskedColumn(
            masked_name=masked_name,
            dtype=dtype_str,
            _original_name=col_str,
        )

    return schema, mapper


def _pandas_dtype_to_string(dtype: np.dtype) -> str:
    """Convert pandas dtype to a simple string representation."""
    dtype_name = str(dtype)
    if "int" in dtype_name:
        return "integer"
    elif "float" in dtype_name:
        return "float"
    elif "bool" in dtype_name:
        return "boolean"
    elif "datetime" in dtype_name:
        return "datetime"
    elif dtype_name == "object" or "str" in dtype_name:
        return "string"
    else:
        return dtype_name


def add_laplace_noise(
    value: float, epsilon: float, sensitivity: float, rng: np.random.Generator | None = None
) -> float:
    """Add Laplace noise to a value for differential privacy.

    Uses the Laplace mechanism: noisy_value = value + Laplace(0, sensitivity/epsilon)

    Args:
        value: The true value to add noise to
        epsilon: Privacy parameter (lower = more private)
        sensitivity: Maximum change in output from changing one record
        rng: Optional random generator for reproducibility

    Returns:
        The noisy value
    """
    if epsilon <= 0:
        raise ValueError("Epsilon must be positive")
    if sensitivity < 0:
        raise ValueError("Sensitivity must be non-negative")

    if rng is None:
        rng = np.random.default_rng()

    scale = sensitivity / epsilon
    noise = rng.laplace(0, scale)
    return float(value + noise)


def _compute_clip_bounds(
    series: pd.Series, clip_bounds: tuple[float, float] | None
) -> tuple[float, float]:
    """Compute clip bounds, defaulting to 1st and 99th percentiles."""
    if clip_bounds is not None:
        return clip_bounds

    numeric_series = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric_series) == 0:
        return (0.0, 1.0)

    lower = float(numeric_series.quantile(0.01))
    upper = float(numeric_series.quantile(0.99))

    # Ensure bounds are different
    if lower == upper:
        lower = lower - 1.0
        upper = upper + 1.0

    return (lower, upper)


def _clip_values(series: pd.Series, lower: float, upper: float) -> pd.Series:
    """Clip values to the specified bounds."""
    return series.clip(lower=lower, upper=upper)


def query_aggregate(
    df: pd.DataFrame,
    column: str,
    statistic: Literal["mean", "max", "min", "count", "sum"],
    epsilon: float = 1.0,
    clip_bounds: tuple[float, float] | None = None,
    rng: np.random.Generator | None = None,
) -> float:
    """Return a differentially private aggregate statistic.

    Args:
        df: The DataFrame containing the data
        column: Column name (can be original or masked name)
        statistic: The aggregate function to compute
        epsilon: Privacy budget for this query
        clip_bounds: Optional (lower, upper) bounds for clipping
        rng: Optional random generator for reproducibility

    Returns:
        The noisy aggregate value

    Raises:
        ValueError: If column not found or invalid statistic
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    series = df[column]

    # For count, we don't need numeric conversion
    if statistic == "count":
        true_value = float(len(series))
        # Sensitivity for count is 1 (adding/removing one row changes count by 1)
        return add_laplace_noise(true_value, epsilon, sensitivity=1.0, rng=rng)

    # Convert to numeric for other statistics
    numeric_series = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric_series) == 0:
        raise ValueError(f"Column '{column}' has no numeric values")

    # Compute clip bounds
    lower, upper = _compute_clip_bounds(numeric_series, clip_bounds)

    # Clip values to bound sensitivity
    clipped = _clip_values(numeric_series, lower, upper)

    # Compute true value and sensitivity based on statistic
    if statistic == "mean":
        true_value = float(clipped.mean())
        # Sensitivity for mean is (upper - lower) / n
        n = len(clipped)
        sensitivity = (upper - lower) / n if n > 0 else upper - lower
    elif statistic == "sum":
        true_value = float(clipped.sum())
        # Sensitivity for sum is (upper - lower) for one record
        sensitivity = upper - lower
    elif statistic == "max":
        true_value = float(clipped.max())
        # Sensitivity for max is (upper - lower)
        sensitivity = upper - lower
    elif statistic == "min":
        true_value = float(clipped.min())
        # Sensitivity for min is (upper - lower)
        sensitivity = upper - lower
    else:
        raise ValueError(f"Unknown statistic: {statistic}")

    return add_laplace_noise(true_value, epsilon, sensitivity, rng=rng)


def get_histogram(
    df: pd.DataFrame,
    column: str,
    num_bins: int = 10,
    epsilon: float = 1.0,
    clip_bounds: tuple[float, float] | None = None,
    rng: np.random.Generator | None = None,
) -> dict:
    """Return a differentially private histogram.

    Args:
        df: The DataFrame containing the data
        column: Column name
        num_bins: Number of histogram bins
        epsilon: Privacy budget for this query (split across bins)
        clip_bounds: Optional (lower, upper) bounds for the histogram range
        rng: Optional random generator for reproducibility

    Returns:
        Dict with 'edges' (bin edges) and 'counts' (noisy bin counts)

    Raises:
        ValueError: If column not found or has no numeric values
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    series = df[column]
    numeric_series = pd.to_numeric(series, errors="coerce").dropna()

    if len(numeric_series) == 0:
        raise ValueError(f"Column '{column}' has no numeric values")

    # Compute clip bounds for histogram range
    lower, upper = _compute_clip_bounds(numeric_series, clip_bounds)

    # Clip values
    clipped = _clip_values(numeric_series, lower, upper)

    # Compute true histogram
    counts, edges = np.histogram(clipped, bins=num_bins, range=(lower, upper))

    # Add noise to each bin count
    # Sensitivity for each bin is 1 (adding/removing one row changes one bin by 1)
    # We split epsilon across all bins for composition
    epsilon_per_bin = epsilon / num_bins

    if rng is None:
        rng = np.random.default_rng()

    noisy_counts = []
    for count in counts:
        noisy_count = add_laplace_noise(float(count), epsilon_per_bin, sensitivity=1.0, rng=rng)
        # Counts can't be negative, so we clamp to 0
        noisy_counts.append(max(0.0, noisy_count))

    return {
        "edges": [float(e) for e in edges],
        "counts": noisy_counts,
    }
