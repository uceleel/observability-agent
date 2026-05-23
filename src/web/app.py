"""Web dashboard API for observability agent."""
import time
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DashboardAPI:
    """REST-like API for observability dashboard."""
    
    def __init__(self, orchestrator=None, metrics_processor=None):
        self.orchestrator = orchestrator
        self.metrics = metrics_processor
        self._routes: Dict[str, Any] = {}
        self._middleware: List[Any] = []
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Register API routes."""
        self._routes = {
            "/api/health": self.health,
            "/api/status": self.status,
            "/api/metrics": self.get_metrics,
            "/api/metrics/{name}": self.get_metric,
            "/api/alerts": self.get_alerts,
            "/api/alerts/active": self.get_active_alerts,
            "/api/alerts/history": self.get_alert_history,
            "/api/anomalies": self.get_anomalies,
            "/api/traces": self.get_traces,
            "/api/traces/{trace_id}": self.get_trace,
            "/api/logs": self.get_logs,
            "/api/logs/search": self.search_logs,
            "/api/capacity": self.get_capacity,
            "/api/topology": self.get_topology,
            "/api/dashboard": self.get_dashboard,
            "/api/dashboard/widgets": self.get_widgets,
            "/api/dashboard/widgets/{id}": self.get_widget,
            "/api/incidents": self.get_incidents,
            "/api/incidents/{id}": self.get_incident,
            "/api/rules": self.get_rules,
            "/api/config": self.get_config,
            "/api/stats": self.get_stats,
        }
    
    def health(self, **kwargs) -> Dict:
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime": self._uptime(),
            "version": "1.0.0",
        }
    
    def status(self, **kwargs) -> Dict:
        state = {}
        if self.orchestrator:
            state = {
                "pipeline_status": self.orchestrator.state.status,
                "agents": list(self.orchestrator.agents.keys()),
                "token_count": self.orchestrator._token_counter,
                "metrics_collected": self.orchestrator.state.metrics_collected,
                "anomalies_detected": self.orchestrator.state.anomalies_detected,
                "alerts_fired": self.orchestrator.state.alerts_fired,
            }
        return {"status": state, "timestamp": time.time()}
    
    def get_metrics(self, **kwargs) -> Dict:
        if not self.metrics:
            return {"error": "Metrics processor not available"}
        return {
            "metrics": self.metrics.get_metric_names(),
            "stats": self.metrics.get_metric_stats(),
            "total_points": sum(len(v) for v in self.metrics._buffer.values()),
        }
    
    def get_metric(self, name: str = "", **kwargs) -> Dict:
        if not self.metrics:
            return {"error": "Metrics processor not available"}
        stats = self.metrics.get_metric_stats()
        if name in stats:
            return {"metric": name, "data": stats[name]}
        return {"error": f"Metric '{name}' not found"}
    
    def get_alerts(self, **kwargs) -> Dict:
        return {"alerts": [], "count": 0}
    
    def get_active_alerts(self, **kwargs) -> Dict:
        return {"active_alerts": [], "count": 0}
    
    def get_alert_history(self, **kwargs) -> Dict:
        return {"history": [], "total": 0}
    
    def get_anomalies(self, **kwargs) -> Dict:
        return {"anomalies": [], "count": 0}
    
    def get_traces(self, **kwargs) -> Dict:
        return {"traces": [], "count": 0}
    
    def get_trace(self, trace_id: str = "", **kwargs) -> Dict:
        return {"trace_id": trace_id, "spans": []}
    
    def get_logs(self, **kwargs) -> Dict:
        return {"logs": [], "count": 0}
    
    def search_logs(self, **kwargs) -> Dict:
        query = kwargs.get("query", "")
        return {"query": query, "results": [], "count": 0}
    
    def get_capacity(self, **kwargs) -> Dict:
        return {"forecasts": [], "resources": []}
    
    def get_topology(self, **kwargs) -> Dict:
        return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}
    
    def get_dashboard(self, **kwargs) -> Dict:
        if self.metrics:
            return self.metrics.get_dashboard()
        return {"widgets": [], "generated_at": time.time()}
    
    def get_widgets(self, **kwargs) -> Dict:
        if self.metrics:
            dashboard = self.metrics.get_dashboard()
            return {"widgets": [w.get("widget", {}) for w in dashboard.get("widgets", [])]}
        return {"widgets": []}
    
    def get_widget(self, widget_id: str = "", **kwargs) -> Dict:
        if self.metrics:
            return self.metrics.get_widget_data(widget_id)
        return {"error": "Metrics processor not available"}
    
    def get_incidents(self, **kwargs) -> Dict:
        return {"incidents": [], "open_count": 0}
    
    def get_incident(self, incident_id: str = "", **kwargs) -> Dict:
        return {"incident_id": incident_id, "error": "Not found"}
    
    def get_rules(self, **kwargs) -> Dict:
        return {"rules": [], "count": 0}
    
    def get_config(self, **kwargs) -> Dict:
        return {
            "config": {
                "collection_interval": 30,
                "alert_cooldown": 300,
                "anomaly_threshold": 3.0,
                "retention_days": 30,
                "max_metrics": 10000,
                "dashboard_refresh": 15,
            }
        }
    
    def get_stats(self, **kwargs) -> Dict:
        stats = {
            "uptime_seconds": self._uptime(),
            "routes": len(self._routes),
            "middleware": len(self._middleware),
        }
        if self.metrics:
            stats["metric_count"] = len(self.metrics.get_metric_names())
            stats["total_points"] = sum(len(v) for v in self.metrics._buffer.values())
        if self.orchestrator:
            stats["agents"] = len(self.orchestrator.agents)
            stats["tokens_consumed"] = self.orchestrator._token_counter
        return stats
    
    def handle_request(self, path: str, method: str = "GET", **kwargs) -> Dict:
        """Route a request to its handler."""
        handler = self._routes.get(path)
        if handler:
            return handler(**kwargs)
        # Try pattern matching
        for route, h in self._routes.items():
            if "{" in route:
                parts = route.split("/")
                path_parts = path.split("/")
                if len(parts) == len(path_parts):
                    params = {}
                    match = True
                    for rp, pp in zip(parts, path_parts):
                        if rp.startswith("{") and rp.endswith("}"):
                            params[rp[1:-1]] = pp
                        elif rp != pp:
                            match = False
                            break
                    if match:
                        return h(**params, **kwargs)
        return {"error": "Not found", "path": path, "status": 404}
    
    def _uptime(self) -> float:
        return time.time() - getattr(self, "_start_time", time.time())
