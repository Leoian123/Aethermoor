"""
Base repository con operazioni CRUD generiche.

Ogni repository riceve l'istanza MockDB parent per accedere
a _cache, _save, e agli altri repository.
"""

import uuid
from typing import Optional, List, Dict, Any


class BaseRepository:
    """Operazioni CRUD generiche su cache JSON."""

    def __init__(self, db_instance):
        self._db = db_instance

    @property
    def _cache(self):
        return self._db._cache

    def _save(self, table_name: str):
        self._db._save(table_name)

    def _generate_id(self, prefix: str = "") -> str:
        short_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{short_id}" if prefix else short_id

    def get_all(self, table: str) -> List[Dict]:
        """SELECT * FROM table"""
        return self._cache.get(table, [])

    def get_by_id(self, table: str, id: str) -> Optional[Dict]:
        """SELECT * FROM table WHERE id = ?"""
        for row in self._cache.get(table, []):
            if row.get('id') == id:
                return row
        return None

    def get_where(self, table: str, **conditions) -> List[Dict]:
        """SELECT * FROM table WHERE col1 = val1 AND col2 = val2..."""
        results = []
        for row in self._cache.get(table, []):
            match = all(row.get(k) == v for k, v in conditions.items())
            if match:
                results.append(row)
        return results

    def insert(self, table: str, data: Dict) -> Dict:
        """INSERT INTO table VALUES (...)"""
        if table not in self._cache:
            self._cache[table] = []
        self._cache[table].append(data)
        self._save(table)
        return data

    def update(self, table: str, id: str, data: Dict) -> Optional[Dict]:
        """UPDATE table SET ... WHERE id = ?"""
        for i, row in enumerate(self._cache.get(table, [])):
            if row.get('id') == id:
                self._cache[table][i] = {**row, **data}
                self._save(table)
                return self._cache[table][i]
        return None

    def delete(self, table: str, id: str) -> bool:
        """DELETE FROM table WHERE id = ?"""
        original_len = len(self._cache.get(table, []))
        self._cache[table] = [r for r in self._cache.get(table, []) if r.get('id') != id]
        if len(self._cache[table]) < original_len:
            self._save(table)
            return True
        return False

    def delete_where(self, table: str, **conditions) -> int:
        """DELETE FROM table WHERE col1 = val1 AND col2 = val2..."""
        original_len = len(self._cache.get(table, []))
        self._cache[table] = [
            row for row in self._cache.get(table, [])
            if not all(row.get(k) == v for k, v in conditions.items())
        ]
        deleted = original_len - len(self._cache[table])
        if deleted > 0:
            self._save(table)
        return deleted
