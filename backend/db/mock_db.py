"""
STATISFY RPG - Mock Database (Facade)

Simula un database PostgreSQL usando file JSON.
Le operazioni sono delegate ai repository specializzati.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict

from .base_repository import BaseRepository
from .repos import (
    CharacterRepository,
    SkillRepository,
    EquipmentRepository,
    UserRepository,
    ChatRepository,
    QuestRepository,
)

# Path al data folder
DB_PATH = Path(__file__).parent / "data"


class MockDB:
    """Mock database — facade che delega ai repository.

    Tutti i metodi delle versioni precedenti continuano a
    funzionare grazie a __getattr__ che cerca nei repository.
    """

    def __init__(self):
        self._cache = {}
        self._load_all()

        # Componi repository
        self.characters = CharacterRepository(self)
        self.skills = SkillRepository(self)
        self.equipment = EquipmentRepository(self)
        self.users = UserRepository(self)
        self.chat = ChatRepository(self)
        self.quests = QuestRepository(self)

        # Repository per CRUD generico
        self._base = BaseRepository(self)

    def _load_all(self):
        """Carica tutti i file JSON in cache."""
        for file in DB_PATH.glob("*.json"):
            table_name = file.stem
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._cache[table_name] = [
                        r for r in data
                        if isinstance(r, dict) and '_comment' not in r
                    ]
                else:
                    self._cache[table_name] = data

    def _save(self, table_name: str):
        """Salva una tabella su disco."""
        file_path = DB_PATH / f"{table_name}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self._cache.get(table_name, []), f, indent=2, ensure_ascii=False)

    # ── CRUD generico (delegato esplicitamente) ──

    def get_all(self, table: str) -> List[Dict]:
        return self._base.get_all(table)

    def get_by_id(self, table: str, id: str) -> Optional[Dict]:
        return self._base.get_by_id(table, id)

    def get_where(self, table: str, **conditions) -> List[Dict]:
        return self._base.get_where(table, **conditions)

    def insert(self, table: str, data: Dict) -> Dict:
        return self._base.insert(table, data)

    def update(self, table: str, id: str, data: Dict) -> Optional[Dict]:
        return self._base.update(table, id, data)

    def delete(self, table: str, id: str) -> bool:
        return self._base.delete(table, id)

    def delete_where(self, table: str, **conditions) -> int:
        return self._base.delete_where(table, **conditions)

    # ── Backward compatibility ──

    def __getattr__(self, name):
        """Delega metodi sconosciuti ai repository."""
        repos = ['characters', 'skills', 'equipment', 'users', 'chat', 'quests']
        for repo_name in repos:
            repo = object.__getattribute__(self, '__dict__').get(repo_name)
            if repo and hasattr(repo, name):
                return getattr(repo, name)
        raise AttributeError(f"MockDB has no attribute '{name}'")


# Singleton instance
db = MockDB()
