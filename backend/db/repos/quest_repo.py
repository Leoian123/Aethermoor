"""
Repository: Quests e Journal Notes.
"""

from datetime import datetime
from typing import Optional, List, Dict

from ..base_repository import BaseRepository


class QuestRepository(BaseRepository):
    """Operazioni su quests, character_quests e journal_notes."""

    def get_quest_by_name(self, name: str) -> Optional[Dict]:
        """Trova quest per nome (case-insensitive)."""
        for quest in self._cache.get('quests', []):
            if quest.get('name', '').lower() == name.lower():
                return quest
        return None

    def get_character_active_quests(self, character_id: str) -> List[Dict]:
        """Ottieni quest attive con dati quest (JOIN)."""
        char_quests = self.get_where(
            'character_quests', character_id=character_id, status='active'
        )
        result = []
        for cq in char_quests:
            quest = self.get_by_id('quests', cq['quest_id'])
            if quest:
                result.append({**cq, 'quest': quest})
        return result

    def get_character_quest_history(self, character_id: str, limit: int = 10) -> List[Dict]:
        """Ottieni quest completate/fallite recenti (JOIN)."""
        char_quests = [
            cq for cq in self.get_where('character_quests', character_id=character_id)
            if cq.get('status') in ('completed', 'failed')
        ]
        char_quests.sort(key=lambda cq: cq.get('completed_at', ''), reverse=True)
        char_quests = char_quests[:limit]

        result = []
        for cq in char_quests:
            quest = self.get_by_id('quests', cq['quest_id'])
            if quest:
                result.append({**cq, 'quest': quest})
        return result

    def get_character_quest_by_name(self, character_id: str, quest_name: str, status: str = 'active') -> Optional[Dict]:
        """Trova una quest specifica per nome e status."""
        active = self.get_where('character_quests', character_id=character_id, status=status)
        for cq in active:
            quest = self.get_by_id('quests', cq['quest_id'])
            if quest and quest.get('name', '').lower() == quest_name.lower():
                return {**cq, 'quest': quest}
        return None

    # ── Journal Notes ──

    def get_journal_notes(self, character_id: str) -> List[Dict]:
        """Ottieni tutte le note del diario per un personaggio."""
        notes = self.get_where('journal_notes', character_id=character_id)
        notes.sort(key=lambda n: n.get('updated_at', n.get('created_at', '')), reverse=True)
        return notes

    def save_journal_note(self, character_id: str, content: str, note_id: Optional[str] = None) -> Dict:
        """Crea o aggiorna una nota del diario."""
        if note_id:
            existing = self.get_by_id('journal_notes', note_id)
            if existing and existing.get('character_id') == character_id:
                return self.update('journal_notes', note_id, {
                    'content': content,
                    'updated_at': datetime.now().isoformat(),
                })
        note = {
            'id': self._generate_id('jn'),
            'character_id': character_id,
            'content': content,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
        return self.insert('journal_notes', note)

    def delete_journal_note(self, character_id: str, note_id: str) -> bool:
        """Elimina una nota del diario (verifica ownership)."""
        existing = self.get_by_id('journal_notes', note_id)
        if existing and existing.get('character_id') == character_id:
            return self.delete('journal_notes', note_id)
        return False
