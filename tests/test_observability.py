"""Comprehensive tests for observability agent."""
import pytest
import time
import math
from src.core.config import Config
from src.core.models import (
    MetricPoint, MetricSeries, Anomaly, Alert, AlertRule,
    LogEntry, TraceSpan, ServiceHealth, CapacityForecast,
    PipelineState, Severity, AlertState, MetricType, AnomalyType,
)
from src.core.orchestrator import Orchestrator
from src.agents.metric_collector import MetricCollectorAgent
from src.agents.anomaly_detector import AnomalyDetectorAgent
from src.agents.alert_manager import AlertManagerAgent
from src.agents.log_analyzer import LogAnalyzerAgent
from src.agents.trace_correlator import TraceCorrelatorAgent
from src.agents.capacity_planner import CapacityPlannerAgent
from src.utils.alert_rules import (
    RuleEngine, AlertRule as RuleAlertRule, Condition, Operator,
    Aggregation, LogicalOp,
)
from src.utils.dashboard_metrics import MetricsProcessor, TopologyMapper, MetricWidget, TimeWindow
from src.utils.statistics import Statistics
from src.utils.formatters import format_metric, format_duration, format_bytes, format_number


# ═══ Config Tests ═══

class TestConfig:
    def test_default_config(self, config):
        assert config is not None

    def test_config_attributes(self, config):
        assert hasattr(config, "__class__")


# ═══ Model Tests ═══

class TestMetricPoint:
    def test_create_metric_point(self):
        mp = MetricPoint(name="cpu", value=75.0, timestamp=time.time())
        assert mp.name == "cpu"
        assert mp.value == 75.0

    def test_metric_point_with_labels(self):
        mp = MetricPoint(name="cpu", value=50.0, timestamp=time.time(), labels={"host": "web-01"})
        assert mp.labels["host"] == "web-01"

    def test_metric_point_value_types(self):
        mp = MetricPoint(name="count", value=42, timestamp=time.time())
        assert mp.value == 42


class TestLogEntry:
    def test_create_log_entry(self):
        log = LogEntry(timestamp=time.time(), level="ERROR", message="test error", source="api")
        assert log.level == "ERROR"
        assert "error" in log.message.lower()

    def test_log_entry_levels(self):
        for level in ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]:
            log = LogEntry(timestamp=time.time(), level=level, message="test", source="svc")
            assert log.level == level


class TestTraceSpan:
    def test_create_trace_span(self):
        span = TraceSpan(trace_id="t1", span_id="s1", parent_id=None, operation="handle", start_time=time.time())
        assert span.trace_id == "t1"
        assert span.operation == "handle"

    def test_trace_span_with_parent(self):
        span = TraceSpan(trace_id="t1", span_id="s2", parent_id="s1", operation="query", start_time=time.time())
        assert span.parent_id == "s1"

    def test_trace_span_duration(self):
        now = time.time()
        span = TraceSpan(trace_id="t1", span_id="s1", parent_id=None, operation="test", start_time=now, end_time=now+0.5)
        assert span.duration_ms == 500.0


class TestAnomaly:
    def test_anomaly_creation(self):
        a = Anomaly(anomaly_type=AnomalyType.SPIKE, metric_name="cpu", value=95.0, expected=50.0, deviation=45.0, confidence=0.95)
        assert a.metric_name == "cpu"
        assert a.confidence == 0.95

    def test_anomaly_types(self):
        for atype in [AnomalyType.SPIKE, AnomalyType.DROP, AnomalyType.TREND]:
            a = Anomaly(anomaly_type=atype, metric_name="test", value=1.0, expected=0.5, deviation=0.5, confidence=0.9)
            assert a.anomaly_type == atype


# ═══ Severity Tests ═══

class TestSeverity:
    def test_severity_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"
        assert Severity.DEBUG.value == "debug"


# ═══ Orchestrator Tests ═══

