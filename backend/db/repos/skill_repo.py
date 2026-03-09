"""
Repository: Skills (lookup, tree, mastery).
"""

from datetime import datetime
from typing import Optional, List, Dict

from ..base_repository import BaseRepository


class SkillRepository(BaseRepository):
    """Operazioni su skills e character_skills."""

    def get_skill_by_tag(self, tag: str) -> Optional[Dict]:
        """Trova skill per tag."""
        skills = self.get_where('skills', tag=tag)
        return skills[0] if skills else None

    def get_skills_by_category(self, category: str) -> List[Dict]:
        """Ottieni tutte le skill di una categoria."""
        return self.get_where('skills', category=category)

    def get_skill_tree(self, root_id: str) -> List[Dict]:
        """Ottieni albero skill a partire da una root."""
        root = self.get_by_id('skills', root_id)
        if not root:
            return []

        tree = [root]
        children = self.get_where('skills', parent_id=root_id)
        for child in children:
            tree.extend(self.get_skill_tree(child['id']))

        return tree

    def get_root_skills(self) -> List[Dict]:
        """Ottieni tutte le skill root (senza parent)."""
        return [s for s in self.get_all('skills') if s.get('parent_id') is None]

    def add_character_skill(self, character_id: str, skill_id: str, mastery: int = 1) -> Dict:
        """Aggiunge una skill al personaggio."""
        existing = self.get_where('character_skills', character_id=character_id, skill_id=skill_id)
        if existing:
            return self.update('character_skills', existing[0]['id'], {'mastery': mastery})

        return self.insert('character_skills', {
            'id': self._generate_id('csk'),
            'character_id': character_id,
            'skill_id': skill_id,
            'mastery': max(1, min(10, mastery)),
            'unlocked_at': datetime.now().isoformat()
        })

    def update_skill_mastery(self, character_id: str, skill_tag: str, delta: int = 1) -> Optional[Dict]:
        """Aumenta/diminuisce mastery di una skill."""
        skill = self.get_skill_by_tag(skill_tag)
        if not skill:
            return None

        char_skill = self.get_where('character_skills', character_id=character_id, skill_id=skill['id'])
        if not char_skill:
            return None

        new_mastery = max(1, min(10, char_skill[0]['mastery'] + delta))
        return self.update('character_skills', char_skill[0]['id'], {'mastery': new_mastery})

    def generate_skill_tag(self, category: str, name: str, parent_tag: Optional[str] = None) -> str:
        """Genera un tag unico per una skill."""
        prefix_map = {
            'sphere': 'SPHERE',
            'martial': 'MARTIAL',
            'knowledge': 'KNOWLEDGE'
        }

        slug = name.upper().replace(' ', '_').replace("'", "")

        if parent_tag:
            return f"{parent_tag}_{slug}"
        else:
            return f"{prefix_map.get(category, 'SKILL')}_{slug}"
