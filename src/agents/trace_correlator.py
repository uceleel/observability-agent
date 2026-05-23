"""TraceCorrelator Agent — correlate distributed traces and find bottlenecks."""
import logging
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from ..core.models import TraceSpan

logger = logging.getLogger(__name__)

class TraceCorrelatorAgent:
    """Correlates distributed traces to find bottlenecks and failures.
    
    Capabilities:
    - Trace tree reconstruction
    - Critical path analysis
    - Bottleneck detection
    - Error propagation tracking
    - Cross-service dependency mapping
    - Latency attribution
    """
    
    def __init__(self, config=None):
        self.config = config
        self.name = "TraceCorrelator"
        self._token_count = 0
        self._service_deps: Dict[str, Set[str]] = defaultdict(set)
        self._latency_stats: Dict[str, List[float]] = defaultdict(list)
    
    def correlate(self, traces: List[TraceSpan]) -> Dict:
        """Analyze and correlate a batch of trace spans."""
        logger.info(f"Correlating {len(traces)} trace spans")
        
        # Build trace trees
        trace_trees = self._build_trace_trees(traces)
        
        # Analyze each trace
        insights = []
        bottlenecks = []
        error_chains = []
        
        for trace_id, spans in trace_trees.items():
            # Critical path analysis
            critical_path = self._find_critical_path(spans)
            if critical_path:
                total_duration = sum(s.duration_ms for s in critical_path)
                slowest = max(critical_path, key=lambda s: s.duration_ms)
                
                if slowest.duration_ms > 500:  # >500ms is slow
                    bottlenecks.append({
                        "trace_id": trace_id,
                        "operation": slowest.operation,
                        "duration_ms": slowest.duration_ms,
                        "total_duration_ms": total_duration,
                        "percentage": (slowest.duration_ms / max(total_duration, 1)) * 100,
                    })
            
            # Error propagation
            error_spans = [s for s in spans if s.status == "error"]
            if error_spans:
                error_chain = self._trace_error_propagation(spans, error_spans)
                error_chains.append({
                    "trace_id": trace_id,
                    "error_count": len(error_spans),
                    "root_error": error_spans[0].operation if error_spans else None,
                    "chain": error_chain,
                })
            
            # Service dependencies
            self._map_dependencies(spans)
            
            # Latency stats
            for span in spans:
                self._latency_stats[span.operation].append(span.duration_ms)
        
        # Generate insights
        if bottlenecks:
            top_bottleneck = max(bottlenecks, key=lambda b: b["duration_ms"])
            insights.append({
                "type": "bottleneck",
                "severity": "warning",
                "message": f"Top bottleneck: {top_bottleneck['operation']} ({top_bottleneck['duration_ms']:.0f}ms, {top_bottleneck['percentage']:.1f}% of total)",
                "recommendation": f"Optimize {top_bottleneck['operation']} — it accounts for {top_bottleneck['percentage']:.0f}% of trace latency",
            })
        
        if error_chains:
            insights.append({
                "type": "error_propagation",
                "severity": "critical",
                "message": f"Found {len(error_chains)} traces with error propagation",
                "recommendation": "Add circuit breakers at error propagation boundaries",
            })
        
        # Latency percentiles
        percentiles = self._calculate_percentiles()
        
        self._token_count += 5000
        
        return {
            "insights": insights,
            "bottlenecks": bottlenecks[:10],
            "error_chains": error_chains[:10],
            "service_dependencies": {k: list(v) for k, v in self._service_deps.items()},
            "latency_percentiles": percentiles,
            "traces_analyzed": len(trace_trees),
            "tokens": self._token_count,
        }
    
    def _build_trace_trees(self, spans: List[TraceSpan]) -> Dict[str, List[TraceSpan]]:
        """Group spans by trace ID."""
        trees = defaultdict(list)
        for span in spans:
            trees[span.trace_id].append(span)
        return dict(trees)
    
    def _find_critical_path(self, spans: List[TraceSpan]) -> List[TraceSpan]:
        """Find the critical path through a trace (longest path)."""
        if not spans:
            return []
        
        # Build parent-child relationships
        span_map = {s.span_id: s for s in spans}
        children = defaultdict(list)
        root = None
        
        for span in spans:
            if span.parent_id and span.parent_id in span_map:
                children[span.parent_id].append(span)
            elif not span.parent_id:
                root = span
        
        if not root:
            return spans[:1]
        
        # DFS to find longest path
        def longest_path(span_id: str) -> List[TraceSpan]:
            kids = children.get(span_id, [])
            if not kids:
                return [span_map[span_id]]
            
            best = []
            for kid in kids:
                path = longest_path(kid.span_id)
                if sum(s.duration_ms for s in path) > sum(s.duration_ms for s in best):
                    best = path
            
            return [span_map[span_id]] + best
        
        return longest_path(root.span_id)
    
    def _trace_error_propagation(self, all_spans: List[TraceSpan], error_spans: List[TraceSpan]) -> List[str]:
        """Trace how errors propagate through services."""
        chain = []
        span_map = {s.span_id: s for s in all_spans}
        
        for error_span in error_spans:
            current = error_span
            path = [current.operation]
            while current.parent_id and current.parent_id in span_map:
                current = span_map[current.parent_id]
                path.append(current.operation)
            chain.append(" -> ".join(reversed(path)))
        
        return chain
    
    def _map_dependencies(self, spans: List[TraceSpan]):
        """Map service dependencies from trace."""
        for span in spans:
            if span.parent_id:
                parent = next((s for s in spans if s.span_id == span.parent_id), None)
                if parent and parent.labels.get("service") != span.labels.get("service"):
                    self._service_deps[parent.labels.get("service", "unknown")].add(span.labels.get("service", "unknown"))
    
    def _calculate_percentiles(self) -> Dict[str, Dict[str, float]]:
        """Calculate latency percentiles per operation."""
        result = {}
        for op, durations in self._latency_stats.items():
            if not durations:
                continue
            sorted_d = sorted(durations)
            n = len(sorted_d)
            result[op] = {
                "p50": sorted_d[int(n * 0.5)],
                "p90": sorted_d[int(n * 0.9)],
                "p95": sorted_d[min(int(n * 0.95), n-1)],
                "p99": sorted_d[min(int(n * 0.99), n-1)],
                "count": n,
                "mean": sum(sorted_d) / n,
            }
        return result
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._service_deps.items()}