class TestOrchestrator:
    def test_create_orchestrator(self, orchestrator):
        assert orchestrator is not None

    def test_register_agents(self, orchestrator):
        assert "metric_collector" in orchestrator.agents
        assert "anomaly_detector" in orchestrator.agents
        assert "alert_manager" in orchestrator.agents
        assert "log_analyzer" in orchestrator.agents
        assert "trace_correlator" in orchestrator.agents
        assert "capacity_planner" in orchestrator.agents

    def test_agent_count(self, orchestrator):
        assert len(orchestrator.agents) == 6

    def test_run_pipeline_with_metrics(self, orchestrator, sample_metrics):
        results = orchestrator.run_pipeline(sample_metrics)
        assert results is not None
        assert "metrics" in results

    def test_pipeline_state_after_run(self, orchestrator, sample_metrics):
        orchestrator.run_pipeline(sample_metrics)
        assert orchestrator.state.status in ("running", "completed")

    def test_pipeline_with_logs(self, orchestrator, sample_metrics, sample_logs):
        results = orchestrator.run_pipeline(sample_metrics, logs=sample_logs)
        assert results is not None

    def test_pipeline_with_traces(self, orchestrator, sample_metrics, sample_traces):
        results = orchestrator.run_pipeline(sample_metrics, traces=sample_traces)
        assert results is not None

    def test_pipeline_token_counter(self, orchestrator, sample_metrics):
        orchestrator.run_pipeline(sample_metrics)
        assert orchestrator._token_counter >= 0


# ═══ MetricCollectorAgent Tests ═══

class TestMetricCollectorAgent:
    def test_create_collector(self):
        mc = MetricCollectorAgent()
        assert mc is not None

    def test_collect_metrics(self, sample_metrics):
        mc = MetricCollectorAgent()
        result = mc.collect(sample_metrics)
        assert result is not None

    def test_collect_returns_dict(self, sample_metrics):
        mc = MetricCollectorAgent()
        result = mc.collect(sample_metrics)
        assert isinstance(result, dict)

    def test_collect_empty_metrics(self):
        mc = MetricCollectorAgent()
        result = mc.collect([])
        assert result is not None


# ═══ AnomalyDetectorAgent Tests ═══

class TestAnomalyDetectorAgent:
    def test_create_detector(self):
        ad = AnomalyDetectorAgent()
        assert ad is not None

    def test_detect_anomalies(self, sample_metrics):
        ad = AnomalyDetectorAgent()
        result = ad.detect(sample_metrics)
        assert result is not None

    def test_detect_returns_dict(self, sample_metrics):
        ad = AnomalyDetectorAgent()
        result = ad.detect(sample_metrics)
        assert isinstance(result, dict)


# ═══ AlertManagerAgent Tests ═══

class TestAlertManagerAgent:
    def test_create_alert_manager(self):
        am = AlertManagerAgent()
        assert am is not None

    def test_evaluate_alerts(self, sample_metrics):
        am = AlertManagerAgent()
        result = am.evaluate(sample_metrics)
        assert result is not None


# ═══ LogAnalyzerAgent Tests ═══

class TestLogAnalyzerAgent:
    def test_create_log_analyzer(self):
        la = LogAnalyzerAgent()
        assert la is not None

    def test_analyze_logs(self, sample_logs):
        la = LogAnalyzerAgent()
        result = la.analyze(sample_logs)
        assert result is not None


# ═══ TraceCorrelatorAgent Tests ═══

class TestTraceCorrelatorAgent:
    def test_create_correlator(self):
        tc = TraceCorrelatorAgent()
        assert tc is not None

    def test_correlate_traces(self, sample_traces):
        tc = TraceCorrelatorAgent()
        result = tc.correlate(sample_traces)
        assert result is not None


# ═══ CapacityPlannerAgent Tests ═══

