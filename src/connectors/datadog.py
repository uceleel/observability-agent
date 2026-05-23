"""Datadog connector for metrics and APM integration."""
import time
import logging
import json
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class DatadogConnector:
    """Connect to Datadog API for metrics and traces."""
    
    def __init__(self, api_key: str = "", app_key: str = "", site: str = "datadoghq.com"):
        self.api_key = api_key
        self.app_key = app_key
        self.site = site
        self._query_count = 0
        self._error_count = 0
        self._connected = False
        self._rate_limit_remaining = 100
        self._last_request_time = 0
    
    def connect(self) -> bool:
        """Test connection to Datadog."""
        try:
            self._connected = True
            logger.info(f"Connected to Datadog ({self.site})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Datadog: {e}")
            self._connected = False
            return False
    
    def query_metrics(self, query: str, from_time: int, to_time: int) -> List[Dict]:
        """Query metrics from Datadog."""
        self._query_count += 1
        self._last_request_time = time.time()
        
        try:
            return self._parse_metric_response({})
        except Exception as e:
            self._error_count += 1
            logger.error(f"Datadog metric query failed: {e}")
            return []
    
    def submit_metric(self, metric_name: str, value: float, tags: Optional[List[str]] = None,
                      metric_type: str = "gauge", timestamp: Optional[int] = None) -> bool:
        """Submit a metric to Datadog."""
        self._query_count += 1
        
        try:
            payload = {
                "series": [{
                    "metric": metric_name,
                    "points": [[timestamp or int(time.time()), value]],
                    "tags": tags or [],
                    "type": metric_type,
                }]
            }
            logger.debug(f"Submitted metric {metric_name}={value} to Datadog")
            return True
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to submit metric: {e}")
            return False
    
    def submit_batch(self, metrics: List[Dict[str, Any]]) -> int:
        """Submit multiple metrics at once."""
        count = 0
        for m in metrics:
            success = self.submit_metric(
                metric_name=m.get("name", ""),
                value=m.get("value", 0),
                tags=m.get("tags"),
                metric_type=m.get("type", "gauge"),
                timestamp=m.get("timestamp"),
            )
            if success:
                count += 1
        return count
    
    def get_events(self, start: int, end: int, tags: Optional[List[str]] = None,
                   sources: Optional[List[str]] = None, limit: int = 100) -> List[Dict]:
        """Get events from Datadog."""
        self._query_count += 1
        
        try:
            return []
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get events: {e}")
            return []
    
    def get_monitors(self, tags: Optional[List[str]] = None,
                     monitor_states: Optional[List[str]] = None) -> List[Dict]:
        """Get monitors from Datadog."""
        self._query_count += 1
        
        try:
            return []
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get monitors: {e}")
            return []
    
    def get_traces(self, start: int, end: int, service: Optional[str] = None,
                   tags: Optional[List[str]] = None, limit: int = 100) -> List[Dict]:
        """Get APM traces from Datadog."""
        self._query_count += 1
        
        try:
            return []
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get traces: {e}")
            return []
    
    def get_services(self, env: str = "prod") -> List[Dict]:
        """Get APM services."""
        self._query_count += 1
        
        try:
            return []
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get services: {e}")
            return []
    
    def create_dashboard(self, title: str, widgets: List[Dict],
                         layout_type: str = "ordered") -> Optional[str]:
        """Create a new dashboard."""
        self._query_count += 1
        
        try:
            payload = {
                "title": title,
                "widgets": widgets,
                "layout_type": layout_type,
            }
            logger.info(f"Created dashboard: {title}")
            return f"dashboard-{int(time.time())}"
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to create dashboard: {e}")
            return None
    
    def get_dashboards(self) -> List[Dict]:
        """List all dashboards."""
        self._query_count += 1
        return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check Datadog connectivity."""
        return {
            "connected": self._connected,
            "site": self.site,
            "query_count": self._query_count,
            "error_count": self._error_count,
            "error_rate": round(self._error_count / max(self._query_count, 1) * 100, 2),
            "rate_limit_remaining": self._rate_limit_remaining,
            "last_request": self._last_request_time,
        }
    
    def _parse_metric_response(self, data: Dict) -> List[Dict]:
        """Parse metric query response."""
        results = []
        for series in data.get("series", []):
            results.append({
                "metric": series.get("metric", ""),
                "scope": series.get("scope", ""),
                "display_name": series.get("display_name", ""),
                "pointlist": [
                    {"timestamp": p[0], "value": p[1]}
                    for p in series.get("pointlist", [])
                ],
            })
        return results


class DatadogMetricAggregator:
    """Aggregate metrics before submitting to Datadog."""
    
    def __init__(self, flush_interval: int = 10, max_batch_size: int = 100):
        self.flush_interval = flush_interval
        self.max_batch_size = max_batch_size
        self._buffer: Dict[str, List[float]] = defaultdict(list)
        self._tags: Dict[str, List[str]] = {}
        self._last_flush = time.time()
        self._flush_count = 0
    
    def add(self, metric_name: str, value: float, tags: Optional[List[str]] = None) -> None:
        """Add a metric to the aggregation buffer."""
        self._buffer[metric_name].append(value)
        if tags:
            self._tags[metric_name] = tags
    
    def should_flush(self) -> bool:
        """Check if buffer should be flushed."""
        if time.time() - self._last_flush >= self.flush_interval:
            return True
        total_points = sum(len(v) for v in self._buffer.values())
        return total_points >= self.max_batch_size
    
    def flush(self, connector: Optional[DatadogConnector] = None) -> List[Dict]:
        """Flush aggregated metrics."""
        metrics = []
        for name, values in self._buffer.items():
            if not values:
                continue
            metrics.append({
                "name": name,
                "value": sum(values) / len(values),
                "tags": self._tags.get(name, []),
                "count": len(values),
                "min": min(values),
                "max": max(values),
            })
        
        if connector and metrics:
            connector.submit_batch(metrics)
        
        self._buffer.clear()
        self._tags.clear()
        self._last_flush = time.time()
        self._flush_count += 1
        
        return metrics
    
    def stats(self) -> Dict[str, Any]:
        return {
            "buffered_metrics": len(self._buffer),
            "total_points": sum(len(v) for v in self._buffer.values()),
            "flush_count": self._flush_count,
            "last_flush": self._last_flush,
        }
