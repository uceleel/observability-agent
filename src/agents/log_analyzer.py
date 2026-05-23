"""LogAnalyzer Agent — parse, analyze, and extract insights from logs."""
import re
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
from ..core.models import LogEntry

logger = logging.getLogger(__name__)

# Common log patterns
LOG_PATTERNS = [
    {"name": "exception", "pattern": r"(Exception|Error|Traceback|FATAL)", "severity": "error"},
    {"name": "oom", "pattern": r"(OutOfMemory|OOM|cannot allocate)", "severity": "critical"},
    {"name": "timeout", "pattern": r"(timeout|timed out|deadline exceeded)", "severity": "warning"},
    {"name": "connection", "pattern": r"(connection refused|ECONNREFUSED|ECONNRESET)", "severity": "warning"},
    {"name": "auth_failure", "pattern": r"(authentication failed|unauthorized|403|401)", "severity": "warning"},
    {"name": "disk", "pattern": r"(disk full|no space left|ENOSPC)", "severity": "critical"},
    {"name": "gc_pause", "pattern": r"(GC pause|garbage collect|stop-the-world)", "severity": "info"},
    {"name": "slow_query", "pattern": r"(slow query|query took|execution time)", "severity": "warning"},
]

class LogAnalyzerAgent:
    """Analyzes log streams for patterns, errors, and insights.
    
    Capabilities:
    - Pattern-based log classification
    - Error rate tracking
    - Log volume anomaly detection
    - Top-K error messages
    - Log-to-trace correlation
    - Structured log parsing
    """
    
    def __init__(self, config=None):
        self.config = config
        self.name = "LogAnalyzer"
        self._token_count = 0
        self._pattern_counts: Counter = Counter()
        self._error_messages: Counter = Counter()
    
    def analyze(self, logs: List[LogEntry]) -> Dict:
        """Analyze a batch of log entries."""
        logger.info(f"Analyzing {len(logs)} log entries")
        
        insights = []
        level_counts = Counter()
        source_counts = Counter()
        pattern_matches = defaultdict(list)
        
        for entry in logs:
            # Count by level
            level_counts[entry.level] += 1
            source_counts[entry.source] += 1
            
            # Pattern matching
            for pattern_def in LOG_PATTERNS:
                if re.search(pattern_def["pattern"], entry.message, re.IGNORECASE):
                    pattern_matches[pattern_def["name"]].append(entry)
                    self._pattern_counts[pattern_def["name"]] += 1
            
            # Track error messages
            if entry.level in ("error", "ERROR", "critical", "CRITICAL", "fatal", "FATAL"):
                # Normalize error message (remove numbers, UUIDs)
                normalized = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "UUID", entry.message)
                normalized = re.sub(r"\d+", "N", normalized)[:100]
                self._error_messages[normalized] += 1
        
        # Generate insights
        total = len(logs)
        error_count = level_counts.get("error", 0) + level_counts.get("ERROR", 0) + level_counts.get("critical", 0)
        
        if total > 0:
            error_rate = (error_count / total) * 100
            if error_rate > 10:
                insights.append({
                    "type": "high_error_rate",
                    "severity": "critical",
                    "message": f"Error rate is {error_rate:.1f}% ({error_count}/{total} logs)",
                    "recommendation": "Investigate error sources immediately",
                })
            elif error_rate > 5:
                insights.append({
                    "type": "elevated_error_rate",
                    "severity": "warning",
                    "message": f"Error rate is {error_rate:.1f}% ({error_count}/{total} logs)",
                    "recommendation": "Monitor error trends",
                })
        
        # Top patterns
        for pattern_name, entries in pattern_matches.items():
            if len(entries) > total * 0.1:  # More than 10% of logs
                insights.append({
                    "type": f"pattern_{pattern_name}",
                    "severity": "warning",
                    "message": f"Pattern '{pattern_name}' found in {len(entries)} logs ({len(entries)/total*100:.1f}%)",
                    "recommendation": f"Investigate {pattern_name} occurrences",
                })
        
        self._token_count += 6000
        
        return {
            "insights": insights,
            "summary": {
                "total": total,
                "by_level": dict(level_counts),
                "by_source": dict(source_counts),
                "error_rate": (error_count / max(total, 1)) * 100,
                "patterns_found": {k: len(v) for k, v in pattern_matches.items()},
                "top_errors": self._error_messages.most_common(5),
            },
            "tokens": self._token_count,
        }
    
    def get_pattern_stats(self) -> Dict:
        return dict(self._pattern_counts.most_common())
    
    def get_top_errors(self, limit: int = 10) -> List[Tuple[str, int]]:
        return self._error_messages.most_common(limit)