class TestCapacityPlannerAgent:
    def test_create_planner(self):
        cp = CapacityPlannerAgent()
        assert cp is not None

    def test_forecast(self, sample_metrics):
        cp = CapacityPlannerAgent()
        result = cp.forecast(sample_metrics)
        assert result is not None


# ═══ RuleEngine Tests ═══

class TestCondition:
    def test_gt_operator(self):
        c = Condition("cpu", Operator.GT, 80.0)
        assert c.evaluate([90.0, 85.0, 95.0]) is True

    def test_lt_operator(self):
        c = Condition("cpu", Operator.LT, 50.0)
        assert c.evaluate([30.0, 40.0]) is True
        assert c.evaluate([60.0, 70.0]) is False

    def test_gte_operator(self):
        c = Condition("cpu", Operator.GTE, 80.0)
        assert c.evaluate([80.0]) is True
        assert c.evaluate([79.9]) is False

    def test_lte_operator(self):
        c = Condition("cpu", Operator.LTE, 80.0)
        assert c.evaluate([80.0]) is True
        assert c.evaluate([80.1]) is False

    def test_eq_operator(self):
        c = Condition("cpu", Operator.EQ, 50.0)
        assert c.evaluate([50.0]) is True
        assert c.evaluate([50.1]) is False

    def test_neq_operator(self):
        c = Condition("cpu", Operator.NEQ, 50.0)
        assert c.evaluate([50.0]) is False
        assert c.evaluate([51.0]) is True

    def test_empty_values(self):
        c = Condition("cpu", Operator.GT, 80.0)
        assert c.evaluate([]) is False

    def test_aggregation_avg(self):
        c = Condition("cpu", Operator.GT, 50.0, Aggregation.AVG)
        assert c.evaluate([40.0, 60.0, 80.0]) is True

    def test_aggregation_sum(self):
        c = Condition("cpu", Operator.GT, 100.0, Aggregation.SUM)
        assert c.evaluate([40.0, 30.0, 50.0]) is True

    def test_aggregation_min(self):
        c = Condition("cpu", Operator.LT, 10.0, Aggregation.MIN)
        assert c.evaluate([5.0, 50.0, 90.0]) is True

    def test_aggregation_max(self):
        c = Condition("cpu", Operator.GT, 90.0, Aggregation.MAX)
        assert c.evaluate([50.0, 80.0, 95.0]) is True

    def test_aggregation_count(self):
        c = Condition("events", Operator.GT, 3.0, Aggregation.COUNT)
        assert c.evaluate([1, 2, 3, 4, 5]) is True

    def test_aggregation_p95(self):
        values = list(range(1, 101))
        c = Condition("latency", Operator.GT, 94.0, Aggregation.P95)
        assert c.evaluate(values) is True

    def test_aggregation_p99(self):
        values = list(range(1, 101))
        c = Condition("latency", Operator.GT, 98.0, Aggregation.P99)
        assert c.evaluate(values) is True

    def test_aggregation_stddev(self):
        c = Condition("variance", Operator.GT, 10.0, Aggregation.STDDEV)
        assert c.evaluate([10, 20, 30, 40, 50]) is True

    def test_stddev_single_value(self):
        c = Condition("variance", Operator.EQ, 0.0, Aggregation.STDDEV)
        assert c.evaluate([50.0]) is True


