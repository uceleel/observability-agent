"""Dashboard metrics processor for real-time observability visualization."""
import time
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TimeWindow:
    """Time window for metric aggregation."""
    start: float
    end: float
    label: str = ""
    
    @property
    def duration(self) -> float:
        return self.end - self.start
    
    def contains(self, timestamp: float) -> bool:
        return self.start <= timestamp <= self.end


@dataclass
class MetricWidget:
    """Dashboard widget configuration."""
    widget_id: str
    title: str
    metric_name: str
    widget_type: str = "line"  # line, gauge, heatmap, table, stat
    aggregation: str = "avg"
    window_seconds: int = 300
    refresh_seconds: int = 30
    thresholds: Dict[str, float] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    position: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.widget_id,
            "title": self.title,
            "metric": self.metric_name,
            "type": self.widget_type,
            "agg": self.aggregation,
            "window": self.window_seconds,
            "refresh": self.refresh_seconds,
            "thresholds": self.thresholds,
        }


class MetricsProcessor:
    """Process metrics for dashboard visualization."""
    
    def __init__(self, max_points: int = 1000):
        self.max_points = max_points
        self._buffer: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        self._widgets: Dict[str, MetricWidget] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._default_widgets()
    
    def _default_widgets(self) -> None:
        """Initialize default dashboard widgets."""
        defaults = [
            MetricWidget("cpu_usage", "CPU Usage", "cpu_usage", "gauge", "avg", 60, 15, {"warn": 70, "crit": 90}),
            MetricWidget("memory_usage", "Memory Usage", "memory_usage", "gauge", "avg", 60, 15, {"warn": 80, "crit": 95}),
            MetricWidget("request_rate", "Request Rate", "request_count", "line", "sum", 300, 30),
            MetricWidget("error_rate", "Error Rate", "error_count", "line", "sum", 300, 30, {"warn": 1, "crit": 5}),
            MetricWidget("latency_p50", "Latency P50", "request_latency", "line", "p50", 300, 30, {"warn": 500, "crit": 2000}),
            MetricWidget("latency_p99", "Latency P99", "request_latency", "line", "p99", 300, 30, {"warn": 2000, "crit": 5000}),
            MetricWidget("disk_io", "Disk I/O", "disk_io_bytes", "line", "sum", 300, 60),
            MetricWidget("network_io", "Network I/O", "network_bytes", "line", "sum", 300, 60),
            MetricWidget("active_connections", "Active Connections", "connection_count", "stat", "avg", 60, 10),
            MetricWidget("queue_depth", "Queue Depth", "queue_size", "gauge", "max", 120, 15, {"warn": 1000, "crit": 5000}),
        ]
        for w in defaults:
            self._widgets[w.widget_id] = w
    
    def ingest(self, metric_name: str, value: float, timestamp: Optional[float] = None) -> None:
        """Ingest a single metric data point."""
        ts = timestamp or time.time()
        self._buffer[metric_name].append((ts, value))
        
        # Trim buffer
        if len(self._buffer[metric_name]) > self.max_points:
            self._buffer[metric_name] = self._buffer[metric_name][-self.max_points:]
        
        # Invalidate cache for this metric
        self._cache.pop(metric_name, None)
    
    def ingest_batch(self, metrics: List[Dict[str, Any]]) -> int:
        """Ingest multiple metric data points."""
        count = 0
        for m in metrics:
            name = m.get("name", "")
            value = m.get("value", 0.0)
            ts = m.get("timestamp", time.time())
            if name:
                self.ingest(name, value, ts)
                count += 1
        return count
    
    def query(self, metric_name: str, window_seconds: int = 300, aggregation: str = "avg") -> Optional[float]:
        """Query aggregated metric value."""
        cache_key = f"{metric_name}:{window_seconds}:{aggregation}"
        if cache_key in self._cache:
            if time.time() - self._cache_ttl.get(cache_key, 0) < 5:
                return self._cache[cache_key]
        
        cutoff = time.time() - window_seconds
        values = [v for ts, v in self._buffer.get(metric_name, []) if ts >= cutoff]
        
        if not values:
            return None
        
        result = self._aggregate(values, aggregation)
        self._cache[cache_key] = result
        self._cache_ttl[cache_key] = time.time()
        return result
    
    def _aggregate(self, values: List[float], method: str) -> float:
        """Aggregate values using specified method."""
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
    
    def get_widget_data(self, widget_id: str) -> Dict[str, Any]:
        """Get data for a specific widget."""
        widget = self._widgets.get(widget_id)
        if not widget:
            return {"error": f"Widget {widget_id} not found"}
        
        value = self.query(widget.metric_name, widget.window_seconds, widget.aggregation)
        
        status = "ok"
        if value is not None and widget.thresholds:
            if "crit" in widget.thresholds and value >= widget.thresholds["crit"]:
                status = "critical"
            elif "warn" in widget.thresholds and value >= widget.thresholds["warn"]:
                status = "warning"
        
        return {
            "widget": widget.to_dict(),
            "value": value,
            "status": status,
            "timestamp": time.time(),
        }
    
    def get_dashboard(self) -> Dict[str, Any]:
        """Get full dashboard data."""
        dashboard = {
            "widgets": [],
            "generated_at": time.time(),
            "metric_count": len(self._buffer),
            "total_points": sum(len(v) for v in self._buffer.values()),
        }
        
        for widget_id in self._widgets:
            dashboard["widgets"].append(self.get_widget_data(widget_id))
        
        return dashboard
    
    def get_metric_names(self) -> List[str]:
        """Get all available metric names."""
        return list(self._buffer.keys())
    
    def get_metric_stats(self) -> Dict[str, Dict]:
        """Get statistics for all metrics."""
        stats = {}
        for name, points in self._buffer.items():
            values = [v for _, v in points]
            if values:
                stats[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "latest": values[-1] if values else None,
                    "oldest_ts": points[0][0] if points else 0,
                    "newest_ts": points[-1][0] if points else 0,
                }
        return stats
    
    def add_widget(self, widget: MetricWidget) -> None:
        """Add a custom widget."""
        self._widgets[widget.widget_id] = widget
    
    def remove_widget(self, widget_id: str) -> bool:
        """Remove a widget."""
        if widget_id in self._widgets:
            del self._widgets[widget_id]
            return True
        return False
    
    def clear_buffer(self, metric_name: Optional[str] = None) -> None:
        """Clear metric buffer."""
        if metric_name:
            self._buffer.pop(metric_name, None)
        else:
            self._buffer.clear()
        self._cache.clear()


