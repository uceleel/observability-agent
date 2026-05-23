"""Test fixtures for observability agent."""
import pytest
import time
from src.core.config import Config
from src.core.models import (
    MetricPoint, MetricSeries, Anomaly, Alert, AlertRule,
    LogEntry, TraceSpan, ServiceHealth, CapacityForecast,
    PipelineState, Severity, AnomalyType,
)
from src.core.orchestrator import Orchestrator
from src.agents.metric_collector import MetricCollectorAgent
from src.agents.anomaly_detector import AnomalyDetectorAgent
from src.agents.alert_manager import AlertManagerAgent
from src.agents.log_analyzer import LogAnalyzerAgent
from src.agents.trace_correlator import TraceCorrelatorAgent
from src.agents.capacity_planner import CapacityPlannerAgent
from src.utils.alert_rules import RuleEngine, AlertRule as RuleAlertRule, Condition, Operator, Aggregation, LogicalOp
from src.utils.dashboard_metrics import MetricsProcessor, TopologyMapper, MetricWidget, TimeWindow
from src.utils.statistics import Statistics
from src.utils.formatters import format_metric, format_duration, format_bytes, format_number


@pytest.fixture
def config():
    return Config()


@pytest.fixture
def orchestrator(config):
    orch = Orchestrator(config)
    orch.register_agent("metric_collector", MetricCollectorAgent())
    orch.register_agent("anomaly_detector", AnomalyDetectorAgent())
    orch.register_agent("alert_manager", AlertManagerAgent())
    orch.register_agent("log_analyzer", LogAnalyzerAgent())
    orch.register_agent("trace_correlator", TraceCorrelatorAgent())
    orch.register_agent("capacity_planner", CapacityPlannerAgent())
    return orch


@pytest.fixture
def sample_metrics():
    now = time.time()
    return [
        MetricPoint(name="cpu_usage", value=75.0, timestamp=now, labels={"host": "web-01"}),
        MetricPoint(name="cpu_usage", value=92.0, timestamp=now, labels={"host": "web-02"}),
        MetricPoint(name="memory_usage", value=68.0, timestamp=now, labels={"host": "web-01"}),
        MetricPoint(name="request_count", value=1500, timestamp=now, labels={"endpoint": "/api"}),
        MetricPoint(name="error_count", value=25, timestamp=now, labels={"endpoint": "/api"}),
        MetricPoint(name="request_latency", value=450, timestamp=now, labels={"endpoint": "/api"}),
    ]


@pytest.fixture
def sample_logs():
    now = time.time()
    return [
        LogEntry(timestamp=now, level="ERROR", message="Connection timeout to database", source="api"),
        LogEntry(timestamp=now, level="WARN", message="High latency on /api/users", source="api"),
        LogEntry(timestamp=now, level="INFO", message="Request processed successfully", source="web"),
        LogEntry(timestamp=now, level="ERROR", message="OOM killed process 1234", source="worker"),
        LogEntry(timestamp=now, level="ERROR", message="SSL certificate expires in 3 days", source="gateway"),
    ]


@pytest.fixture
def sample_traces():
    now = time.time()
    return [
        TraceSpan(trace_id="t1", span_id="s1", parent_id=None, operation="handle_request", start_time=now, end_time=now+0.5),
        TraceSpan(trace_id="t1", span_id="s2", parent_id="s1", operation="process", start_time=now+0.1, end_time=now+0.4),
        TraceSpan(trace_id="t1", span_id="s3", parent_id="s2", operation="query", start_time=now+0.15, end_time=now+0.35),
    ]


@pytest.fixture
def rule_engine():
    return RuleEngine()


@pytest.fixture
def metrics_processor():
    return MetricsProcessor()


@pytest.fixture
def topology_mapper():
    return TopologyMapper()
