"""Formatting utilities."""
from typing import Dict

def format_metric(name: str, value: float, labels: Dict[str, str] = None) -> str:
    """Format a metric for display."""
    label_str = ""
    if labels:
        label_str = "{" + ", ".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
    return f"{name}{label_str} {value}"

def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}h"
    else:
        return f"{seconds/86400:.1f}d"

def format_bytes(bytes_val: float) -> str:
    """Format bytes in human-readable form."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}PB"

def format_number(n: float) -> str:
    """Format large numbers with suffixes."""
    for suffix in ["", "K", "M", "B", "T"]:
        if abs(n) < 1000:
            return f"{n:.1f}{suffix}"
        n /= 1000
    return f"{n:.1f}Q"
