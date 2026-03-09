"""
Repository: Chat History (messages).
"""

from datetime import datetime
from typing import List, Dict

from ..base_repository import BaseRepository


class ChatRepository(BaseRepository):
    """Operazioni su chat_history."""

    def add_chat_message(self, character_id: str, role: str, content: str) -> Dict:
        """Aggiunge messaggio alla cronologia."""
        return self.insert('chat_history', {
            'id': self._generate_id('msg'),
            'character_id': character_id,
            'role': role,
            'content': content,
            'created_at': datetime.now().isoformat()
        })

    def get_chat_history(self, character_id: str, limit: int = 50) -> List[Dict]:
        """Ottiene cronologia chat ordinata."""
        messages = self.get_where('chat_history', character_id=character_id)
        messages.sort(key=lambda m: m.get('created_at', ''))
        return messages[-limit:] if limit else messages
