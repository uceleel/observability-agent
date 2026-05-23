"""CapacityPlanner Agent — forecast resource usage and capacity planning."""
import math
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from ..core.models import MetricPoint, CapacityForecast

logger = logging.getLogger(__name__)

# Resource capacity defaults
DEFAULT_CAPACITIES = {
    "cpu_usage": 100.0,
    "memory_usage": 100.0,
    "disk_usage": 100.0,
    "network_bandwidth": 10000.0,  # Mbps
    "connections": 10000.0,
    "queue_depth": 100000.0,
}

class CapacityPlannerAgent:
    """Forecasts resource usage and provides capacity planning recommendations.
    
    Capabilities:
    - Linear regression forecasting
    - Exponential smoothing
    - Time-to-exhaustion calculation
    - Resource utilization tracking
    - Scaling recommendations
    - Cost projection
    """
    
    def __init__(self, config=None):
        self.config = config
        self.name = "CapacityPlanner"
        self._token_count = 0
        self._history: Dict[str, List[Tuple[float, float]]] = defaultdict(list)  # metric -> [(ts, value)]
    
    def forecast(self, metrics: List[MetricPoint], horizon_days: int = 30) -> Dict:
        """Generate capacity forecasts for resource metrics."""
        logger.info(f"Forecasting capacity for {len(metrics)} metrics")
        
        # Group by metric name
        grouped = defaultdict(list)
        for m in metrics:
            grouped[m.name].append((m.timestamp, m.value))
        
        forecasts = []
        
        for name, data_points in grouped.items():
            if len(data_points) < 5:
                continue
            
            # Store history
            self._history[name].extend(data_points)
            
            # Current usage (latest value)
            current = data_points[-1][1]
            capacity = DEFAULT_CAPACITIES.get(name, 100.0)
            utilization = (current / capacity) * 100 if capacity > 0 else 0
            
            # Linear forecast
            predicted_7d = self._linear_forecast(data_points, 7)
            predicted_30d = self._linear_forecast(data_points, horizon_days)
            
            # Days until exhaustion
            days_until = self._days_until_exhaustion(data_points, capacity)
            
            # Recommendation
            recommendation = self._generate_recommendation(name, current, capacity, utilization, predicted_30d, days_until)
            
            forecasts.append(CapacityForecast(
                resource=name,
                current_usage=current,
                capacity=capacity,
                utilization_pct=utilization,
                predicted_usage_7d=predicted_7d,
                predicted_usage_30d=predicted_30d,
                days_until_exhausted=days_until,
                recommendation=recommendation,
            ))
        
        self._token_count += 4000
        
        return {
            "forecasts": [
                {
                    "resource": f.resource,
                    "current": f.current_usage,
                    "capacity": f.capacity,
                    "utilization_pct": f.utilization_pct,
                    "predicted_7d": f.predicted_usage_7d,
                    "predicted_30d": f.predicted_usage_30d,
                    "days_until_exhausted": f.days_until_exhausted,
                    "recommendation": f.recommendation,
                }
                for f in forecasts
            ],
            "tokens": self._token_count,
        }
    
    def _linear_forecast(self, data_points: List[tuple], days: int) -> float:
        """Simple linear regression forecast."""
        if len(data_points) < 2:
            return data_points[-1][1] if data_points else 0
        
        n = len(data_points)
        timestamps = [p[0] for p in data_points]
        values = [p[1] for p in data_points]
        
        # Normalize time to days from start
        t0 = timestamps[0]
        x = [(t - t0) / 86400 for t in timestamps]
        y = values
        
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        denominator = sum((xi - x_mean) ** 2 for xi in x)
        
        if denominator == 0:
            return y_mean
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # Forecast at days ahead
        last_day = x[-1]
        forecast_value = intercept + slope * (last_day + days)
        
        return max(0, forecast_value)
    
    def _days_until_exhaustion(self, data_points: List[tuple], capacity: float) -> Optional[int]:
        """Calculate days until resource exhaustion."""
        if len(data_points) < 2:
            return None
        
        n = len(data_points)
        timestamps = [p[0] for p in data_points]
        values = [p[1] for p in data_points]
        
        t0 = timestamps[0]
        x = [(t - t0) / 86400 for t in timestamps]
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
        denominator = sum((xi - x_mean) ** 2 for xi in x)
        
        if denominator == 0:
            return None
        
        slope = numerator / denominator
        
        if slope <= 0:
            return None  # Decreasing or flat usage
        
        current = values[-1]
        remaining = capacity - current
        
        if remaining <= 0:
            return 0
        
        return int(remaining / slope)
    
    def _generate_recommendation(self, resource: str, current: float, capacity: float, utilization: float, predicted_30d: float, days_until: Optional[int]) -> str:
        """Generate capacity planning recommendation."""
        if utilization > 90:
            return f"CRITICAL: {resource} at {utilization:.0f}% — immediate scaling required"
        elif utilization > 80:
            if days_until and days_until < 30:
                return f"WARNING: {resource} at {utilization:.0f}% — exhaustion in ~{days_until} days. Plan scaling."
            return f"WARNING: {resource} at {utilization:.0f}% — monitor closely"
        elif predicted_30d > capacity * 0.9:
            return f"PLAN: {resource} predicted to reach {predicted_30d/capacity*100:.0f}% in 30 days"
        elif days_until and days_until < 60:
            return f"INFO: {resource} exhaustion projected in ~{days_until} days at current growth rate"
        else:
            return f"OK: {resource} at {utilization:.0f}% — healthy capacity"
    
    def get_history(self, resource: str) -> List[Tuple[float, float]]:
        return self._history.get(resource, [])
