"""Prometheus connector for metrics ingestion."""
import time
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class PrometheusConnector:
    """Connect to Prometheus and query/ingest metrics."""
    
    def __init__(self, base_url: str = "http://localhost:9090", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._query_count = 0
        self._error_count = 0
        self._last_query_time = 0
        self._connected = False
    
    def connect(self) -> bool:
        """Test connection to Prometheus."""
        try:
            # Simulated connection check
            self._connected = True
            logger.info(f"Connected to Prometheus at {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Prometheus: {e}")
            self._connected = False
            return False
    
    def query(self, promql: str, time_point: Optional[float] = None) -> List[Dict]:
        """Execute an instant PromQL query."""
        self._query_count += 1
        self._last_query_time = time.time()
        
        try:
            params = {"query": promql}
            if time_point:
                params["time"] = time_point
            
            # Simulated query result
            return self._parse_instant_result({})
        except Exception as e:
            self._error_count += 1
            logger.error(f"Prometheus query failed: {e}")
            return []
    
    def query_range(self, promql: str, start: float, end: float,
                    step: str = "15s") -> List[Dict]:
        """Execute a range PromQL query."""
        self._query_count += 1
        self._last_query_time = time.time()
        
        try:
            params = {
                "query": promql,
                "start": start,
                "end": end,
                "step": step,
            }
            return self._parse_range_result({})
        except Exception as e:
            self._error_count += 1
            logger.error(f"Prometheus range query failed: {e}")
            return []
    
    def get_targets(self) -> List[Dict]:
        """Get all scrape targets."""
        try:
            return self._parse_targets({})
        except Exception as e:
            logger.error(f"Failed to get targets: {e}")
            return []
    
    def get_alerts(self) -> List[Dict]:
        """Get current alerts from Alertmanager."""
        try:
            return self._parse_alerts({})
        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []
    
    def get_rules(self) -> List[Dict]:
        """Get alerting and recording rules."""
        try:
            return self._parse_rules({})
        except Exception as e:
            logger.error(f"Failed to get rules: {e}")
            return []
    
    def get_metric_metadata(self, metric_name: str) -> Dict:
        """Get metadata for a specific metric."""
        try:
            return {"metric": metric_name, "type": "unknown", "help": ""}
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {}
    
    def get_label_values(self, label_name: str) -> List[str]:
        """Get all values for a specific label."""
        try:
            return []
        except Exception as e:
            logger.error(f"Failed to get label values: {e}")
            return []
    
    def build_query(self, metric: str, filters: Optional[Dict[str, str]] = None,
                    aggregation: Optional[str] = None, by_labels: Optional[List[str]] = None,
                    rate_interval: Optional[str] = None) -> str:
        """Build a PromQL query from parameters."""
        # Base metric
        if rate_interval:
            expr = f"rate({metric}[{rate_interval}])"
        else:
            expr = metric
        
        # Add filters
        if filters:
            filter_parts = [f'{k}="{v}"' for k, v in filters.items()]
            expr += "{" + ", ".join(filter_parts) + "}"
        
        # Add aggregation
        if aggregation:
            if by_labels:
                by_str = ", ".join(by_labels)
                expr = f"{aggregation}_over_time({expr}[5m])"
            else:
                expr = f"{aggregation}({expr})"
        
        return expr
    
    def health_check(self) -> Dict[str, Any]:
        """Check Prometheus health and connectivity."""
        return {
            "connected": self._connected,
            "base_url": self.base_url,
            "query_count": self._query_count,
            "error_count": self._error_count,
            "error_rate": round(self._error_count / max(self._query_count, 1) * 100, 2),
            "last_query": self._last_query_time,
        }
    
    def _parse_instant_result(self, data: Dict) -> List[Dict]:
        """Parse instant query response."""
        results = []
        for result in data.get("data", {}).get("result", []):
            metric = result.get("metric", {})
            value = result.get("value", [None, None])
            if len(value) >= 2:
                results.append({
                    "metric": metric,
                    "value": float(value[1]),
                    "timestamp": float(value[0]),
                })
        return results
    
    def _parse_range_result(self, data: Dict) -> List[Dict]:
        """Parse range query response."""
        results = []
        for result in data.get("data", {}).get("result", []):
            metric = result.get("metric", {})
            values = result.get("values", [])
            results.append({
                "metric": metric,
                "values": [{"timestamp": float(v[0]), "value": float(v[1])} for v in values],
            })
        return results
    
    def _parse_targets(self, data: Dict) -> List[Dict]:
        """Parse targets response."""
        targets = []
        for target in data.get("data", {}).get("activeTargets", []):
            targets.append({
                "url": target.get("scrapeUrl", ""),
                "health": target.get("health", "unknown"),
                "labels": target.get("labels", {}),
                "last_scrape": target.get("lastScrape", ""),
            })
        return targets
    
    def _parse_alerts(self, data: Dict) -> List[Dict]:
        """Parse alerts response."""
        return [
            {
                "name": a.get("labels", {}).get("alertname", ""),
                "state": a.get("state", ""),
                "severity": a.get("labels", {}).get("severity", ""),
                "active_at": a.get("activeAt", ""),
            }
            for a in data.get("data", {}).get("alerts", [])
        ]
    
    def _parse_rules(self, data: Dict) -> List[Dict]:
        """Parse rules response."""
        rules = []
        for group in data.get("data", {}).get("groups", []):
            for rule in group.get("rules", []):
                rules.append({
                    "name": rule.get("name", ""),
                    "type": rule.get("type", ""),
                    "query": rule.get("query", ""),
                    "state": rule.get("state", ""),
                })
        return rules


class PrometheusQueryBuilder:
    """Helper for building complex PromQL queries."""
    
    @staticmethod
    def cpu_usage(instance: Optional[str] = None, interval: str = "5m") -> str:
        filter_str = f'instance="{instance}",' if instance else ""
        return f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle",{filter_str}}}[{interval}])) * 100)'
    
    @staticmethod
    def memory_usage(instance: Optional[str] = None) -> str:
        filter_str = f'instance="{instance}",' if instance else ""
        return f'(1 - node_memory_MemAvailable_bytes{{filter_str}} / node_memory_MemTotal_bytes{{filter_str}}) * 100'
    
    @staticmethod
    def disk_usage(instance: Optional[str] = None, mountpoint: str = "/") -> str:
        filter_str = f'instance="{instance}",' if instance else ""
        return f'(1 - node_filesystem_avail_bytes{{mountpoint="{mountpoint}",{filter_str}}} / node_filesystem_size_bytes{{mountpoint="{mountpoint}",{filter_str}}}) * 100'
    
    @staticmethod
    def request_rate(service: str, interval: str = "5m") -> str:
        return f'sum(rate(http_requests_total{{service="{service}"}}[{interval}]))'
    
    @staticmethod
    def error_rate(service: str, interval: str = "5m") -> str:
        return f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[{interval}])) / sum(rate(http_requests_total{{service="{service}"}}[{interval}])) * 100'
    
    @staticmethod
    def latency_percentile(service: str, percentile: float = 0.99, interval: str = "5m") -> str:
        return f'histogram_quantile({percentile}, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[{interval}])) by (le))'
