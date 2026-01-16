"""Unit tests for the privacy budget module.

Tests:
- Budget tracking and spending
- Budget exhaustion handling
- Cost calculation for different operations
"""

import pytest

from sanctum_mcp.budget import BudgetExhaustedError, PrivacyBudget


class TestPrivacyBudget:
    """Tests for PrivacyBudget class."""

    def test_initial_budget(self):
        """Budget should start at total_budget."""
        budget = PrivacyBudget(total_budget=10.0)

        assert budget.remaining == 10.0
        assert budget.spent == 0.0

    def test_spend_reduces_remaining(self):
        """Spending budget should reduce remaining."""
        budget = PrivacyBudget(total_budget=10.0)

        remaining = budget.spend(3.0)

        assert remaining == 7.0
        assert budget.remaining == 7.0
        assert budget.spent == 3.0

    def test_multiple_spends_accumulate(self):
        """Multiple spends should accumulate."""
        budget = PrivacyBudget(total_budget=10.0)

        budget.spend(2.0)
        budget.spend(3.0)
        budget.spend(1.0)

        assert budget.spent == 6.0
        assert budget.remaining == 4.0

    def test_can_spend_returns_true_when_available(self):
        """can_spend should return True when budget is available."""
        budget = PrivacyBudget(total_budget=10.0)
        budget.spend(5.0)

        assert budget.can_spend(5.0) is True
        assert budget.can_spend(4.0) is True

    def test_can_spend_returns_false_when_insufficient(self):
        """can_spend should return False when budget is insufficient."""
        budget = PrivacyBudget(total_budget=10.0)
        budget.spend(8.0)

        assert budget.can_spend(3.0) is False
        assert budget.can_spend(2.1) is False

    def test_spend_raises_when_exhausted(self):
        """Spending more than remaining should raise BudgetExhaustedError."""
        budget = PrivacyBudget(total_budget=5.0)
        budget.spend(3.0)

        with pytest.raises(BudgetExhaustedError) as exc_info:
            budget.spend(3.0)

        assert "Insufficient privacy budget" in str(exc_info.value)
        assert "Requested: 3.0" in str(exc_info.value)
        assert "Remaining: 2.0" in str(exc_info.value)

    def test_spend_exactly_remaining_succeeds(self):
        """Spending exactly the remaining budget should succeed."""
        budget = PrivacyBudget(total_budget=5.0)
        budget.spend(3.0)

        remaining = budget.spend(2.0)

        assert remaining == 0.0
        assert budget.remaining == 0.0

    def test_zero_spend_raises_error(self):
        """Zero epsilon spend should raise ValueError."""
        budget = PrivacyBudget(total_budget=10.0)

        with pytest.raises(ValueError, match="Epsilon must be positive"):
            budget.spend(0)

    def test_negative_spend_raises_error(self):
        """Negative epsilon spend should raise ValueError."""
        budget = PrivacyBudget(total_budget=10.0)

        with pytest.raises(ValueError, match="Epsilon must be positive"):
            budget.spend(-1.0)

    def test_remaining_never_negative(self):
        """Remaining budget should never go negative."""
        budget = PrivacyBudget(total_budget=5.0)
        budget.spend(5.0)

        assert budget.remaining == 0.0

    def test_reset_restores_full_budget(self):
        """Reset should restore full budget."""
        budget = PrivacyBudget(total_budget=10.0)
        budget.spend(7.0)

        budget.reset()

        assert budget.remaining == 10.0
        assert budget.spent == 0.0


class TestBudgetCosts:
    """Tests for operation cost calculations."""

    def test_get_schema_cost_is_zero(self):
        """get_schema should have no privacy cost."""
        budget = PrivacyBudget()

        cost = budget.get_cost("get_schema")

        assert cost == 0.0

    def test_query_stat_cost_is_one(self):
        """query_stat should cost 1.0 epsilon by default."""
        budget = PrivacyBudget()

        cost = budget.get_cost("query_stat")

        assert cost == 1.0

    def test_get_histogram_cost(self):
        """get_histogram should cost epsilon."""
        budget = PrivacyBudget()

        cost = budget.get_cost("get_histogram", num_bins=10)

        assert cost == 1.0

    def test_unknown_operation_raises_error(self):
        """Unknown operation should raise ValueError."""
        budget = PrivacyBudget()

        with pytest.raises(ValueError, match="Unknown operation"):
            budget.get_cost("unknown_op")  # type: ignore


class TestBudgetIntegration:
    """Integration tests for budget tracking scenarios."""

    def test_typical_session_workflow(self):
        """Test a typical session with multiple queries."""
        budget = PrivacyBudget(total_budget=10.0)

        # Get schema (free)
        schema_cost = budget.get_cost("get_schema")
        if schema_cost > 0:
            budget.spend(schema_cost)

        # Run some stat queries
        for _ in range(5):
            stat_cost = budget.get_cost("query_stat")
            budget.spend(stat_cost)

        assert budget.remaining == 5.0

        # Run histogram
        hist_cost = budget.get_cost("get_histogram")
        budget.spend(hist_cost)

        assert budget.remaining == 4.0

        # Try to run more queries than budget allows
        for _ in range(4):
            stat_cost = budget.get_cost("query_stat")
            budget.spend(stat_cost)

        assert budget.remaining == 0.0

        # Next query should fail
        with pytest.raises(BudgetExhaustedError):
            budget.spend(budget.get_cost("query_stat"))

    def test_budget_prevents_over_querying(self):
        """Budget should prevent queries when exhausted."""
        budget = PrivacyBudget(total_budget=2.0)

        budget.spend(1.0)
        budget.spend(1.0)

        assert not budget.can_spend(0.1)

        with pytest.raises(BudgetExhaustedError):
            budget.spend(0.1)
