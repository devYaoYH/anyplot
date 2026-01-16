"""Unit tests for the privacy module.

Tests:
- Schema masking never leaks original column names
- Laplace noise distribution verification
- Aggregate statistics with DP
- Histogram generation with DP
- Clip bounds calculation
"""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from sanctum_mcp.privacy import (
    MaskedColumn,
    SchemaMapper,
    add_laplace_noise,
    extract_masked_schema,
    get_histogram,
    query_aggregate,
)


class TestSchemaMapper:
    """Tests for SchemaMapper class."""

    def test_column_hashing_produces_masked_names(self):
        """Column names should be converted to hashed identifiers."""
        mapper = SchemaMapper(salt="test_salt")
        masked = mapper.add_column("salary")

        assert masked.startswith("col_")
        assert masked != "salary"
        assert len(masked) == 12  # col_ + 8 hex chars

    def test_same_column_returns_same_hash(self):
        """Same column name should always produce same masked name."""
        mapper = SchemaMapper(salt="test_salt")
        masked1 = mapper.add_column("salary")
        masked2 = mapper.add_column("salary")

        assert masked1 == masked2

    def test_different_columns_produce_different_hashes(self):
        """Different column names should produce different hashes."""
        mapper = SchemaMapper(salt="test_salt")
        masked1 = mapper.add_column("salary")
        masked2 = mapper.add_column("age")

        assert masked1 != masked2

    def test_reverse_mapping_works(self):
        """Should be able to get original name from masked name."""
        mapper = SchemaMapper(salt="test_salt")
        masked = mapper.add_column("salary")
        original = mapper.get_original(masked)

        assert original == "salary"

    def test_forward_mapping_works(self):
        """Should be able to get masked name from original name."""
        mapper = SchemaMapper(salt="test_salt")
        mapper.add_column("salary")
        masked = mapper.get_masked("salary")

        assert masked is not None
        assert masked.startswith("col_")

    def test_unknown_column_returns_none(self):
        """Unknown masked name should return None."""
        mapper = SchemaMapper(salt="test_salt")
        result = mapper.get_original("col_unknown")

        assert result is None


class TestExtractMaskedSchema:
    """Tests for extract_masked_schema function."""

    def test_schema_contains_all_columns(self):
        """Schema should include all DataFrame columns."""
        df = pd.DataFrame({"salary": [50000, 60000], "age": [30, 40], "name": ["Alice", "Bob"]})

        schema, mapper = extract_masked_schema(df, salt="test")

        assert len(schema) == 3

    def test_original_names_never_in_output(self):
        """Original column names must NEVER appear in serialized output."""
        # Use PII-like column names to test
        df = pd.DataFrame(
            {
                "ssn": ["123-45-6789", "987-65-4321"],
                "credit_card": ["4111111111111111", "5500000000000004"],
                "password": ["secret123", "hunter2"],
            }
        )

        schema, mapper = extract_masked_schema(df, salt="test")

        # Check serialized output
        for masked_name, masked_col in schema.items():
            serialized = masked_col.to_dict()
            assert "ssn" not in str(serialized)
            assert "credit_card" not in str(serialized)
            assert "password" not in str(serialized)
            assert masked_col.masked_name.startswith("col_")

    def test_dtype_preserved_correctly(self):
        """Data types should be correctly identified."""
        df = pd.DataFrame(
            {
                "int_col": [1, 2, 3],
                "float_col": [1.1, 2.2, 3.3],
                "str_col": ["a", "b", "c"],
                "bool_col": [True, False, True],
            }
        )

        schema, mapper = extract_masked_schema(df, salt="test")

        # Get dtypes by original column name
        dtypes = {masked_col._original_name: masked_col.dtype for masked_col in schema.values()}

        assert dtypes["int_col"] == "integer"
        assert dtypes["float_col"] == "float"
        assert dtypes["str_col"] == "string"
        assert dtypes["bool_col"] == "boolean"

    def test_mapper_can_reverse_lookup(self):
        """SchemaMapper should allow reverse lookup of column names."""
        df = pd.DataFrame({"salary": [50000], "age": [30]})

        schema, mapper = extract_masked_schema(df, salt="test")

        reverse_mapping = mapper.get_reverse_mapping()
        assert len(reverse_mapping) == 2
        assert "salary" in reverse_mapping.values()
        assert "age" in reverse_mapping.values()