class TestRuleEngine:
    def test_create_engine(self, rule_engine):
        assert rule_engine is not None

    def test_default_rules_loaded(self, rule_engine):
        assert len(rule_engine.rules) >= 5

    def test_high_cpu_rule_exists(self, rule_engine):
        assert "high_cpu" in rule_engine.rules

    def test_memory_pressure_rule(self, rule_engine):
        assert "memory_pressure" in rule_engine.rules

    def test_error_rate_rule(self, rule_engine):
        assert "error_rate_spike" in rule_engine.rules

    def test_latency_rule(self, rule_engine):
        assert "latency_degradation" in rule_engine.rules

    def test_disk_space_rule(self, rule_engine):
        assert "disk_space_low" in rule_engine.rules

    def test_evaluate_all_triggers_cpu(self, rule_engine):
        data = {"cpu_usage": [95.0, 92.0, 98.0]}
        alerts = rule_engine.evaluate_all(data)
        assert any(a["rule_id"] == "high_cpu" for a in alerts)

    def test_evaluate_no_trigger(self, rule_engine):
        data = {"cpu_usage": [30.0, 40.0, 50.0]}
        alerts = rule_engine.evaluate_all(data)
        assert len(alerts) == 0

    def test_add_custom_rule(self, rule_engine):
        rule = RuleAlertRule(
            rule_id="custom_test",
            name="Custom Test",
            conditions=[Condition("test_metric", Operator.GT, 100.0)],
        )
        rule_engine.add_rule(rule)
        assert "custom_test" in rule_engine.rules

    def test_remove_rule(self, rule_engine):
        assert rule_engine.remove_rule("high_cpu") is True
        assert "high_cpu" not in rule_engine.rules

    def test_remove_nonexistent_rule(self, rule_engine):
        assert rule_engine.remove_rule("nonexistent") is False

    def test_suppress_rule(self, rule_engine):
        rule_engine.suppress_rule("high_cpu")
        assert "high_cpu" in rule_engine._suppressed

    def test_suppressed_rule_skipped(self, rule_engine):
        rule_engine.suppress_rule("high_cpu")
        data = {"cpu_usage": [99.0]}
        alerts = rule_engine.evaluate_all(data)
        assert not any(a["rule_id"] == "high_cpu" for a in alerts)

    def test_unsuppress_rule(self, rule_engine):
        rule_engine.suppress_rule("high_cpu")
        rule_engine.unsuppress_rule("high_cpu")
        assert "high_cpu" not in rule_engine._suppressed

    def test_get_active_alerts(self, rule_engine):
        active = rule_engine.get_active_alerts()
        assert isinstance(active, list)

    def test_get_rule_stats(self, rule_engine):
        stats = rule_engine.get_rule_stats()
        assert "high_cpu" in stats
        assert "fire_count" in stats["high_cpu"]

    def test_export_rules(self, rule_engine):
        exported = rule_engine.export_rules()
        assert len(exported) >= 5
        assert all("rule_id" in r for r in exported)

    def test_cooldown_prevents_refire(self, rule_engine):
        data = {"cpu_usage": [99.0]}
        rule_engine.evaluate_all(data)
        alerts2 = rule_engine.evaluate_all(data)
        assert len(alerts2) == 0

    def test_and_logic(self):
        rule = RuleAlertRule(
            rule_id="test_and",
            name="Test AND",
            conditions=[
                Condition("a", Operator.GT, 50.0),
                Condition("b", Operator.GT, 50.0),
            ],
            logical_op=LogicalOp.AND,
            cooldown_seconds=0,
        )
        engine = RuleEngine()
        engine.rules = {"test_and": rule}
        alerts = engine.evaluate_all({"a": [60.0], "b": [60.0]})
        assert len(alerts) == 1

    def test_or_logic(self):
        rule = RuleAlertRule(
            rule_id="test_or",
            name="Test OR",
            conditions=[
                Condition("a", Operator.GT, 50.0),
                Condition("b", Operator.GT, 50.0),
            ],
            logical_op=LogicalOp.OR,
            cooldown_seconds=0,
        )
        engine = RuleEngine()
        engine.rules = {"test_or": rule}
        alerts = engine.evaluate_all({"a": [60.0], "b": [30.0]})
        assert len(alerts) == 1


# ═══ MetricsProcessor Tests ═══

