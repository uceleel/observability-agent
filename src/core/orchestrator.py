"""Pipeline orchestrator for multi-agent observability workflow."""
import time
import logging
from typing import List, Optional, Dict, Any
from .config import Config
from .models import (
    MetricPoint, MetricSeries, Anomaly, Alert, AlertRule,
    LogEntry, TraceSpan, ServiceHealth, CapacityForecast,
    PipelineState, Severity, AlertState, MetricType
)

logger = logging.getLogger(__name__)

class Orchestrator:
    """Coordinates 6-agent observability pipeline.
    
    Pipeline:
    1. MetricCollector — ingest and normalize metrics
    2. AnomalyDetector — detect statistical anomalies
    3. AlertManager — evaluate rules and manage alerts
    4. LogAnalyzer — parse and analyze log patterns
    5. TraceCorrelator — correlate distributed traces
    6. CapacityPlanner — forecast resource usage
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.agents: Dict[str, Any] = {}
        self.state = PipelineState()
        self._token_counter = 0
    
    def register_agent(self, name: str, agent: Any):
        self.agents[name] = agent
        logger.info(f"Agent registered: {name}")
    
    def run_pipeline(self, metrics: List[MetricPoint], logs: Optional[List[LogEntry]] = None, traces: Optional[List[TraceSpan]] = None) -> Dict:
        """Run full observability pipeline."""
        self.state = PipelineState(status="running")
        results = {"metrics": [], "anomalies": [], "alerts": [], "log_insights": [], "trace_insights": [], "capacity": []}
        
        try:
            # Stage 1: Metric Collection
            if "metric_collector" in self.agents:
                self.state.add_log("orchestrator", "Running MetricCollector")
                mc_result = self.agents["metric_collector"].collect(metrics)
                results["metrics"] = mc_result.get("normalized", [])
                self._consume(mc_result.get("tokens", 3000))
                self.state.metrics_collected = len(results["metrics"])
            
            # Stage 2: Anomaly Detection
            if "anomaly_detector" in self.agents:
                self.state.add_log("orchestrator", "Running AnomalyDetector")
                ad_result = self.agents["anomaly_detector"].detect(metrics)
                results["anomalies"] = ad_result.get("anomalies", [])
                self._consume(ad_result.get("tokens", 5000))
                self.state.anomalies_detected = len(results["anomalies"])
            
            # Stage 3: Alert Management
            if "alert_manager" in self.agents:
                self.state.add_log("orchestrator", "Running AlertManager")
                am_result = self.agents["alert_manager"].evaluate(metrics, results["anomalies"])
                results["alerts"] = am_result.get("alerts", [])
                self._consume(am_result.get("tokens", 4000))
                self.state.alerts_fired = sum(1 for a in results["alerts"] if a.get("state") == "firing")
            
            # Stage 4: Log Analysis
            if "log_analyzer" in self.agents and logs:
                self.state.add_log("orchestrator", "Running LogAnalyzer")
                la_result = self.agents["log_analyzer"].analyze(logs)
                results["log_insights"] = la_result.get("insights", [])
                self._consume(la_result.get("tokens", 6000))
                self.state.logs_processed = len(logs)
            
            # Stage 5: Trace Correlation
            if "trace_correlator" in self.agents and traces:
                self.state.add_log("orchestrator", "Running TraceCorrelator")
                tc_result = self.agents["trace_correlator"].correlate(traces)
                results["trace_insights"] = tc_result.get("insights", [])
                self._consume(tc_result.get("tokens", 5000))
                self.state.traces_correlated = len(traces)
            
            # Stage 6: Capacity Planning
            if "capacity_planner" in self.agents:
                self.state.add_log("orchestrator", "Running CapacityPlanner")
                cp_result = self.agents["capacity_planner"].forecast(metrics)
                results["capacity"] = cp_result.get("forecasts", [])
                self._consume(cp_result.get("tokens", 4000))
            
            self.state.status = "completed"
            self.state.agents_used = list(self.agents.keys())
            self.state.token_consumed = self._token_counter
            
        except Exception as e:
            self.state.status = "failed"
            self.state.add_log("orchestrator", f"Pipeline failed: {e}", "error")
            logger.error(f"Pipeline failed: {e}")
            raise
        
        results["state"] = {
            "status": self.state.status,
            "elapsed": self.state.elapsed(),
            "metrics_collected": self.state.metrics_collected,
            "anomalies_detected": self.state.anomalies_detected,
            "alerts_fired": self.state.alerts_fired,
            "tokens": self._token_counter,
        }
        return results
    
    def get_health(self) -> Dict:
        """Get current pipeline health status."""
        return {
            "status": self.state.status,
            "agents": list(self.agents.keys()),
            "tokens": self._token_counter,
            "elapsed": self.state.elapsed(),
            "logs": self.state.agent_logs[-5:],
        }
    
    def _consume(self, tokens: int):
        self._token_counter += tokens
