"""Incident management system for automated incident response."""
import time
import logging
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentPriority(Enum):
    P1 = "p1"  # Critical business impact
    P2 = "p2"  # High impact
    P3 = "p3"  # Medium impact
    P4 = "p4"  # Low impact


@dataclass
class TimelineEvent:
    """Single event in incident timeline."""
    timestamp: float
    event_type: str
    message: str
    actor: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """Represents a managed incident."""
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    priority: IncidentPriority = IncidentPriority.P3
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    assignee: Optional[str] = None
    affected_services: List[str] = field(default_factory=list)
    timeline: List[TimelineEvent] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    runbook_url: Optional[str] = None
    escalation_level: int = 0
    _mttr: Optional[float] = None
    
    def add_event(self, event_type: str, message: str, actor: str = "system") -> None:
        """Add event to incident timeline."""
        self.timeline.append(TimelineEvent(
            timestamp=time.time(),
            event_type=event_type,
            message=message,
            actor=actor,
        ))
        self.updated_at = time.time()
    
    def transition(self, new_status: IncidentStatus, actor: str = "system") -> bool:
        """Transition incident to new status."""
        valid_transitions = {
            IncidentStatus.OPEN: [IncidentStatus.ACKNOWLEDGED],
            IncidentStatus.ACKNOWLEDGED: [IncidentStatus.INVESTIGATING],
            IncidentStatus.INVESTIGATING: [IncidentStatus.MITIGATING, IncidentStatus.RESOLVED],
            IncidentStatus.MITIGATING: [IncidentStatus.RESOLVED],
            IncidentStatus.RESOLVED: [IncidentStatus.CLOSED, IncidentStatus.OPEN],
            IncidentStatus.CLOSED: [],
        }
        
        allowed = valid_transitions.get(self.status, [])
        if new_status not in allowed:
            self.add_event("transition_failed", f"Cannot transition from {self.status.value} to {new_status.value}", actor)
            return False
        
        old_status = self.status
        self.status = new_status
        self.updated_at = time.time()
        
        if new_status == IncidentStatus.RESOLVED:
            self.resolved_at = time.time()
            self._mttr = self.resolved_at - self.created_at
        
        self.add_event("status_change", f"Status: {old_status.value} -> {new_status.value}", actor)
        return True
    
    @property
    def duration_seconds(self) -> float:
        """Get incident duration in seconds."""
        end = self.resolved_at or time.time()
        return end - self.created_at
    
    @property
    def mttr_minutes(self) -> Optional[float]:
        """Get mean time to resolve in minutes."""
        if self._mttr:
            return self._mttr / 60
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.incident_id,
            "title": self.title,
            "severity": self.severity.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "duration_s": self.duration_seconds,
            "mttr_min": self.mttr_minutes,
            "assignee": self.assignee,
            "services": self.affected_services,
            "events": len(self.timeline),
        }


