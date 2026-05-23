"""Advanced alert rule engine with multi-condition support."""
import re
import time
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Operator(Enum):
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="
    CONTAINS = "contains"
    REGEX = "regex"


class Aggregation(Enum):
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    P95 = "p95"
    P99 = "p99"
    STDDEV = "stddev"


class LogicalOp(Enum):
    AND = "and"
    OR = "or"


@dataclass
class Condition:
    """Single condition for alert rule evaluation."""
    metric_name: str
    operator: Operator
    threshold: float
    aggregation: Aggregation = Aggregation.AVG
    window_seconds: int = 300
    label_filters: Dict[str, str] = field(default_factory=dict)
    
    def evaluate(self, values: List[float]) -> bool:
        """Evaluate condition against a list of values."""
        if not values:
            return False
        aggregated = self._aggregate(values)
        return self._compare(aggregated)
    
    def _aggregate(self, values: List[float]) -> float:
        if self.aggregation == Aggregation.AVG:
            return sum(values) / len(values)
        elif self.aggregation == Aggregation.SUM:
            return sum(values)
        elif self.aggregation == Aggregation.MIN:
            return min(values)
        elif self.aggregation == Aggregation.MAX:
            return max(values)
        elif self.aggregation == Aggregation.COUNT:
            return float(len(values))
        elif self.aggregation == Aggregation.P95:
            sorted_v = sorted(values)
            idx = int(len(sorted_v) * 0.95)
            return sorted_v[min(idx, len(sorted_v) - 1)]
        elif self.aggregation == Aggregation.P99:
            sorted_v = sorted(values)
            idx = int(len(sorted_v) * 0.99)
            return sorted_v[min(idx, len(sorted_v) - 1)]
        elif self.aggregation == Aggregation.STDDEV:
            if len(values) < 2:
                return 0.0
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
            return variance ** 0.5
        return sum(values) / len(values)
    
    def _compare(self, value: float) -> bool:
        if self.operator == Operator.GT:
            return value > self.threshold
        elif self.operator == Operator.LT:
            return value < self.threshold
        elif self.operator == Operator.GTE:
            return value >= self.threshold
        elif self.operator == Operator.LTE:
            return value <= self.threshold
        elif self.operator == Operator.EQ:
            return abs(value - self.threshold) < 1e-9
        elif self.operator == Operator.NEQ:
            return abs(value - self.threshold) >= 1e-9
        return False


@dataclass
class AlertRule:
    """Multi-condition alert rule with cooldown and escalation."""
    rule_id: str
    name: str
    conditions: List[Condition]
    logical_op: LogicalOp = LogicalOp.AND
    severity: str = "warning"
    cooldown_seconds: int = 300
    escalation_rules: List[Dict[str, Any]] = field(default_factory=list)
    notification_channels: List[str] = field(default_factory=list)
    auto_resolve_seconds: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    _last_fired: float = 0
    _fire_count: int = 0
    _resolved_at: float = 0
    
    def evaluate(self, metric_data: Dict[str, List[float]]) -> bool:
        """Evaluate all conditions against metric data."""
        if not self.conditions:
            return False
        
        results = []
        for condition in self.conditions:
            values = metric_data.get(condition.metric_name, [])
            results.append(condition.evaluate(values))
        
        if self.logical_op == LogicalOp.AND:
            return all(results)
        else:
            return any(results)
    
    def can_fire(self) -> bool:
        """Check if rule can fire (cooldown check)."""
        now = time.time()
        if now - self._last_fired < self.cooldown_seconds:
            return False
        return True
    
    def fire(self) -> Dict[str, Any]:
        """Fire the alert rule and return alert info."""
        now = time.time()
        self._last_fired = now
        self._fire_count += 1
        
        alert = {
            "rule_id": self.rule_id,
            "name": self.name,
            "severity": self.severity,
            "fired_at": now,
            "fire_count": self._fire_count,
            "labels": self.labels.copy(),
            "annotations": self.annotations.copy(),
        }
        
        # Check escalation
        if self.escalation_rules:
            for esc in self.escalation_rules:
                if self._fire_count >= esc.get("threshold", 999):
                    alert["escalated"] = True
                    alert["escalation"] = esc
                    break
        
        return alert
    
    def check_auto_resolve(self) -> bool:
        """Check if alert should auto-resolve."""
        if self.auto_resolve_seconds <= 0:
            return False
        return time.time() - self._resolved_at > self.auto_resolve_seconds


