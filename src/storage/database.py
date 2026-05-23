"""Storage database for observability data persistence."""
import time
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Record:
    """Generic database record."""
    record_id: str
    table: str
    data: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1


class ObservabilityDatabase:
    """In-memory database for observability data."""
    
    def __init__(self, max_records: int = 100000):
        self.max_records = max_records
        self._tables: Dict[str, Dict[str, Record]] = defaultdict(dict)
        self._indexes: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
        self._query_count = 0
        self._write_count = 0
        self._start_time = time.time()
    
    def insert(self, table: str, data: Dict[str, Any], record_id: Optional[str] = None) -> str:
        """Insert a record into a table."""
        rid = record_id or self._generate_id(table, data)
        record = Record(record_id=rid, table=table, data=data)
        self._tables[table][rid] = record
        self._write_count += 1
        self._update_indexes(table, rid, data)
        self._enforce_limits(table)
        return rid
    
    def get(self, table: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Get a record by ID."""
        self._query_count += 1
        record = self._tables.get(table, {}).get(record_id)
        return record.data if record else None
    
    def update(self, table: str, record_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing record."""
        record = self._tables.get(table, {}).get(record_id)
        if not record:
            return False
        record.data.update(data)
        record.updated_at = time.time()
        record.version += 1
        self._write_count += 1
        return True
    
    def delete(self, table: str, record_id: str) -> bool:
        """Delete a record."""
        if record_id in self._tables.get(table, {}):
            del self._tables[table][record_id]
            self._write_count += 1
            return True
        return False
    
    def query(self, table: str, filters: Optional[Dict[str, Any]] = None,
              limit: int = 100, offset: int = 0, sort_by: Optional[str] = None,
              sort_desc: bool = True) -> List[Dict[str, Any]]:
        """Query records with optional filtering and sorting."""
        self._query_count += 1
        records = list(self._tables.get(table, {}).values())
        
        if filters:
            records = [r for r in records if self._match_filters(r.data, filters)]
        
        if sort_by:
            records.sort(key=lambda r: r.data.get(sort_by, 0), reverse=sort_desc)
        
        return [r.data for r in records[offset:offset + limit]]
    
    def count(self, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching filters."""
        records = list(self._tables.get(table, {}).values())
        if filters:
            records = [r for r in records if self._match_filters(r.data, filters)]
        return len(records)
    
    def bulk_insert(self, table: str, records: List[Dict[str, Any]]) -> int:
        """Insert multiple records at once."""
        count = 0
        for data in records:
            self.insert(table, data)
            count += 1
        return count
    
    def get_latest(self, table: str, field: str = "timestamp", limit: int = 10) -> List[Dict]:
        """Get most recent records."""
        return self.query(table, sort_by=field, sort_desc=True, limit=limit)
    
    def get_range(self, table: str, start: float, end: float,
                  time_field: str = "timestamp") -> List[Dict]:
        """Get records within a time range."""
        self._query_count += 1
        records = self._tables.get(table, {}).values()
        return [
            r.data for r in records
            if start <= r.data.get(time_field, 0) <= end
        ]
    
    def aggregate(self, table: str, field: str, operation: str = "avg",
                  filters: Optional[Dict] = None) -> Optional[float]:
        """Aggregate a field across records."""
        records = self.query(table, filters=filters, limit=self.max_records)
        values = [r.get(field, 0) for r in records if field in r]
        if not values:
            return None
        if operation == "avg":
            return sum(values) / len(values)
        elif operation == "sum":
            return sum(values)
        elif operation == "min":
            return min(values)
        elif operation == "max":
            return max(values)
        elif operation == "count":
            return float(len(values))
        return sum(values) / len(values)
    
    def group_by(self, table: str, group_field: str, agg_field: str,
                 agg_op: str = "count", filters: Optional[Dict] = None) -> Dict[str, float]:
        """Group records and aggregate."""
        records = self.query(table, filters=filters, limit=self.max_records)
        groups: Dict[str, List[float]] = defaultdict(list)
        for r in records:
            key = str(r.get(group_field, "unknown"))
            if agg_op == "count":
                groups[key].append(1)
            elif agg_field in r:
                groups[key].append(r[agg_field])
        
        result = {}
        for key, values in groups.items():
            if agg_op == "count":
                result[key] = float(len(values))
            elif agg_op == "avg":
                result[key] = sum(values) / len(values)
            elif agg_op == "sum":
                result[key] = sum(values)
            elif agg_op == "max":
                result[key] = max(values)
            elif agg_op == "min":
                result[key] = min(values)
        return result
    
    def truncate(self, table: str) -> int:
        """Remove all records from a table."""
        count = len(self._tables.get(table, {}))
        self._tables[table] = {}
        self._indexes.pop(table, None)
        return count
    
    def tables(self) -> List[str]:
        """List all tables."""
        return list(self._tables.keys())
    
    def table_info(self, table: str) -> Dict[str, Any]:
        """Get table metadata."""
        records = self._tables.get(table, {})
        return {
            "name": table,
            "record_count": len(records),
            "oldest": min((r.created_at for r in records.values()), default=0),
            "newest": max((r.created_at for r in records.values()), default=0),
        }
    
    def stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "tables": len(self._tables),
            "total_records": sum(len(t) for t in self._tables.values()),
            "query_count": self._query_count,
            "write_count": self._write_count,
            "uptime_seconds": time.time() - self._start_time,
            "max_records": self.max_records,
        }
    
    def _generate_id(self, table: str, data: Dict) -> str:
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(f"{table}:{content}:{time.time()}".encode()).hexdigest()[:12]
    
    def _match_filters(self, data: Dict, filters: Dict) -> bool:
        for key, value in filters.items():
            if key not in data:
                return False
            if isinstance(value, dict):
                op = value.get("op", "eq")
                val = value.get("value")
                if op == "eq" and data[key] != val:
                    return False
                elif op == "gt" and data[key] <= val:
                    return False
                elif op == "lt" and data[key] >= val:
                    return False
                elif op == "gte" and data[key] < val:
                    return False
                elif op == "lte" and data[key] > val:
                    return False
                elif op == "neq" and data[key] == val:
                    return False
                elif op == "contains" and val not in str(data[key]):
                    return False
            elif data[key] != value:
                return False
        return True
    
    def _update_indexes(self, table: str, record_id: str, data: Dict) -> None:
        for key in data:
            value = str(data[key])
            self._indexes[table][f"{key}:{value}"].add(record_id)
    
    def _enforce_limits(self, table: str) -> None:
        records = self._tables.get(table, {})
        if len(records) > self.max_records:
            sorted_records = sorted(records.values(), key=lambda r: r.created_at)
            to_remove = len(records) - self.max_records
            for r in sorted_records[:to_remove]:
                del self._tables[table][r.record_id]