class TestMetricsProcessor:
    def test_create_processor(self, metrics_processor):
        assert metrics_processor is not None

    def test_ingest_metric(self, metrics_processor):
        metrics_processor.ingest("cpu", 75.0)
        assert "cpu" in metrics_processor.get_metric_names()

    def test_ingest_batch(self, metrics_processor):
        batch = [
            {"name": "cpu", "value": 75.0},
            {"name": "mem", "value": 60.0},
            {"name": "cpu", "value": 80.0},
        ]
        count = metrics_processor.ingest_batch(batch)
        assert count == 3

    def test_query_metric(self, metrics_processor):
        metrics_processor.ingest("cpu", 70.0)
        metrics_processor.ingest("cpu", 80.0)
        result = metrics_processor.query("cpu", 60, "avg")
        assert result is not None
        assert result == 75.0

    def test_query_nonexistent(self, metrics_processor):
        result = metrics_processor.query("nonexistent", 60, "avg")
        assert result is None

    def test_query_sum(self, metrics_processor):
        metrics_processor.ingest("requests", 100)
        metrics_processor.ingest("requests", 200)
        result = metrics_processor.query("requests", 60, "sum")
        assert result == 300

    def test_query_min_max(self, metrics_processor):
        for v in [10, 20, 30, 40, 50]:
            metrics_processor.ingest("temp", v)
        assert metrics_processor.query("temp", 60, "min") == 10
        assert metrics_processor.query("temp", 60, "max") == 50

    def test_default_widgets(self, metrics_processor):
        assert len(metrics_processor._widgets) >= 8

    def test_get_widget_data(self, metrics_processor):
        metrics_processor.ingest("cpu_usage", 75.0)
        data = metrics_processor.get_widget_data("cpu_usage")
        assert "widget" in data
        assert "value" in data
        assert "status" in data

    def test_get_widget_nonexistent(self, metrics_processor):
        data = metrics_processor.get_widget_data("nonexistent")
        assert "error" in data

    def test_get_dashboard(self, metrics_processor):
        dashboard = metrics_processor.get_dashboard()
        assert "widgets" in dashboard
        assert "generated_at" in dashboard
        assert "metric_count" in dashboard

    def test_add_custom_widget(self, metrics_processor):
        w = MetricWidget("custom", "Custom Widget", "custom_metric", "stat")
        metrics_processor.add_widget(w)
        assert "custom" in metrics_processor._widgets

    def test_remove_widget(self, metrics_processor):
        assert metrics_processor.remove_widget("cpu_usage") is True
        assert "cpu_usage" not in metrics_processor._widgets

    def test_metric_stats(self, metrics_processor):
        metrics_processor.ingest("cpu", 50.0)
        metrics_processor.ingest("cpu", 70.0)
        stats = metrics_processor.get_metric_stats()
        assert "cpu" in stats
        assert stats["cpu"]["count"] == 2
        assert stats["cpu"]["min"] == 50.0

    def test_clear_buffer(self, metrics_processor):
        metrics_processor.ingest("cpu", 50.0)
        metrics_processor.clear_buffer("cpu")
        assert metrics_processor.query("cpu", 60, "avg") is None

    def test_clear_all_buffer(self, metrics_processor):
        metrics_processor.ingest("a", 1)
        metrics_processor.ingest("b", 2)
        metrics_processor.clear_buffer()
        assert metrics_processor.get_metric_names() == []


# ═══ TopologyMapper Tests ═══

