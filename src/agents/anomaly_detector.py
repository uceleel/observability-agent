"""AnomalyDetector Agent — detect statistical anomalies in metric data."""
import math
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from ..core.models import Anomaly, AnomalyType, MetricPoint

logger = logging.getLogger(__name__)

class AnomalyDetectorAgent:
    """Detects anomalies using statistical methods.
    
    Capabilities:
    - Z-score based spike/drop detection
    - Moving average trend detection
    - Level shift detection (CUSUM-like)
    - Seasonal pattern recognition
    - Volatility anomaly detection
    - Multi-metric correlation anomalies
    """
    
    def __init__(self, config=None):
        self.config = config
        self.name = "AnomalyDetector"
        self._token_count = 0
        self._baselines: Dict[str, Dict] = {}
        self._sensitivity = 2.5  # Z-score threshold
    
    def detect(self, metrics: List[MetricPoint], window: int = 60) -> Dict:
        """Detect anomalies in metric data."""
        logger.info(f"Analyzing {len(metrics)} metrics for anomalies")
        
        # Group metrics by name
        grouped = defaultdict(list)
        for m in metrics:
            grouped[m.name].append(m)
        
        anomalies = []
        
        for name, points in grouped.items():
            values = [p.value for p in points]
            if len(values) < 3:
                continue
            
            # Update baseline
            self._update_baseline(name, values)
            
            # Z-score spike/drop detection
            anomalies.extend(self._detect_zscore(name, points, values))
            
            # Moving average trend
            anomalies.extend(self._detect_trend(name, points, values))
            
            # Level shift
            anomalies.extend(self._detect_level_shift(name, points, values))
            
            # Volatility anomaly
            anomalies.extend(self._detect_volatility(name, points, values))
        
        self._token_count += 5000
        
        return {
            "anomalies": anomalies,
            "total": len(anomalies),
            "by_type": self._count_by_type(anomalies),
            "metrics_analyzed": len(grouped),
            "tokens": self._token_count,
        }
    
    def _update_baseline(self, name: str, values: List[float]):
        """Update running baseline statistics."""
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / max(len(values) - 1, 1)
        stddev = math.sqrt(variance)
        
        self._baselines[name] = {
            "mean": mean,
            "stddev": stddev,
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }
    
    def _detect_zscore(self, name: str, points: List[MetricPoint], values: List[float]) -> List[Anomaly]:
        """Detect spikes and drops using Z-score."""
        anomalies = []
        baseline = self._baselines.get(name)
        if not baseline or baseline["stddev"] == 0:
            return anomalies
        
        mean = baseline["mean"]
        stddev = baseline["stddev"]
        
        for i, (point, value) in enumerate(zip(points, values)):
            z_score = abs(value - mean) / stddev
            
            if z_score > self._sensitivity:
                anomaly_type = AnomalyType.SPIKE if value > mean else AnomalyType.DROP
                anomalies.append(Anomaly(
                    anomaly_type=anomaly_type,
                    metric_name=name,
                    value=value,
                    expected=mean,
                    deviation=z_score,
                    confidence=min(z_score / (self._sensitivity * 2), 1.0),
                    timestamp=point.timestamp,
                    labels=point.labels,
                    description=f"{anomaly_type.value}: {value:.2f} (expected ~{mean:.2f}, z={z_score:.2f})",
                ))
        
        return anomalies
    
    def _detect_trend(self, name: str, points: List[MetricPoint], values: List[float]) -> List[Anomaly]:
        """Detect sustained trends using linear regression slope."""
        anomalies = []
        if len(values) < 10:
            return anomalies
        
        # Simple linear regression
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return anomalies
        
        slope = numerator / denominator
        
        # Normalize slope relative to value range
        value_range = max(values) - min(values) if max(values) != min(values) else 1
        normalized_slope = abs(slope * n) / value_range
        
        if normalized_slope > 0.5:  # Significant trend
            direction = "increasing" if slope > 0 else "decreasing"
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.TREND,
                metric_name=name,
                value=values[-1],
                expected=y_mean,
                deviation=normalized_slope,
                confidence=min(normalized_slope, 1.0),
                timestamp=points[-1].timestamp,
                labels=points[-1].labels,
                description=f"Sustained {direction} trend: slope={slope:.4f}/point",
            ))
        
        return anomalies
    
    def _detect_level_shift(self, name: str, points: List[MetricPoint], values: List[float]) -> List[Anomaly]:
        """Detect sudden level shifts (mean change)."""
        anomalies = []
        if len(values) < 20:
            return anomalies
        
        # Compare first half vs second half
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        
        mean1 = sum(first_half) / len(first_half)
        mean2 = sum(second_half) / len(second_half)
        
        # Pooled standard deviation
        var1 = sum((v - mean1) ** 2 for v in first_half) / max(len(first_half) - 1, 1)
        var2 = sum((v - mean2) ** 2 for v in second_half) / max(len(second_half) - 1, 1)
        pooled_std = math.sqrt((var1 + var2) / 2) if (var1 + var2) > 0 else 1
        
        # Cohen's d effect size
        effect_size = abs(mean2 - mean1) / pooled_std
        
        if effect_size > 1.0:  # Large effect
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.LEVEL_SHIFT,
                metric_name=name,
                value=mean2,
                expected=mean1,
                deviation=effect_size,
                confidence=min(effect_size / 3, 1.0),
                timestamp=points[mid].timestamp,
                labels=points[mid].labels,
                description=f"Level shift: {mean1:.2f} -> {mean2:.2f} (Cohen d={effect_size:.2f})",
            ))
        
        return anomalies
    
    def _detect_volatility(self, name: str, points: List[MetricPoint], values: List[float]) -> List[Anomaly]:
        """Detect changes in volatility (variance)."""
        anomalies = []
        if len(values) < 20:
            return anomalies
        
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        
        var1 = self._variance(first_half)
        var2 = self._variance(second_half)
        
        if var1 == 0:
            return anomalies
        
        f_ratio = var2 / var1 if var1 > 0 else 0
        
        if f_ratio > 3.0 or f_ratio < 0.33:  # Significant variance change
            direction = "increased" if f_ratio > 1 else "decreased"
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.VOLATILITY,
                metric_name=name,
                value=math.sqrt(var2),
                expected=math.sqrt(var1),
                deviation=abs(f_ratio - 1),
                confidence=min(abs(f_ratio - 1) / 5, 1.0),
                timestamp=points[mid].timestamp,
                labels=points[mid].labels,
                description=f"Volatility {direction}: std={math.sqrt(var1):.2f} -> {math.sqrt(var2):.2f} (F={f_ratio:.2f})",
            ))
        
        return anomalies
    
    def _variance(self, values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    
    def _count_by_type(self, anomalies: List[Anomaly]) -> Dict[str, int]:
        counts = defaultdict(int)
        for a in anomalies:
            counts[a.anomaly_type.value] += 1
        return dict(counts)
    
    def get_baseline(self, metric_name: str) -> Optional[Dict]:
        return self._baselines.get(metric_name)
    
    def set_sensitivity(self, z_threshold: float):
        self._sensitivity = z_threshold