class IncidentManager:
    """Manages incident lifecycle and response automation."""
    
    def __init__(self):
        self.incidents: Dict[str, Incident] = self._seed_incidents()
        self._escalation_policies: Dict[str, List[Dict]] = self._default_escalation()
        self._runbooks: Dict[str, str] = {}
        self._stats = {"total_created": 0, "total_resolved": 0, "total_mttr": 0}
    
    def _seed_incidents(self) -> Dict[str, Incident]:
        """Seed with example resolved incidents for demo."""
        now = time.time()
        incidents = {}
        
        inc1 = Incident("INC-001", "High CPU on prod-web-01", "CPU sustained above 95% for 10 minutes",
                        IncidentSeverity.HIGH, IncidentStatus.RESOLVED, IncidentPriority.P2,
                        created_at=now - 7200, resolved_at=now - 3600)
        inc1.affected_services = ["web", "api"]
        inc1.assignee = "oncall-sre"
        inc1.add_event("created", "Alert triggered: high_cpu", "system")
        inc1.add_event("acknowledged", "Taking a look", "oncall-sre")
        inc1.add_event("resolved", "Scaled up replicas to 5", "oncall-sre")
        incidents["INC-001"] = inc1
        
        inc2 = Incident("INC-002", "Database connection pool exhaustion", "All DB connections consumed",
                        IncidentSeverity.CRITICAL, IncidentStatus.RESOLVED, IncidentPriority.P1,
                        created_at=now - 14400, resolved_at=now - 10800)
        inc2.affected_services = ["database", "api", "worker"]
        inc2.assignee = "dba-team"
        inc2.add_event("created", "Alert: db_connections at max", "system")
        inc2.add_event("resolved", "Killed long-running queries, increased pool size", "dba-team")
        incidents["INC-002"] = inc2
        
        return incidents
    
    def _default_escalation(self) -> Dict[str, List[Dict]]:
        return {
            "low": [{"delay_minutes": 30, "channel": "slack"}],
            "medium": [{"delay_minutes": 15, "channel": "slack"}, {"delay_minutes": 30, "channel": "pagerduty"}],
            "high": [{"delay_minutes": 5, "channel": "slack"}, {"delay_minutes": 15, "channel": "pagerduty"}],
            "critical": [{"delay_minutes": 0, "channel": "pagerduty"}, {"delay_minutes": 5, "channel": "phone"}],
        }
    
    def create_incident(self, title: str, description: str, severity: IncidentSeverity,
                       affected_services: Optional[List[str]] = None, priority: IncidentPriority = IncidentPriority.P3) -> Incident:
        """Create a new incident."""
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        incident = Incident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            priority=priority,
            affected_services=affected_services or [],
        )
        incident.add_event("created", f"Incident created: {title}", "system")
        self.incidents[incident_id] = incident
        self._stats["total_created"] += 1
        logger.warning(f"Incident created: {incident_id} - {title} ({severity.value})")
        return incident
    
    def acknowledge(self, incident_id: str, actor: str) -> bool:
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        return incident.transition(IncidentStatus.ACKNOWLEDGED, actor)
    
    def start_investigation(self, incident_id: str, actor: str) -> bool:
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        return incident.transition(IncidentStatus.INVESTIGATING, actor)
    
    def mitigate(self, incident_id: str, actor: str, action: str) -> bool:
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        incident.add_event("mitigation", action, actor)
        return incident.transition(IncidentStatus.MITIGATING, actor)
    
    def resolve(self, incident_id: str, actor: str, resolution: str) -> bool:
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        incident.add_event("resolution", resolution, actor)
        result = incident.transition(IncidentStatus.RESOLVED, actor)
        if result:
            self._stats["total_resolved"] += 1
            if incident._mttr:
                self._stats["total_mttr"] += incident._mttr
        return result
    
    def close(self, incident_id: str, actor: str) -> bool:
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        return incident.transition(IncidentStatus.CLOSED, actor)
    
    def assign(self, incident_id: str, assignee: str) -> bool:
        incident = self.incidents.get(incident_id)
        if not incident:
            return False
        incident.assignee = assignee
        incident.add_event("assigned", f"Assigned to {assignee}", "system")
        return True
    
    def get_open_incidents(self) -> List[Incident]:
        open_statuses = {IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATING}
        return [i for i in self.incidents.values() if i.status in open_statuses]
    
    def get_incidents_by_severity(self, severity: IncidentSeverity) -> List[Incident]:
        return [i for i in self.incidents.values() if i.severity == severity]
    
    def get_incident_summary(self) -> Dict[str, Any]:
        open_count = len(self.get_open_incidents())
        resolved = [i for i in self.incidents.values() if i.status == IncidentStatus.RESOLVED]
        avg_mttr = sum(i._mttr for i in resolved if i._mttr) / len(resolved) if resolved else 0
        
        return {
            "total": len(self.incidents),
            "open": open_count,
            "resolved": len(resolved),
            "avg_mttr_minutes": round(avg_mttr / 60, 2),
            "by_severity": {
                sev.value: len(self.get_incidents_by_severity(sev))
                for sev in IncidentSeverity
            },
            "stats": self._stats,
        }
    
    def search_incidents(self, query: str) -> List[Incident]:
        query_lower = query.lower()
        results = []
        for inc in self.incidents.values():
            if (query_lower in inc.title.lower() or
                query_lower in inc.description.lower() or
                any(query_lower in s.lower() for s in inc.affected_services)):
                results.append(inc)
        return results
    
    def get_escalation_policy(self, severity: str) -> List[Dict]:
        return self._escalation_policies.get(severity, [])