class TestTopologyMapper:
    def test_create_mapper(self, topology_mapper):
        assert topology_mapper is not None

    def test_add_trace(self, topology_mapper):
        spans = [
            {"span_id": "s1", "service": "gateway", "duration_ms": 100},
            {"span_id": "s2", "parent_id": "s1", "service": "api", "duration_ms": 80},
        ]
        topology_mapper.add_trace(spans)
        topo = topology_mapper.get_topology()
        assert topo["node_count"] == 2

    def test_topology_edges(self, topology_mapper):
        spans = [
            {"span_id": "s1", "service": "web", "duration_ms": 100},
            {"span_id": "s2", "parent_id": "s1", "service": "api", "duration_ms": 50},
            {"span_id": "s3", "parent_id": "s2", "service": "db", "duration_ms": 30},
        ]
        topology_mapper.add_trace(spans)
        topo = topology_mapper.get_topology()
        assert topo["edge_count"] == 2

    def test_topology_errors(self, topology_mapper):
        spans = [
            {"span_id": "s1", "service": "api", "duration_ms": 100, "error": True},
            {"span_id": "s2", "parent_id": "s1", "service": "db", "duration_ms": 50, "error": True},
        ]
        topology_mapper.add_trace(spans)
        topo = topology_mapper.get_topology()
        assert any(e["error_count"] > 0 for e in topo["edges"])

    def test_reset(self, topology_mapper):
        topology_mapper.add_trace([{"span_id": "s1", "service": "a", "duration_ms": 10}])
        topology_mapper.reset()
        topo = topology_mapper.get_topology()
        assert topo["node_count"] == 0

    def test_empty_topology(self, topology_mapper):
        topo = topology_mapper.get_topology()
        assert topo["node_count"] == 0
        assert topo["edge_count"] == 0

    def test_critical_path_empty(self, topology_mapper):
        path = topology_mapper.get_critical_path()
        assert path == []


# ═══ Statistics Tests ═══

class TestStatistics:
    def test_mean(self):
        assert Statistics.mean([1, 2, 3, 4, 5]) == 3.0

    def test_mean_empty(self):
        assert Statistics.mean([]) == 0.0

    def test_median(self):
        assert Statistics.median([1, 2, 3, 4, 5]) == 3

    def test_stddev(self):
        result = Statistics.stddev([2, 4, 4, 4, 5, 5, 7, 9])
        assert result > 0

    def test_percentile(self):
        values = list(range(1, 101))
        p50 = Statistics.percentile(values, 50)
        assert 50 <= p50 <= 51  # Implementation may vary

    def test_percentile_p95(self):
        values = list(range(1, 101))
        p95 = Statistics.percentile(values, 95)
        assert 94 <= p95 <= 96

    def test_z_score(self):
        z = Statistics.z_score(100, 50, 10)
        assert z == 5.0


# ═══ Formatters Tests ═══

class TestFormatters:
    def test_format_duration(self):
        assert format_duration(60) is not None

    def test_format_bytes(self):
        assert format_bytes(1024) is not None

    def test_format_number(self):
        assert format_number(1000000) is not None

    def test_format_metric(self):
        result = format_metric("cpu_usage", 75.5, {"host": "web-01"})
        assert result is not None


# ═══ Integration Tests ═══

class TestIntegration:
    def test_full_pipeline_flow(self, orchestrator, sample_metrics, sample_logs, sample_traces):
        results = orchestrator.run_pipeline(sample_metrics, logs=sample_logs, traces=sample_traces)
        assert results is not None
        assert "metrics" in results

    def test_rule_engine_with_metrics_processor(self, rule_engine, metrics_processor):
        metrics_processor.ingest("cpu_usage", 95.0)
        metrics_processor.ingest("cpu_usage", 98.0)
        value = metrics_processor.query("cpu_usage", 300, "avg")
        assert value is not None
        assert value > 90.0

    def test_multi_metric_evaluation(self, rule_engine):
        data = {
            "cpu_usage": [85.0, 90.0],
            "memory_usage": [70.0, 75.0],
            "error_rate": [1.0, 2.0],
            "request_latency": [300.0, 500.0],
        }
        alerts = rule_engine.evaluate_all(data)
        assert isinstance(alerts, list)

    def test_dashboard_with_ingested_data(self, metrics_processor):
        for i in range(50):
            metrics_processor.ingest("cpu_usage", 50.0 + i)
            metrics_processor.ingest("memory_usage", 60.0 + i * 0.5)
        dashboard = metrics_processor.get_dashboard()
        assert dashboard["total_points"] == 100
        assert dashboard["metric_count"] == 2
