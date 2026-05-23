"""Data models for ObservabilityAgent."""
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"

class AlertState(Enum):
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    SILENCED = "silenced"

class AnomalyType(Enum):
    SPIKE = "spike"
    DROP = "drop"
    TREND = "trend"
    SEASONAL = "seasonal"
    LEVEL_SHIFT = "level_shift"
    VOLATILITY = "volatility"

@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    source: str = ""
    metric_type: MetricType = MetricType.GAUGE

@dataclass
class MetricSeries:
    name: str
    labels: Dict[str, str] = field(default_factory=dict)
    points: List[MetricPoint] = field(default_factory=list)
    
    def add(self, value: float, timestamp: Optional[float] = None):
        self.points.append(MetricPoint(name=self.name, value=value, timestamp=timestamp or time.time(), labels=self.labels))
    
    def values(self) -> List[float]:
        return [p.value for p in self.points]
    
    def latest(self) -> Optional[float]:
        return self.points[-1].value if self.points else None

@dataclass
class Anomaly:
    anomaly_type: AnomalyType
    metric_name: str
    value: float
    expected: float
    deviation: float
    confidence: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    description: str = ""

@dataclass
class AlertRule:
    rule_id: str
    name: str
    metric: str
    condition: str  # "gt", "lt", "eq", "change_pct"
    threshold: float
    severity: Severity
    duration: int = 0  # seconds to wait before firing
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

@dataclass
class Alert:
    rule: AlertRule
    state: AlertState
    value: float
    fired_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule.rule_id,
            "name": self.rule.name,
            "state": self.state.value,
            "severity": self.rule.severity.value,
            "value": self.value,
            "threshold": self.rule.threshold,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
        }

@dataclass
class LogEntry:
    timestamp: float
    level: str
    message: str
    source: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    operation: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "ok"
    labels: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

@dataclass
class ServiceHealth:
    service_name: str
    status: str = "unknown"
    uptime_pct: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    error_rate: float = 0.0
    request_rate: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_alerts: int = 0
    last_check: float = field(default_factory=time.time)

@dataclass
class CapacityForecast:
    resource: str
    current_usage: float
    capacity: float
    utilization_pct: float
    predicted_usage_7d: float
    predicted_usage_30d: float
    days_until_exhausted: Optional[int] = None
    recommendation: str = ""

@dataclass
class PipelineState:
    status: str = "pending"
    start_time: float = field(default_factory=time.time)
    metrics_collected: int = 0
    anomalies_detected: int = 0
    alerts_fired: int = 0
    logs_processed: int = 0
    traces_correlated: int = 0
    agents_used: List[str] = field(default_factory=list)
    token_consumed: int = 0
    agent_logs: List[Dict] = field(default_factory=list)
    
    def add_log(self, agent: str, msg: str, level: str = "info"):
        self.agent_logs.append({"agent": agent, "message": msg, "level": level, "timestamp": time.time()})
    
    def elapsed(self) -> float:
        return time.time() - self.start_time
