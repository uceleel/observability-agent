"""CLI interface for ObservabilityAgent."""
import sys
import json
import time
import argparse
import logging
import random

logger = logging.getLogger(__name__)

def setup_logging(verbose=False):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

def cmd_run(args):
    """Run observability pipeline with simulated or real data."""
    from src.core.config import Config
    from src.core.orchestrator import Orchestrator
    from src.core.models import MetricPoint, LogEntry, MetricType, Severity
    from src.agents import (
        MetricCollectorAgent, AnomalyDetectorAgent, AlertManagerAgent,
        LogAnalyzerAgent, TraceCorrelatorAgent, CapacityPlannerAgent,
    )
    from src.storage.database import Database
    
    config = Config(args.config)
    orch = Orchestrator(config)
    db = Database(config.storage.db_path)
    
    # Register all agents
    agents = {
        "metric_collector": MetricCollectorAgent(config),
        "anomaly_detector": AnomalyDetectorAgent(config),
        "alert_manager": AlertManagerAgent(config),
        "log_analyzer": LogAnalyzerAgent(config),
        "trace_correlator": TraceCorrelatorAgent(config),
        "capacity_planner": CapacityPlannerAgent(config),
    }
    
    for name, agent in agents.items():
        orch.register_agent(name, agent)
    
    # Add default alert rules
    agents["alert_manager"].create_default_rules()
    
    # Generate simulated metrics
    metrics = []
    now = time.time()
    for i in range(200):
        t = now - (200 - i) * 60
        base_cpu = 50 + 10 * (i / 200)  # Trending up
        metrics.append(MetricPoint(name="cpu_usage", value=base_cpu + random.gauss(0, 5), timestamp=t))
        metrics.append(MetricPoint(name="memory_usage", value=60 + random.gauss(0, 3), timestamp=t))
        metrics.append(MetricPoint(name="error_rate", value=max(0, 2 + random.gauss(0, 1)), timestamp=t))
        metrics.append(MetricPoint(name="latency_p99", value=200 + random.gauss(0, 50), timestamp=t))
        metrics.append(MetricPoint(name="disk_usage", value=70 + 0.05 * i + random.gauss(0, 1), timestamp=t))
    
    # Add spike
    metrics.append(MetricPoint(name="cpu_usage", value=98.5, timestamp=now))
    metrics.append(MetricPoint(name="error_rate", value=15.0, timestamp=now))
    
    # Generate logs
    logs = [
        LogEntry(timestamp=now-60, level="ERROR", message="Connection refused to database:3306", source="api-server"),
        LogEntry(timestamp=now-50, level="ERROR", message="Timeout waiting for response from payment-service", source="order-service"),
        LogEntry(timestamp=now-40, level="WARN", message="High memory usage detected: 85%", source="monitor"),
        LogEntry(timestamp=now-30, level="ERROR", message="OutOfMemory: Java heap space", source="analytics-service"),
        LogEntry(timestamp=now-20, level="INFO", message="Request processed successfully", source="api-server"),
        LogEntry(timestamp=now-10, level="ERROR", message="Authentication failed for user admin", source="auth-service"),
    ]
    
    print("\nRunning Observability Pipeline...")
    print("=" * 60)
    
    start = time.time()
    results = orch.run_pipeline(metrics=metrics, logs=logs)
    duration = time.time() - start
    
    state = results["state"]
    print(f"\nPipeline: {state['status']} in {duration:.1f}s")
    print(f"Metrics: {state['metrics_collected']} collected")
    print(f"Anomalies: {state['anomalies_detected']} detected")
    print(f"Alerts: {state['alerts_fired']} fired")
    print(f"Logs: {state.get('logs_processed', 0)} processed")
    print(f"Tokens: {state['tokens']:,}")
    
    if results["anomalies"]:
        print(f"\nANOMALIES ({len(results['anomalies'])}):")
        for a in results["anomalies"][:5]:
            print(f"  [{a.get('anomaly_type', '?')}] {a.get('metric_name', '?')}: {a.get('description', '')}")
    
    if results["alerts"]:
        print(f"\nALERTS ({len(results['alerts'])}):")
        for a in results["alerts"][:5]:
            print(f"  [{a.get('severity', '?')}] {a.get('name', '?')}: state={a.get('state')}, value={a.get('value', 0):.1f}")
    
    if results["log_insights"]:
        print(f"\nLOG INSIGHTS ({len(results['log_insights'])}):")
        for i in results["log_insights"][:3]:
            print(f"  [{i.get('severity', '?')}] {i.get('message', '')}")
    
    # Save to DB
    db.save_pipeline_run(state)
    print(f"\nSaved pipeline run to database")
    db.close()

def cmd_alerts(args):
    """Show recent alerts."""
    from src.core.config import Config
    from src.storage.database import Database
    
    config = Config(args.config)
    db = Database(config.storage.db_path)
    alerts = db.get_recent_alerts(args.limit)
    
    if not alerts:
        print("No alerts found.")
        return
    
    print(f"\nRecent Alerts (last {args.limit}):")
    for a in alerts:
        print(f"  [{a['severity']}] {a['name']} — {a['state']} (value={a.get('value', 0):.1f})")
    db.close()

def main():
    parser = argparse.ArgumentParser(description="ObservabilityAgent")
    parser.add_argument("--config", "-c", default="config.json")
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="command")
    
    p_run = sub.add_parser("run", help="Run pipeline")
    p_run.set_defaults(func=cmd_run)
    
    p_alerts = sub.add_parser("alerts", help="Show alerts")
    p_alerts.add_argument("--limit", "-l", type=int, default=20)
    p_alerts.set_defaults(func=cmd_alerts)
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
