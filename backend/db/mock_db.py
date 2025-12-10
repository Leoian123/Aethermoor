"""
STATISFY RPG - Mock Database
Simula un database PostgreSQL usando file JSON
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Path al data folder
DB_PATH = Path(__file__).parent / "data"


class MockDB:
    """Mock database che simula PostgreSQL con file JSON"""
    
    def __init__(self):
        self._cache = {}
        self._load_all()
    
    def _load_all(self):
        """Carica tutti i file JSON in cache"""
        for file in DB_PATH.glob("*.json"):
            table_name = file.stem
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Filtra commenti
                if isinstance(data, list):
                    self._cache[table_name] = [
                        r for r in data 
                        if isinstance(r, dict) and '_comment' not in r
                    ]
                else:
                    self._cache[table_name] = data
    
    def _save(self, table_name: str):
        """Salva una tabella su disco"""
        file_path = DB_PATH / f"{table_name}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self._cache.get(table_name, []), f, indent=2, ensure_ascii=False)
    
    def _generate_id(self, prefix: str = "") -> str:
        """Genera un UUID con prefisso opzionale"""
        short_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{short_id}" if prefix else short_id
    
    # ═══════════════════════════════════════
    # CRUD GENERICO
    # ═══════════════════════════════════════
    
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
    
    # ═══════════════════════════════════════
    # CHARACTERS
    # ═══════════════════════════════════════
    
    def create_character(
        self,
        slot: int,
        name: str,
        class_id: str,
        str_stat: int = 10,
        dex_stat: int = 10,
        vit_stat: int = 10,
        int_stat: int = 10
    ) -> Dict:
        """Crea un nuovo personaggio con stats derivate"""
        
        # Ottieni classe per calcolare HP/Mana
        char_class = self.get_by_id('classes', class_id)
        if not char_class:
            raise ValueError(f"Classe non trovata: {class_id}")
        
        # Calcola HP e Mana
        hp_max = char_class['hp_base'] + (vit_stat * char_class['hp_per_vit'])
        mana_max = char_class['mana_base'] + (int_stat * char_class['mana_per_int'])
        
        character = {
            'id': self._generate_id('char'),
            'slot': slot,
            'name': name,
            'class_id': class_id,
            'level': 1,
            'xp': 0,
            'hp_current': hp_max,
            'hp_max': hp_max,
            'mana_current': mana_max,
            'mana_max': mana_max,
            'str': str_stat,
            'dex': dex_stat,
            'vit': vit_stat,
            'int': int_stat,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.insert('characters', character)
        
        # Assegna equipaggiamento iniziale
        for eq_id in char_class.get('starting_equipment_ids', []):
            equipment = self.get_by_id('equipment', eq_id)
            if equipment:
                self.insert('character_equipment', {
                    'id': self._generate_id('ceq'),
                    'character_id': character['id'],
                    'equipment_id': eq_id,
                    'equipped_slot': equipment.get('slot', 'inventory')
                })
        
        # Assegna abilità iniziale
        starting_tag = char_class.get('starting_ability_tag')
        if starting_tag:
            skill = self.get_skill_by_tag(starting_tag)
            if skill:
                self.add_character_skill(character['id'], skill['id'], mastery=1)
                
                # Aggiungi anche la skill padre se esiste
                if skill.get('parent_id'):
                    parent = self.get_by_id('skills', skill['parent_id'])
                    if parent:
                        self.add_character_skill(character['id'], parent['id'], mastery=1)
        
        return character
    
    def get_character_by_slot(self, slot: int) -> Optional[Dict]:
        """Ottieni personaggio per slot"""
        chars = self.get_where('characters', slot=slot)
        return chars[0] if chars else None
    
    def get_character_full(self, character_id: str) -> Optional[Dict]:
        """Ottieni personaggio con tutte le relazioni (JOIN simulato)"""
        char = self.get_by_id('characters', character_id)
        if not char:
            return None
        
        # Classe
        char['class'] = self.get_by_id('classes', char['class_id'])
        
        # Skills con dettagli
        char_skills = self.get_where('character_skills', character_id=character_id)
        char['skills'] = []
        for cs in char_skills:
            skill = self.get_by_id('skills', cs['skill_id'])
            if skill:
                char['skills'].append({
                    **skill,
                    'mastery': cs['mastery'],
                    'unlocked_at': cs.get('unlocked_at')
                })
        
        # Equipment con dettagli
        char_eq = self.get_where('character_equipment', character_id=character_id)
        char['equipment'] = []
        for ce in char_eq:
            eq = self.get_by_id('equipment', ce['equipment_id'])
            if eq:
                char['equipment'].append({
                    **eq,
                    'equipped_slot': ce['equipped_slot']
                })
        
        # Inventario
        char['inventory'] = self.get_where('inventory', character_id=character_id)
        
        return char
    
    def delete_character(self, character_id: str) -> bool:
        """Elimina personaggio e tutte le relazioni (CASCADE)"""
        self.delete_where('character_skills', character_id=character_id)
        self.delete_where('character_equipment', character_id=character_id)
        self.delete_where('inventory', character_id=character_id)
        self.delete_where('chat_history', character_id=character_id)
        return self.delete('characters', character_id)
    
    # ═══════════════════════════════════════
    # SKILLS
    # ═══════════════════════════════════════
    
    def get_skill_by_tag(self, tag: str) -> Optional[Dict]:
        """Trova skill per tag"""
        skills = self.get_where('skills', tag=tag)
        return skills[0] if skills else None
    
    def get_skills_by_category(self, category: str) -> List[Dict]:
        """Ottieni tutte le skill di una categoria"""
        return self.get_where('skills', category=category)
    
    def get_skill_tree(self, root_id: str) -> List[Dict]:
        """Ottieni albero skill a partire da una root"""
        root = self.get_by_id('skills', root_id)
        if not root:
            return []
        
        tree = [root]
        children = self.get_where('skills', parent_id=root_id)
        for child in children:
            tree.extend(self.get_skill_tree(child['id']))
        
        return tree
    
    def get_root_skills(self) -> List[Dict]:
        """Ottieni tutte le skill root (senza parent)"""
        return [s for s in self.get_all('skills') if s.get('parent_id') is None]
    
    def add_character_skill(self, character_id: str, skill_id: str, mastery: int = 1) -> Dict:
        """Aggiunge una skill al personaggio"""
        existing = self.get_where('character_skills', character_id=character_id, skill_id=skill_id)
        if existing:
            # Aggiorna mastery se già esiste
            return self.update('character_skills', existing[0]['id'], {'mastery': mastery})
        
        return self.insert('character_skills', {
            'id': self._generate_id('csk'),
            'character_id': character_id,
            'skill_id': skill_id,
            'mastery': max(1, min(10, mastery)),
            'unlocked_at': datetime.now().isoformat()
        })
    
    def update_skill_mastery(self, character_id: str, skill_tag: str, delta: int = 1) -> Optional[Dict]:
        """Aumenta/diminuisce mastery di una skill"""
        skill = self.get_skill_by_tag(skill_tag)
        if not skill:
            return None
        
        char_skill = self.get_where('character_skills', character_id=character_id, skill_id=skill['id'])
        if not char_skill:
            return None
        
        new_mastery = max(1, min(10, char_skill[0]['mastery'] + delta))
        return self.update('character_skills', char_skill[0]['id'], {'mastery': new_mastery})
    
    def generate_skill_tag(self, category: str, name: str, parent_tag: Optional[str] = None) -> str:
        """Genera un tag unico per una skill"""
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
    
    # ═══════════════════════════════════════
    # CLASSES
    # ═══════════════════════════════════════
    
    def get_all_classes(self) -> List[Dict]:
        """Ottieni tutte le classi disponibili"""
        return self.get_all('classes')
    
    # ═══════════════════════════════════════
    # EQUIPMENT
    # ═══════════════════════════════════════
    
    def equip_item(self, character_id: str, equipment_id: str, slot: str) -> Dict:
        """Equipaggia un item in uno slot"""
        # Rimuovi item precedente nello stesso slot
        self.delete_where('character_equipment', character_id=character_id, equipped_slot=slot)
        
        return self.insert('character_equipment', {
            'id': self._generate_id('ceq'),
            'character_id': character_id,
            'equipment_id': equipment_id,
            'equipped_slot': slot
        })
    
    # ═══════════════════════════════════════
    # INVENTORY
    # ═══════════════════════════════════════
    
    def add_to_inventory(self, character_id: str, item_name: str, quantity: int = 1, metadata: Dict = None) -> Dict:
        """Aggiunge item all'inventario"""
        existing = self.get_where('inventory', character_id=character_id, item_name=item_name)
        if existing:
            new_qty = existing[0].get('quantity', 0) + quantity
            return self.update('inventory', existing[0]['id'], {'quantity': new_qty})
        
        return self.insert('inventory', {
            'id': self._generate_id('inv'),
            'character_id': character_id,
            'item_name': item_name,
            'quantity': quantity,
            'metadata': metadata or {}
        })
    
    def remove_from_inventory(self, character_id: str, item_name: str, quantity: int = 1) -> bool:
        """Rimuove item dall'inventario"""
        existing = self.get_where('inventory', character_id=character_id, item_name=item_name)
        if not existing:
            return False
        
        current_qty = existing[0].get('quantity', 0)
        if quantity >= current_qty:
            return self.delete('inventory', existing[0]['id'])
        else:
            self.update('inventory', existing[0]['id'], {'quantity': current_qty - quantity})
            return True
    
    # ═══════════════════════════════════════
    # CHAT HISTORY
    # ═══════════════════════════════════════
    
    def add_chat_message(self, character_id: str, role: str, content: str) -> Dict:
        """Aggiunge messaggio alla cronologia"""
        return self.insert('chat_history', {
            'id': self._generate_id('msg'),
            'character_id': character_id,
            'role': role,
            'content': content,
            'created_at': datetime.now().isoformat()
        })
    
    def get_chat_history(self, character_id: str, limit: int = 50) -> List[Dict]:
        """Ottiene cronologia chat ordinata"""
        messages = self.get_where('chat_history', character_id=character_id)
        messages.sort(key=lambda m: m.get('created_at', ''))
        return messages[-limit:] if limit else messages


# Singleton instance
db = MockDB()