class RuleEngine:
    """Engine for managing and evaluating alert rules."""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = self._default_rules()
        self._history: List[Dict] = []
        self._suppressed: set = set()
    
    def _default_rules(self) -> Dict[str, AlertRule]:
        """Load default alert rules."""
        return {
            "high_cpu": AlertRule(
                rule_id="high_cpu",
                name="High CPU Usage",
                conditions=[Condition("cpu_usage", Operator.GT, 90.0, Aggregation.AVG, 300)],
                severity="critical",
                cooldown_seconds=600,
                notification_channels=["slack", "pagerduty"],
                auto_resolve_seconds=1800,
            ),
            "memory_pressure": AlertRule(
                rule_id="memory_pressure",
                name="Memory Pressure",
                conditions=[
                    Condition("memory_usage", Operator.GT, 85.0, Aggregation.AVG, 300),
                    Condition("memory_usage", Operator.GT, 95.0, Aggregation.MAX, 60),
                ],
                logical_op=LogicalOp.OR,
                severity="warning",
                cooldown_seconds=300,
            ),
            "error_rate_spike": AlertRule(
                rule_id="error_rate_spike",
                name="Error Rate Spike",
                conditions=[Condition("error_rate", Operator.GT, 5.0, Aggregation.P95, 120)],
                severity="critical",
                cooldown_seconds=120,
                escalation_rules=[{"threshold": 3, "channel": "pagerduty", "urgency": "high"}],
            ),
            "latency_degradation": AlertRule(
                rule_id="latency_degradation",
                name="Latency Degradation",
                conditions=[
                    Condition("request_latency", Operator.GT, 2000.0, Aggregation.P95, 300),
                    Condition("request_latency", Operator.GT, 5000.0, Aggregation.P99, 60),
                ],
                logical_op=LogicalOp.OR,
                severity="warning",
                cooldown_seconds=300,
            ),
            "disk_space_low": AlertRule(
                rule_id="disk_space_low",
                name="Disk Space Low",
                conditions=[Condition("disk_usage", Operator.GT, 90.0, Aggregation.AVG, 600)],
                severity="critical",
                cooldown_seconds=3600,
                auto_resolve_seconds=7200,
            ),
            "pod_restart_loop": AlertRule(
                rule_id="pod_restart_loop",
                name="Pod Restart Loop",
                conditions=[Condition("pod_restarts", Operator.GT, 5.0, Aggregation.COUNT, 600)],
                severity="critical",
                cooldown_seconds=300,
            ),
            "ssl_expiry": AlertRule(
                rule_id="ssl_expiry",
                name="SSL Certificate Expiry",
                conditions=[Condition("ssl_days_remaining", Operator.LT, 14.0, Aggregation.MIN, 3600)],
                severity="warning",
                cooldown_seconds=86400,
            ),
        }
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add or update an alert rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Rule added/updated: {rule.rule_id}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False
    
    def suppress_rule(self, rule_id: str) -> None:
        """Temporarily suppress a rule."""
        self._suppressed.add(rule_id)
    
    def unsuppress_rule(self, rule_id: str) -> None:
        """Remove suppression from a rule."""
        self._suppressed.discard(rule_id)
    
    def evaluate_all(self, metric_data: Dict[str, List[float]]) -> List[Dict]:
        """Evaluate all rules against metric data."""
        alerts = []
        for rule_id, rule in self.rules.items():
            if rule_id in self._suppressed:
                continue
            if rule.evaluate(metric_data) and rule.can_fire():
                alert = rule.fire()
                alerts.append(alert)
                self._history.append(alert)
        return alerts
    
    def get_active_alerts(self) -> List[Dict]:
        """Get recently fired alerts."""
        cutoff = time.time() - 3600
        return [a for a in self._history if a.get("fired_at", 0) > cutoff]
    
    def get_rule_stats(self) -> Dict[str, Any]:
        """Get statistics about rule evaluations."""
        stats = {}
        for rule_id, rule in self.rules.items():
            stats[rule_id] = {
                "name": rule.name,
                "fire_count": rule._fire_count,
                "last_fired": rule._last_fired,
                "suppressed": rule_id in self._suppressed,
                "condition_count": len(rule.conditions),
            }
        return stats
    
    def export_rules(self) -> List[Dict]:
        """Export all rules as serializable dicts."""
        exported = []
        for rule in self.rules.values():
            exported.append({
                "rule_id": rule.rule_id,
                "name": rule.name,
                "severity": rule.severity,
                "cooldown": rule.cooldown_seconds,
                "conditions": len(rule.conditions),
                "channels": rule.notification_channels,
            })
        return exported
