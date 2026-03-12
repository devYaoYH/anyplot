"""
Privacy assertion utilities for testing differential privacy guarantees
"""

import numpy as np
from typing import Callable, Any


class PrivacyAssertion:
    """
    Verify differential privacy guarantees in tests
    
    Example:
        >>> assertion = PrivacyAssertion(epsilon=1.0)
        >>> assertion.verify_differential_privacy(query_func, dataset1, dataset2)
    """
    
    def __init__(self, epsilon: float, delta: float = 0.0):
        """
        Initialize privacy assertion
        
        Args:
            epsilon: Privacy budget
            delta: Delta parameter for (ε, δ)-DP
        """
        self.epsilon = epsilon
        self.delta = delta
    
    def verify_differential_privacy(
        self,
        query_func: Callable,
        dataset1: Any,
        dataset2: Any,
        num_trials: int = 100,
        tolerance: float = 0.1
    ) -> bool:
        """
        Verify that a query satisfies differential privacy
        
        Tests that for two adjacent datasets (differing by one record),
        the query output distributions satisfy:
        P[M(D1) ∈ S] ≤ e^ε * P[M(D2) ∈ S] + δ
        
        Args:
            query_func: Function to test, should accept a dataset
            dataset1: First dataset
            dataset2: Adjacent dataset (differs by one record)
            num_trials: Number of trials for statistical testing
            tolerance: Tolerance for epsilon verification
        
        Returns:
            True if privacy guarantee is satisfied
        
        Raises:
            AssertionError: If privacy guarantee is violated
        """
        results1 = [query_func(dataset1) for _ in range(num_trials)]
        results2 = [query_func(dataset2) for _ in range(num_trials)]
        
        # Calculate empirical epsilon
        empirical_epsilon = self._estimate_epsilon(results1, results2)
        
        assert empirical_epsilon <= self.epsilon + tolerance, \
            f"Privacy violation: empirical ε = {empirical_epsilon:.3f}, expected ε = {self.epsilon:.3f}"
        
        return True
    
    def _estimate_epsilon(self, results1: list, results2: list) -> float:
        """
        Estimate epsilon from query results
        
        Uses histogram-based estimation of distribution ratio
        """
        # Convert to numpy arrays
        r1 = np.array(results1)
        r2 = np.array(results2)
        
        # Create histogram bins
        all_results = np.concatenate([r1, r2])
        bins = np.linspace(all_results.min(), all_results.max(), 20)
        
        # Compute histograms
        hist1, _ = np.histogram(r1, bins=bins)
        hist2, _ = np.histogram(r2, bins=bins)
        
        # Add smoothing to avoid division by zero
        hist1 = hist1 + 1
        hist2 = hist2 + 1
        
        # Compute maximum log ratio
        ratios = hist1 / hist2
        max_log_ratio = np.log(ratios.max())
        
        return max_log_ratio
    
    def verify_laplace_noise(
        self,
        true_value: float,
        noisy_values: list[float],
        sensitivity: float,
        tolerance: float = 0.2
    ) -> bool:
        """
        Verify that noise follows Laplace distribution
        
        Args:
            true_value: True value before noise
            noisy_values: List of noisy values
            sensitivity: Sensitivity of the query
            tolerance: Tolerance for scale verification
        
        Returns:
            True if noise distribution is correct
        """
        noise = np.array(noisy_values) - true_value
        
        # Expected scale for Laplace distribution
        expected_scale = sensitivity / self.epsilon
        
        # Empirical scale (MAE for Laplace = scale)
        empirical_scale = np.abs(noise).mean()
        
        assert abs(empirical_scale - expected_scale) / expected_scale <= tolerance, \
            f"Noise scale incorrect: empirical = {empirical_scale:.3f}, expected = {expected_scale:.3f}"
        
        return True
    
    def verify_budget_enforcement(
        self,
        budget_tracker: Any,
        operations: list[tuple[str, float]],
        total_budget: float
    ) -> bool:
        """
        Verify that privacy budget is correctly enforced
        
        Args:
            budget_tracker: Budget tracking object
            operations: List of (operation_name, epsilon_cost) tuples
            total_budget: Total budget available
        
        Returns:
            True if budget is correctly enforced
        """
        spent = 0.0
        
        for i, (op_name, cost) in enumerate(operations):
            if spent + cost > total_budget:
                # Should reject this operation
                try:
                    budget_tracker.spend(cost)
                    raise AssertionError(
                        f"Budget not enforced: operation {i} ({op_name}) allowed "
                        f"when budget exhausted (spent={spent:.2f}, cost={cost:.2f}, total={total_budget:.2f})"
                    )
                except Exception as e:
                    if "budget" not in str(e).lower():
                        raise
                    # Correctly rejected
                    return True
            else:
                # Should allow this operation
                budget_tracker.spend(cost)
                spent += cost
        
        assert abs(spent - min(sum(c for _, c in operations), total_budget)) < 0.01, \
            f"Budget tracking incorrect: spent={spent:.2f}, expected={min(sum(c for _, c in operations), total_budget):.2f}"
        
        return True
    
    def verify_no_data_leakage(
        self,
        query_output: Any,
        sensitive_data: Any,
        check_substring: bool = True
    ) -> bool:
        """
        Verify that query output doesn't contain raw sensitive data
        
        Args:
            query_output: Output from the query
            sensitive_data: Sensitive data that should not appear
            check_substring: If True, check for substrings too
        
        Returns:
            True if no leakage detected
        """
        output_str = str(query_output)
        
        if isinstance(sensitive_data, (list, tuple)):
            for item in sensitive_data:
                item_str = str(item)
                if check_substring:
                    assert item_str not in output_str, \
                        f"Data leakage: '{item_str}' found in output"
                else:
                    assert item_str != output_str, \
                        f"Data leakage: exact match with '{item_str}'"
        else:
            sensitive_str = str(sensitive_data)
            if check_substring:
                assert sensitive_str not in output_str, \
                    f"Data leakage: '{sensitive_str}' found in output"
            else:
                assert sensitive_str != output_str, \
                    f"Data leakage: exact match with '{sensitive_str}'"
        
        return True
