"""Statistical utility functions."""
import math
from typing import List, Optional, Tuple

class Statistics:
    """Statistical calculations for metric analysis."""
    
    @staticmethod
    def mean(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0
    
    @staticmethod
    def median(values: List[float]) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        n = len(sorted_v)
        if n % 2 == 0:
            return (sorted_v[n//2-1] + sorted_v[n//2]) / 2
        return sorted_v[n//2]
    
    @staticmethod
    def stddev(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        m = Statistics.mean(values)
        variance = sum((v - m)**2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    @staticmethod
    def percentile(values: List[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        k = (len(sorted_v) - 1) * (p / 100)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_v[int(k)]
        return sorted_v[int(f)] * (c - k) + sorted_v[int(c)] * (k - f)
    
    @staticmethod
    def z_score(value: float, mean: float, stddev: float) -> float:
        if stddev == 0:
            return 0.0
        return (value - mean) / stddev
    
    @staticmethod
    def linear_regression(x: List[float], y: List[float]) -> Tuple[float, float]:
        """Returns (slope, intercept)."""
        n = len(x)
        if n < 2:
            return 0.0, 0.0
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        den = sum((xi - x_mean)**2 for xi in x)
        if den == 0:
            return 0.0, y_mean
        slope = num / den
        intercept = y_mean - slope * x_mean
        return slope, intercept
    
    @staticmethod
    def moving_average(values: List[float], window: int) -> List[float]:
        if len(values) < window:
            return values
        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            result.append(sum(values[start:i+1]) / (i - start + 1))
        return result
    
    @staticmethod
    def exponential_smoothing(values: List[float], alpha: float = 0.3) -> List[float]:
        if not values:
            return []
        result = [values[0]]
        for i in range(1, len(values)):
            result.append(alpha * values[i] + (1 - alpha) * result[-1])
        return result
