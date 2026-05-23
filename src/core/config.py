"""Configuration for ObservabilityAgent."""
import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    name: str
    enabled: bool = True
    max_retries: int = 3
    timeout_seconds: int = 300
    model: str = "mimo-v2.5-pro"
    temperature: float = 0.2
    max_tokens: int = 4096

@dataclass
class CollectorConfig:
    scrape_interval: int = 15
    batch_size: int = 1000
    max_queue_size: int = 100000
    flush_interval: int = 5
    metric_prefix: str = "obs_agent"

@dataclass
class AlertConfig:
    evaluation_interval: int = 30
    dedup_window: int = 300
    max_active_alerts: int = 1000
    notification_channels: List[str] = field(default_factory=lambda: ["log", "webhook"])
    severity_levels: List[str] = field(default_factory=lambda: ["critical", "warning", "info"])

@dataclass
class StorageConfig:
    db_path: str = "data/observability.db"
    retention_days: int = 30
    compaction_interval: int = 3600

@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

class Config:
    def __init__(self, config_path: Optional[str] = None):
        self.agent = AgentConfig(name="default")
        self.collector = CollectorConfig()
        self.alert = AlertConfig()
        self.storage = StorageConfig()
        self.web = WebConfig()
        self._config_path = config_path or os.getenv("OBS_CONFIG", "config.json")
        self._load_config()
    
    def _load_config(self):
        path = Path(self._config_path)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                for section_name in ["collector", "alert", "storage", "web"]:
                    if section_name in data:
                        section = getattr(self, section_name)
                        for k, v in data[section_name].items():
                            if hasattr(section, k):
                                setattr(section, k, v)
                logger.info(f"Config loaded from {path}")
            except Exception as e:
                logger.warning(f"Config load failed: {e}")
    
    def get_agent_config(self, name: str) -> AgentConfig:
        return AgentConfig(name=name, model=self.agent.model, temperature=self.agent.temperature)