class TestAddLaplaceNoise:
    """Tests for add_laplace_noise function."""

    def test_noise_follows_laplace_distribution(self):
        """Verify noise follows Laplace distribution with correct scale."""
        epsilon = 1.0
        sensitivity = 100.0
        expected_scale = sensitivity / epsilon  # = 100

        rng = np.random.default_rng(42)
        samples = [add_laplace_noise(0, epsilon, sensitivity, rng=rng) for _ in range(10000)]

        # Laplace std = scale * sqrt(2)
        expected_std = expected_scale * np.sqrt(2)
        actual_std = np.std(samples)

        # Allow 10% tolerance
        assert abs(actual_std - expected_std) < expected_std * 0.1

    def test_noise_mean_is_original_value(self):
        """Mean of noisy samples should be close to original value."""
        original_value = 500.0
        epsilon = 1.0
        sensitivity = 10.0

        rng = np.random.default_rng(42)
        samples = [
            add_laplace_noise(original_value, epsilon, sensitivity, rng=rng) for _ in range(10000)
        ]

        # Mean should be close to original value
        assert abs(np.mean(samples) - original_value) < 1.0

    def test_lower_epsilon_more_noise(self):
        """Lower epsilon should result in more noise (higher variance)."""
        sensitivity = 100.0

        rng_high = np.random.default_rng(42)
        high_eps_samples = [
            add_laplace_noise(0, epsilon=2.0, sensitivity=sensitivity, rng=rng_high)
            for _ in range(5000)
        ]

        rng_low = np.random.default_rng(42)
        low_eps_samples = [
            add_laplace_noise(0, epsilon=0.5, sensitivity=sensitivity, rng=rng_low)
            for _ in range(5000)
        ]

        assert np.std(low_eps_samples) > np.std(high_eps_samples)

    def test_zero_epsilon_raises_error(self):
        """Epsilon must be positive."""
        with pytest.raises(ValueError, match="Epsilon must be positive"):
            add_laplace_noise(100, epsilon=0, sensitivity=1.0)

    def test_negative_epsilon_raises_error(self):
        """Negative epsilon should raise error."""
        with pytest.raises(ValueError, match="Epsilon must be positive"):
            add_laplace_noise(100, epsilon=-1.0, sensitivity=1.0)

    def test_negative_sensitivity_raises_error(self):
        """Negative sensitivity should raise error."""
        with pytest.raises(ValueError, match="Sensitivity must be non-negative"):
            add_laplace_noise(100, epsilon=1.0, sensitivity=-1.0)

    def test_statistical_test_laplace(self):
        """Use Kolmogorov-Smirnov test to verify Laplace distribution."""
        epsilon = 1.0
        sensitivity = 50.0
        scale = sensitivity / epsilon

        rng = np.random.default_rng(42)
        samples = [add_laplace_noise(0, epsilon, sensitivity, rng=rng) for _ in range(5000)]

        # KS test against Laplace distribution
        statistic, p_value = stats.kstest(samples, stats.laplace(loc=0, scale=scale).cdf)

        # p-value should be > 0.05 (we don't reject that samples are Laplace)
        assert p_value > 0.01