class TopologyMapper:
    """Map service dependencies from trace data."""
    
    def __init__(self):
        self._edges: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._errors: Dict[str, int] = defaultdict(int)
    
    def add_trace(self, spans: List[Dict[str, Any]]) -> None:
        """Process trace spans to build topology."""
        for i, span in enumerate(spans):
            service = span.get("service", "unknown")
            parent_service = None
            
            for other in spans:
                if other.get("span_id") == span.get("parent_id"):
                    parent_service = other.get("service", "unknown")
                    break
            
            if parent_service and parent_service != service:
                self._edges[parent_service][service] += 1
                duration = span.get("duration_ms", 0)
                key = f"{parent_service}->{service}"
                self._latencies[key].append(duration)
                if span.get("error", False):
                    self._errors[key] += 1
    
    def get_topology(self) -> Dict[str, Any]:
        """Get full service topology graph."""
        nodes = set()
        edges = []
        for src, targets in self._edges.items():
            nodes.add(src)
            for dst, count in targets.items():
                nodes.add(dst)
                key = f"{src}->{dst}"
                latencies = self._latencies.get(key, [])
                avg_lat = sum(latencies) / len(latencies) if latencies else 0
                edges.append({
                    "source": src,
                    "target": dst,
                    "request_count": count,
                    "avg_latency_ms": round(avg_lat, 2),
                    "error_count": self._errors.get(key, 0),
                    "error_rate": round(self._errors.get(key, 0) / count * 100, 2) if count > 0 else 0,
                })
        
        return {
            "nodes": [{"id": n, "name": n} for n in sorted(nodes)],
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }
    
    def get_critical_path(self) -> List[Dict]:
        """Find the critical path (highest latency chain)."""
        if not self._latencies:
            return []
        
        sorted_edges = sorted(
            self._latencies.items(),
            key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0,
            reverse=True,
        )
        
        return [
            {
                "edge": key,
                "avg_latency_ms": round(sum(vals) / len(vals), 2),
                "p99_latency_ms": round(sorted(vals)[int(len(vals) * 0.99)] if vals else 0, 2),
                "request_count": len(vals),
            }
            for key, vals in sorted_edges[:10]
        ]
    
    def reset(self) -> None:
        """Reset topology data."""
        self._edges.clear()
        self._latencies.clear()
        self._errors.clear()
