"""AlertManager Agent — evaluate alert rules and manage alert lifecycle."""
import time
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from ..core.models import Alert, AlertRule, AlertState, Severity, Anomaly, MetricPoint

logger = logging.getLogger(__name__)

class AlertManagerAgent:
    """Manages alert rules, evaluation, and lifecycle.
    
    Capabilities:
    - Rule-based alert evaluation
    - Threshold, change, and anomaly-based conditions
    - Alert deduplication
    - Silence/mute management
    - Escalation policies
    - Notification routing
    """
    
    def __init__(self, config=None):
        self.config = config
        self.name = "AlertManager"
        self._token_count = 0
        self._rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._silenced: Dict[str, float] = {}  # rule_id -> until_timestamp
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self._rules[rule.rule_id] = rule
        logger.info(f"Alert rule added: {rule.name}")
    
    def evaluate(self, metrics: List[MetricPoint], anomalies: Optional[List[Anomaly]] = None) -> Dict:
        """Evaluate all rules against current metrics."""
        logger.info(f"Evaluating {len(self._rules)} rules against {len(metrics)} metrics")
        
        alerts = []
        
        # Group metrics by name for lookup
        metric_values = defaultdict(list)
        for m in metrics:
            metric_values[m.name].append(m)
        
        # Evaluate each rule
        for rule_id, rule in self._rules.items():
            if not rule.enabled:
                continue
            
            # Check silence
            if rule_id in self._silenced:
                if time.time() < self._silenced[rule_id]:
                    continue
                else:
                    del self._silenced[rule_id]
            
            # Get latest value for metric
            if rule.metric not in metric_values:
                continue
            
            latest_points = metric_values[rule.metric]
            if not latest_points:
                continue
            
            latest = latest_points[-1].value
            
            # Evaluate condition
            fired = self._evaluate_condition(latest, rule.condition, rule.threshold)
            
            if fired:
                if rule_id not in self._active_alerts:
                    alert = Alert(
                        rule=rule,
                        state=AlertState.FIRING,
                        value=latest,
                        labels=latest_points[-1].labels,
                    )
                    self._active_alerts[rule_id] = alert
                    self._alert_history.append(alert)
                    alerts.append(alert.to_dict())
                    logger.warning(f"ALERT FIRING: {rule.name} ({rule.severity.value}) — {rule.metric}={latest} {rule.condition} {rule.threshold}")
            else:
                # Check if we should resolve
                if rule_id in self._active_alerts:
                    alert = self._active_alerts.pop(rule_id)
                    alert.state = AlertState.RESOLVED
                    alert.resolved_at = time.time()
                    alerts.append(alert.to_dict())
                    logger.info(f"ALERT RESOLVED: {rule.name}")
        
        # Check anomalies for auto-alerting
        if anomalies:
            for anomaly in anomalies:
                if anomaly.confidence > 0.8:
                    auto_key = f"anomaly:{anomaly.metric_name}:{anomaly.anomaly_type.value}"
                    if auto_key not in self._active_alerts:
                        rule = AlertRule(
                            rule_id=auto_key,
                            name=f"Anomaly: {anomaly.metric_name}",
                            metric=anomaly.metric_name,
                            condition="anomaly",
                            threshold=anomaly.deviation,
                            severity=Severity.WARNING if anomaly.confidence < 0.95 else Severity.CRITICAL,
                        )
                        alert = Alert(
                            rule=rule,
                            state=AlertState.FIRING,
                            value=anomaly.value,
                            labels=anomaly.labels,
                            annotations={"description": anomaly.description, "type": anomaly.anomaly_type.value},
                        )
                        self._active_alerts[auto_key] = alert
                        alerts.append(alert.to_dict())
        
        self._token_count += 4000
        
        return {
            "alerts": alerts,
            "active_count": len(self._active_alerts),
            "rules_evaluated": len(self._rules),
            "tokens": self._token_count,
        }
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate a single condition."""
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "eq":
            return abs(value - threshold) < 0.001
        elif condition == "gte":
            return value >= threshold
        elif condition == "lte":
            return value <= threshold
        elif condition == "neq":
            return abs(value - threshold) >= 0.001
        return False
    
    def silence_rule(self, rule_id: str, duration_seconds: int):
        """Silence an alert rule for a duration."""
        self._silenced[rule_id] = time.time() + duration_seconds
        logger.info(f"Silenced rule {rule_id} for {duration_seconds}s")
    
    def get_active_alerts(self) -> List[Dict]:
        return [a.to_dict() for a in self._active_alerts.values()]
    
    def get_alert_history(self, limit: int = 100) -> List[Dict]:
        return [a.to_dict() for a in self._alert_history[-limit:]]
    
    def get_rules(self) -> List[Dict]:
        return [{"id": r.rule_id, "name": r.name, "metric": r.metric, "condition": r.condition, "threshold": r.threshold, "severity": r.severity.value, "enabled": r.enabled} for r in self._rules.values()]
    
    def create_default_rules(self) -> List[AlertRule]:
        """Create sensible default alert rules."""
        defaults = [
            AlertRule(rule_id="cpu_high", name="High CPU", metric="cpu_usage", condition="gt", threshold=90.0, severity=Severity.CRITICAL),
            AlertRule(rule_id="mem_high", name="High Memory", metric="memory_usage", condition="gt", threshold=85.0, severity=Severity.WARNING),
            AlertRule(rule_id="disk_high", name="High Disk", metric="disk_usage", condition="gt", threshold=90.0, severity=Severity.CRITICAL),
            AlertRule(rule_id="error_rate", name="High Error Rate", metric="error_rate", condition="gt", threshold=5.0, severity=Severity.CRITICAL),
            AlertRule(rule_id="latency_high", name="High Latency", metric="latency_p99", condition="gt", threshold=1000.0, severity=Severity.WARNING),
        ]
        for rule in defaults:
            self.add_rule(rule)
        return defaults