class TestQueryAggregate:
    """Tests for query_aggregate function."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame for testing."""
        return pd.DataFrame(
            {
                "salary": [40000, 50000, 60000, 70000, 80000],
                "age": [25, 30, 35, 40, 45],
                "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            }
        )

    def test_count_returns_noisy_value(self, sample_df):
        """Count should return noisy row count."""
        rng = np.random.default_rng(42)
        result = query_aggregate(sample_df, "salary", "count", epsilon=1.0, rng=rng)

        # Should be close to 5 but not exact
        assert isinstance(result, float)
        # With epsilon=1.0 and sensitivity=1, noise scale is 1
        # True value is 5, so result should be in reasonable range
        assert 0 < result < 15

    def test_mean_returns_noisy_value(self, sample_df):
        """Mean should return noisy average."""
        rng = np.random.default_rng(42)
        result = query_aggregate(sample_df, "salary", "mean", epsilon=1.0, rng=rng)

        # True mean is 60000
        assert isinstance(result, float)
        # Should be in reasonable range
        assert 40000 < result < 80000

    def test_sum_returns_noisy_value(self, sample_df):
        """Sum should return noisy total."""
        rng = np.random.default_rng(42)
        result = query_aggregate(sample_df, "salary", "sum", epsilon=1.0, rng=rng)

        # True sum is 300000
        assert isinstance(result, float)

    def test_max_returns_noisy_value(self, sample_df):
        """Max should return noisy maximum."""
        rng = np.random.default_rng(42)
        result = query_aggregate(sample_df, "salary", "max", epsilon=1.0, rng=rng)

        assert isinstance(result, float)

    def test_min_returns_noisy_value(self, sample_df):
        """Min should return noisy minimum."""
        rng = np.random.default_rng(42)
        result = query_aggregate(sample_df, "salary", "min", epsilon=1.0, rng=rng)

        assert isinstance(result, float)

    def test_invalid_column_raises_error(self, sample_df):
        """Non-existent column should raise ValueError."""
        with pytest.raises(ValueError, match="Column 'nonexistent' not found"):
            query_aggregate(sample_df, "nonexistent", "mean")

    def test_invalid_statistic_raises_error(self, sample_df):
        """Invalid statistic should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown statistic"):
            query_aggregate(sample_df, "salary", "invalid")  # type: ignore

    def test_non_numeric_column_raises_error(self, sample_df):
        """Non-numeric column for stats other than count should raise error."""
        with pytest.raises(ValueError, match="no numeric values"):
            query_aggregate(sample_df, "name", "mean")

    def test_clip_bounds_applied(self):
        """Custom clip bounds should be applied."""
        df = pd.DataFrame({"value": [1, 2, 3, 100, 200]})  # 100, 200 are outliers

        rng = np.random.default_rng(42)
        result = query_aggregate(
            df, "value", "max", epsilon=1.0, clip_bounds=(0, 10), rng=rng
        )

        # With clip bounds (0, 10), max should be around 10, not 200
        assert result < 50  # Should be closer to 10 than 200

    def test_deterministic_with_same_seed(self, sample_df):
        """Same RNG seed should produce same result."""
        rng1 = np.random.default_rng(42)
        result1 = query_aggregate(sample_df, "salary", "mean", epsilon=1.0, rng=rng1)

        rng2 = np.random.default_rng(42)
        result2 = query_aggregate(sample_df, "salary", "mean", epsilon=1.0, rng=rng2)

        assert result1 == result2


class TestGetHistogram:
    """Tests for get_histogram function."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame for testing."""
        return pd.DataFrame({"value": list(range(100))})  # 0 to 99

    def test_returns_edges_and_counts(self, sample_df):
        """Histogram should return edges and counts."""
        rng = np.random.default_rng(42)
        result = get_histogram(sample_df, "value", num_bins=10, epsilon=1.0, rng=rng)

        assert "edges" in result
        assert "counts" in result
        assert len(result["edges"]) == 11  # n+1 edges for n bins
        assert len(result["counts"]) == 10

    def test_counts_are_noisy(self, sample_df):
        """Histogram counts should have noise added."""
        rng = np.random.default_rng(42)
        result = get_histogram(sample_df, "value", num_bins=10, epsilon=1.0, rng=rng)

        # True histogram would have 10 items per bin (for 0-99 in 10 bins)
        # Noisy counts should not all be exactly 10
        assert not all(c == 10.0 for c in result["counts"])

    def test_counts_are_non_negative(self, sample_df):
        """Noisy counts should be clamped to non-negative."""
        # Use low epsilon for more noise
        rng = np.random.default_rng(42)
        result = get_histogram(sample_df, "value", num_bins=10, epsilon=0.1, rng=rng)

        assert all(c >= 0 for c in result["counts"])

    def test_invalid_column_raises_error(self, sample_df):
        """Non-existent column should raise ValueError."""
        with pytest.raises(ValueError, match="Column 'nonexistent' not found"):
            get_histogram(sample_df, "nonexistent", num_bins=10)

    def test_non_numeric_column_raises_error(self):
        """Non-numeric column should raise ValueError."""
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]})

        with pytest.raises(ValueError, match="no numeric values"):
            get_histogram(df, "name", num_bins=10)

    def test_clip_bounds_applied(self):
        """Custom clip bounds should set histogram range."""
        df = pd.DataFrame({"value": list(range(100))})

        rng = np.random.default_rng(42)
        result = get_histogram(df, "value", num_bins=5, clip_bounds=(20, 80), rng=rng)

        # Edges should span from 20 to 80
        assert result["edges"][0] == 20.0
        assert result["edges"][-1] == 80.0
