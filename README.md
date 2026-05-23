# ObservabilityAgent

Multi-agent observability pipeline for metrics collection, anomaly detection, alert management, log analysis, distributed trace correlation, and capacity planning.

## Architecture

6 specialized agents orchestrated through a pipeline:

1. **MetricCollectorAgent** — ingest, normalize, and aggregate metrics
2. **AnomalyDetectorAgent** — detect statistical anomalies (z-score, trend, seasonal)
3. **AlertManagerAgent** — evaluate alert rules and manage alert lifecycle
4. **LogAnalyzerAgent** — parse logs, detect patterns, extract insights
5. **TraceCorrelatorAgent** — correlate distributed traces, find critical paths
6. **CapacityPlannerAgent** — forecast resource usage and capacity planning

## Additional Components

- **RuleEngine** — multi-condition alert rules with cooldown, escalation, suppression
- **MetricsProcessor** — real-time dashboard data with widget system
- **TopologyMapper** — service dependency mapping from trace data
- **IncidentManager** — incident lifecycle management with automated escalation
- **TimeSeriesStore** — efficient time-series storage with aggregation and downsampling
- **ObservabilityDatabase** — in-memory database with indexing and query capabilities
- **PrometheusConnector** — PromQL query builder and Prometheus API integration
- **DatadogConnector** — Datadog metrics, APM, and dashboard integration

## Quick Start

```python
from src.core.orchestrator import Orchestrator
from src.agents import *
from src.core.models import MetricPoint

orch = Orchestrator()
orch.register_agent("metric_collector", MetricCollectorAgent())
orch.register_agent("anomaly_detector", AnomalyDetectorAgent())
# ... register all agents

metrics = [MetricPoint(name="cpu_usage", value=75.0, timestamp=time.time())]
results = orch.run_pipeline(metrics)
```

## Dashboard API

```python
from src.web.app import DashboardAPI

api = DashboardAPI(orchestrator=orch, metrics_processor=processor)
health = api.handle_request("/api/health")
dashboard = api.handle_request("/api/dashboard")
```

## Tests

```bash
python -m pytest tests/ -v
```

## Project Stats

- ~4,400 lines of Python
- 111 unit and integration tests
- 6 specialized AI agents
- Real-time dashboard with 10 default widgets
- Multi-condition alert rules with escalation
- Service topology mapping from traces
