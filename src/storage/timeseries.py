"""Time-series storage for metrics data."""
import time
import math
import logging
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class TimeSeriesStore:
    """Efficient time-series data storage with aggregation."""
    
    def __init__(self, retention_seconds: int = 86400 * 7, max_points: int = 100000):
        self.retention_seconds = retention_seconds
        self.max_points = max_points
        self._series: Dict[str, List[TimeSeriesPoint]] = defaultdict(list)
        self._metadata: Dict[str, Dict] = {}
        self._write_count = 0
        self._query_count = 0
    
    def write(self, series_name: str, value: float, timestamp: Optional[float] = None,
              labels: Optional[Dict[str, str]] = None) -> None:
        """Write a single data point."""
        ts = timestamp or time.time()
        point = TimeSeriesPoint(timestamp=ts, value=value, labels=labels or {})
        self._series[series_name].append(point)
        self._write_count += 1
        
        # Update metadata
        if series_name not in self._metadata:
            self._metadata[series_name] = {"first_ts": ts, "last_ts": ts, "count": 0}
        self._metadata[series_name]["last_ts"] = ts
        self._metadata[series_name]["count"] += 1
        
        # Enforce limits
        self._enforce_limits(series_name)
    
    def write_batch(self, series_name: str, points: List[Dict[str, Any]]) -> int:
        """Write multiple data points."""
        count = 0
        for p in points:
            self.write(series_name, p.get("value", 0), p.get("timestamp"), p.get("labels"))
            count += 1
        return count
    
    def query(self, series_name: str, start: Optional[float] = None,
              end: Optional[float] = None, limit: int = 1000) -> List[TimeSeriesPoint]:
        """Query points within a time range."""
        self._query_count += 1
        points = self._series.get(series_name, [])
        
        if start:
            points = [p for p in points if p.timestamp >= start]
        if end:
            points = [p for p in points if p.timestamp <= end]
        
        return points[:limit]
    
    def aggregate(self, series_name: str, window_seconds: int = 300,
                  aggregation: str = "avg", start: Optional[float] = None,
                  end: Optional[float] = None) -> List[Dict[str, Any]]:
        """Aggregate points into time windows."""
        points = self.query(series_name, start, end)
        if not points:
            return []
        
        now = end or time.time()
        start_time = start or (now - self.retention_seconds)
        windows = []
        
        window_start = start_time
        while window_start < now:
            window_end = window_start + window_seconds
            window_points = [p for p in points if window_start <= p.timestamp < window_end]
            
            if window_points:
                values = [p.value for p in window_points]
                agg_value = self._aggregate_values(values, aggregation)
                windows.append({
                    "start": window_start,
                    "end": window_end,
                    "value": agg_value,
                    "count": len(values),
                })
            
            window_start = window_end
        
        return windows
    
    def downsample(self, series_name: str, target_points: int = 100) -> List[TimeSeriesPoint]:
        """Downsample a series to target number of points."""
        points = self._series.get(series_name, [])
        if len(points) <= target_points:
            return points
        
        step = len(points) // target_points
        return [points[i] for i in range(0, len(points), step)][:target_points]
    
    def latest(self, series_name: str) -> Optional[float]:
        """Get the latest value in a series."""
        points = self._series.get(series_name, [])
        return points[-1].value if points else None
    
    def series_names(self) -> List[str]:
        """Get all series names."""
        return list(self._series.keys())
    
    def series_info(self, series_name: str) -> Dict[str, Any]:
        """Get metadata about a series."""
        points = self._series.get(series_name, [])
        meta = self._metadata.get(series_name, {})
        values = [p.value for p in points]
        
        return {
            "name": series_name,
            "point_count": len(points),
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "avg": sum(values) / len(values) if values else None,
            "first_timestamp": meta.get("first_ts", 0),
            "last_timestamp": meta.get("last_ts", 0),
            "duration_seconds": meta.get("last_ts", 0) - meta.get("first_ts", 0),
        }
    
    def delete_series(self, series_name: str) -> bool:
        """Delete an entire series."""
        if series_name in self._series:
            del self._series[series_name]
            self._metadata.pop(series_name, None)
            return True
        return False
    
    def prune(self, max_age_seconds: Optional[int] = None) -> int:
        """Remove old data points."""
        age = max_age_seconds or self.retention_seconds
        cutoff = time.time() - age
        pruned = 0
        
        for name in list(self._series.keys()):
            before = len(self._series[name])
            self._series[name] = [p for p in self._series[name] if p.timestamp >= cutoff]
            pruned += before - len(self._series[name])
        
        return pruned
    
    def stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        total_points = sum(len(v) for v in self._series.values())
        return {
            "series_count": len(self._series),
            "total_points": total_points,
            "write_count": self._write_count,
            "query_count": self._query_count,
            "retention_seconds": self.retention_seconds,
            "max_points": self.max_points,
        }
    
    def _aggregate_values(self, values: List[float], method: str) -> float:
        if not values:
            return 0.0
        if method == "avg":
            return sum(values) / len(values)
        elif method == "sum":
            return sum(values)
        elif method == "min":
            return min(values)
        elif method == "max":
            return max(values)
        elif method == "count":
            return float(len(values))
        elif method == "p50":
            s = sorted(values)
            return s[len(s) // 2]
        elif method == "p95":
            s = sorted(values)
            return s[int(len(s) * 0.95)]
        elif method == "p99":
            s = sorted(values)
            return s[min(int(len(s) * 0.99), len(s) - 1)]
        elif method == "stddev":
            if len(values) < 2:
                return 0.0
            mean = sum(values) / len(values)
            return (sum((x - mean) ** 2 for x in values) / (len(values) - 1)) ** 0.5
        return sum(values) / len(values)
    
    def _enforce_limits(self, series_name: str) -> None:
        points = self._series[series_name]
        if len(points) > self.max_points:
            self._series[series_name] = points[-self.max_points:]
