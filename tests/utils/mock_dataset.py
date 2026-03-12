"""
Mock dataset generator for testing
"""

import pandas as pd
import numpy as np
from typing import Literal, Optional


class MockDataset:
    """
    Generate mock datasets for testing
    
    Example:
        >>> dataset = MockDataset(rows=100, columns=['age', 'salary'])
        >>> df = dataset.generate()
        >>> assert len(df) == 100
        >>> assert 'age' in df.columns
    """
    
    COLUMN_TYPES = {
        # Numeric columns
        'age': ('int', 18, 80),
        'salary': ('float', 30000, 200000),
        'temperature': ('float', -20, 40),
        'humidity': ('float', 0, 100),
        'score': ('int', 0, 100),
        'count': ('int', 0, 1000),
        'revenue': ('float', 0, 1000000),
        'price': ('float', 0, 10000),
        
        # Categorical columns
        'category': ('category', ['A', 'B', 'C', 'D']),
        'region': ('category', ['North', 'South', 'East', 'West']),
        'status': ('category', ['Active', 'Inactive', 'Pending']),
        'department': ('category', ['Engineering', 'Sales', 'Marketing', 'HR']),
        'product': ('category', ['Product A', 'Product B', 'Product C']),
        
        # String columns
        'name': ('string', None),
        'email': ('email', None),
        'id': ('id', None),
    }
    
    def __init__(
        self,
        rows: int = 100,
        columns: Optional[list[str]] = None,
        seed: Optional[int] = None
    ):
        """
        Initialize mock dataset generator
        
        Args:
            rows: Number of rows to generate
            columns: List of column names (uses defaults if None)
            seed: Random seed for reproducibility
        """
        self.rows = rows
        self.columns = columns or ['id', 'category', 'value', 'score']
        self.seed = seed
        
        if seed is not None:
            np.random.seed(seed)
    
    def generate(self) -> pd.DataFrame:
        """Generate the mock dataset"""
        data = {}
        
        for col in self.columns:
            if col in self.COLUMN_TYPES:
                col_type, *params = self.COLUMN_TYPES[col]
                data[col] = self._generate_column(col, col_type, params)
            else:
                # Default to random float
                data[col] = np.random.uniform(0, 100, self.rows)
        
        return pd.DataFrame(data)
    
    def _generate_column(self, name: str, col_type: str, params: list) -> np.ndarray:
        """Generate a single column"""
        if col_type == 'int':
            low, high = params
            return np.random.randint(low, high, self.rows)
        
        elif col_type == 'float':
            low, high = params
            return np.random.uniform(low, high, self.rows)
        
        elif col_type == 'category':
            categories = params[0]
            return np.random.choice(categories, self.rows)
        
        elif col_type == 'string':
            return [f"{name}_{i}" for i in range(self.rows)]
        
        elif col_type == 'email':
            return [f"user{i}@example.com" for i in range(self.rows)]
        
        elif col_type == 'id':
            return [f"{name.upper()}{i:04d}" for i in range(self.rows)]
        
        else:
            return np.random.uniform(0, 100, self.rows)
    
    def with_missing_values(self, fraction: float = 0.1) -> pd.DataFrame:
        """
        Generate dataset with missing values
        
        Args:
            fraction: Fraction of values to set as NaN (0.0 to 1.0)
        """
        df = self.generate()
        
        # Randomly set some values to NaN
        mask = np.random.random(df.shape) < fraction
        df = df.mask(mask)
        
        return df
    
    def with_outliers(self, fraction: float = 0.05) -> pd.DataFrame:
        """
        Generate dataset with outliers in numeric columns
        
        Args:
            fraction: Fraction of rows to make outliers
        """
        df = self.generate()
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        num_outliers = int(self.rows * fraction)
        
        for col in numeric_cols:
            outlier_indices = np.random.choice(self.rows, num_outliers, replace=False)
            mean = df[col].mean()
            std = df[col].std()
            
            # Set outliers to 5 standard deviations from mean
            df.loc[outlier_indices, col] = mean + (5 * std * np.random.choice([-1, 1], num_outliers))
        
        return df
    
    def with_correlation(self, col1: str, col2: str, correlation: float = 0.8) -> pd.DataFrame:
        """
        Generate dataset with correlated columns
        
        Args:
            col1: First column name
            col2: Second column name
            correlation: Correlation coefficient (-1 to 1)
        """
        df = self.generate()
        
        if col1 in df.columns and col2 in df.columns:
            # Generate correlated values
            x = df[col1].values
            noise = np.random.normal(0, 1, self.rows)
            y = correlation * x + np.sqrt(1 - correlation**2) * noise
            
            # Scale to match original range
            y = (y - y.min()) / (y.max() - y.min())
            y = y * (df[col2].max() - df[col2].min()) + df[col2].min()
            
            df[col2] = y
        
        return df
    
    @classmethod
    def from_schema(cls, schema: dict, rows: int = 100, seed: Optional[int] = None) -> pd.DataFrame:
        """
        Generate dataset from schema definition
        
        Args:
            schema: Dictionary mapping column names to types
            rows: Number of rows
            seed: Random seed
        
        Example:
            >>> schema = {'age': 'int', 'name': 'string', 'score': 'float'}
            >>> df = MockDataset.from_schema(schema, rows=50)
        """
        generator = cls(rows=rows, columns=list(schema.keys()), seed=seed)
        return generator.generate()
