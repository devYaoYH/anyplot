"""Privacy budget tracking for Sanctum.

Tracks cumulative epsilon spend per session and rejects queries when budget exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


class BudgetExhaustedError(Exception):
    """Raised when privacy budget is exhausted."""

    pass


@dataclass
class PrivacyBudget:
    """Tracks privacy budget for a session.

    Each query consumes a portion of the total budget. When exhausted,
    no more statistical queries are allowed.
    """

    total_budget: float = 10.0
    _spent: float = field(default=0.0, repr=False)

    @property
    def remaining(self) -> float:
        """Get the remaining privacy budget."""
        return max(0.0, self.total_budget - self._spent)

    @property
    def spent(self) -> float:
        """Get the total budget spent so far."""
        return self._spent

    def can_spend(self, epsilon: float) -> bool:
        """Check if we can spend the given epsilon amount."""
        return epsilon <= self.remaining

    def spend(self, epsilon: float) -> float:
        """Spend privacy budget and return remaining budget.

        Args:
            epsilon: Amount of budget to spend

        Returns:
            Remaining budget after spending

        Raises:
            BudgetExhaustedError: If not enough budget remains
        """
        if epsilon <= 0:
            raise ValueError("Epsilon must be positive")

        if not self.can_spend(epsilon):
            raise BudgetExhaustedError(
                f"Insufficient privacy budget. Requested: {epsilon}, "
                f"Remaining: {self.remaining}"
            )

        self._spent += epsilon
        return self.remaining

    def get_cost(
        self, operation: Literal["query_stat", "get_histogram", "get_schema"], num_bins: int = 10
    ) -> float:
        """Get the privacy cost for an operation.

        Args:
            operation: Type of operation
            num_bins: Number of bins (for histogram operations)

        Returns:
            Epsilon cost for the operation
        """
        if operation == "get_schema":
            return 0.0  # Schema access has no privacy cost
        elif operation == "query_stat":
            return 1.0  # Default epsilon per stat query
        elif operation == "get_histogram":
            return 1.0  # Epsilon for histogram (already split internally)
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def reset(self) -> None:
        """Reset the budget to full (for testing or new sessions)."""
        self._spent = 0.0
