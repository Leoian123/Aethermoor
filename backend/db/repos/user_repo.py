"""
Repository: Users (lookup, create).
"""

from datetime import datetime
from typing import Optional, Dict

from ..base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Operazioni su utenti."""

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Trova utente per username (case-insensitive)."""
        for user in self._cache.get('users', []):
            if user.get('username', '').lower() == username.lower():
                return user
        return None

    def create_user(self, username: str, password_hash: str) -> Dict:
        """Crea un nuovo utente."""
        user = {
            'id': self._generate_id('user'),
            'username': username,
            'password_hash': password_hash,
            'created_at': datetime.now().isoformat(),
        }
        return self.insert('users', user)
