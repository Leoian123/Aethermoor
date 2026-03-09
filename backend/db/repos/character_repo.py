"""
Repository: Character CRUD, slots, stats.

Cross-repo: accede a skills e equipment via self._db.
"""

from datetime import datetime
from typing import Optional, List, Dict

from stats import (
    STAT_KEYS, compute_total_stats, compute_equipment_bonuses,
    compute_derived_stats, empty_stat_bonuses, compute_invest_points_available,
    apply_condition_modifiers
)
from ..base_repository import BaseRepository


class CharacterRepository(BaseRepository):
    """Operazioni su personaggi."""

    def create_character(
        self,
        user_id: str,
        slot: int,
        name: str,
        class_id: str,
        str_stat: int = 10,
        dex_stat: int = 10,
        vit_stat: int = 10,
        int_stat: int = 10
    ) -> Dict:
        """Crea un nuovo personaggio con stats derivate."""
        char_class = self.get_by_id('classes', class_id)
        if not char_class:
            raise ValueError(f"Classe non trovata: {class_id}")

        base_stats = {'str': str_stat, 'dex': dex_stat, 'vit': vit_stat, 'int': int_stat}
        totals = compute_total_stats(base_stats, empty_stat_bonuses(), {})
        derived = compute_derived_stats(totals)

        character = {
            'id': self._generate_id('char'),
            'user_id': user_id,
            'slot': slot,
            'name': name,
            'class_id': class_id,
            'level': 1,
            'xp': 0,
            'hp_current': derived['hp_max'],
            'hp_max': derived['hp_max'],
            'mana_current': derived['mana_max'],
            'mana_max': derived['mana_max'],
            'str': str_stat,
            'dex': dex_stat,
            'vit': vit_stat,
            'int': int_stat,
            'stat_bonuses': empty_stat_bonuses(),
            'spheres': {},
            'corone': 0,
            'conditions': [],
            'echoes': {},
            'lore': {},
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        self.insert('characters', character)

        # Equipaggiamento iniziale (con gestione conflitto two-hand)
        occupied_slots = set()
        for eq_id in char_class.get('starting_equipment_ids', []):
            equipment = self.get_by_id('equipment', eq_id)
            if equipment:
                equip_tags = equipment.get('equip_tags', [])
                is_two_hand = 'two_hand' in equip_tags
                target_slot = None

                if is_two_hand:
                    if 'main_hand' not in occupied_slots:
                        target_slot = 'main_hand'
                        occupied_slots.add('main_hand')
                        occupied_slots.add('off_hand')  # Blocca off_hand
                else:
                    for tag in equip_tags:
                        if tag != 'two_hand' and tag not in occupied_slots:
                            target_slot = tag
                            occupied_slots.add(tag)
                            break

                if target_slot:
                    self.insert('character_equipment', {
                        'id': self._generate_id('ceq'),
                        'character_id': character['id'],
                        'equipment_id': eq_id,
                        'equipped_slot': target_slot
                    })
                else:
                    # Slot non disponibile: metti in inventario
                    self._db.add_to_inventory(character['id'], equipment['name'], 1)

        # Abilita' iniziale (cross-repo: skills)
        starting_tag = char_class.get('starting_ability_tag')
        if starting_tag:
            skill = self._db.get_skill_by_tag(starting_tag)
            if skill:
                self._db.add_character_skill(character['id'], skill['id'], mastery=1)
                if skill.get('parent_id'):
                    parent = self.get_by_id('skills', skill['parent_id'])
                    if parent:
                        self._db.add_character_skill(character['id'], parent['id'], mastery=1)

        return character

    def get_character_by_slot(self, slot: int) -> Optional[Dict]:
        """Ottieni personaggio per slot."""
        chars = self.get_where('characters', slot=slot)
        return chars[0] if chars else None

    def get_character_full(self, character_id: str) -> Optional[Dict]:
        """Ottieni personaggio con tutte le relazioni (JOIN simulato)."""
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

        # Inventario arricchito
        raw_inventory = self.get_where('inventory', character_id=character_id)
        char['inventory'] = []
        for inv_item in raw_inventory:
            eq_data = self._db.get_equipment_by_name(inv_item['item_name'])
            if eq_data:
                char['inventory'].append({
                    **inv_item,
                    'type': eq_data.get('type'),
                    'category': eq_data.get('category', 'equipment'),
                    'equip_tags': eq_data.get('equip_tags', []),
                    'rarity': eq_data.get('rarity', 'common'),
                    'description': eq_data.get('description'),
                    'stats_bonus': eq_data.get('stats_bonus', {}),
                    'item_level': eq_data.get('item_level', 1),
                    'damage_min': eq_data.get('damage_min', 0),
                    'damage_max': eq_data.get('damage_max', 0),
                    'armor_value': eq_data.get('armor_value', 0),
                    'sell_price': eq_data.get('sell_price', 0),
                    'weight': eq_data.get('weight', 1.0),
                    'use_effect': eq_data.get('use_effect'),
                    'requirements': eq_data.get('requirements', {})
                })
            else:
                char['inventory'].append(inv_item)

        # Stats calcolate
        base = {k: char.get(k, 10) for k in STAT_KEYS}
        bonuses = char.get('stat_bonuses', empty_stat_bonuses())
        eq_bonus = compute_equipment_bonuses(char['equipment'])
        totals = compute_total_stats(base, bonuses, eq_bonus)
        derived = compute_derived_stats(totals)

        conditions = char.get('conditions', [])
        derived = apply_condition_modifiers(derived, conditions)

        char['total_stats'] = totals
        char['derived'] = derived
        char['hp_max'] = derived['hp_max']
        char['mana_max'] = derived['mana_max']
        char['invest_points_available'] = compute_invest_points_available(
            char.get('level', 1), bonuses
        )
        char['xp_next'] = char.get('level', 1) * 100
        char['corone'] = char.get('corone', 0)

        # Two-hand lock status (cross-repo: equipment)
        char['two_hand_status'] = self._db.get_two_hand_status(character_id)

        return char

    def update_character_fields(self, character_id: str, changes: Dict) -> Optional[Dict]:
        """Aggiorna campi del personaggio con merge per dict nested."""
        char = self.get_by_id('characters', character_id)
        if not char:
            return None

        update = {}
        for key, value in changes.items():
            if isinstance(value, dict) and isinstance(char.get(key), dict):
                merged = {**char[key], **value}
                update[key] = merged
            else:
                update[key] = value

        update['updated_at'] = datetime.now().isoformat()
        return self.update('characters', character_id, update)

    def delete_character(self, character_id: str) -> bool:
        """Elimina personaggio e relazioni (CASCADE)."""
        self.delete_where('character_skills', character_id=character_id)
        self.delete_where('character_equipment', character_id=character_id)
        self.delete_where('character_quests', character_id=character_id)
        self.delete_where('inventory', character_id=character_id)
        self.delete_where('chat_history', character_id=character_id)
        return self.delete('characters', character_id)

    def get_character_by_slot_for_user(self, user_id: str, slot: int) -> Optional[Dict]:
        """Ottieni personaggio per slot e utente."""
        for c in self._cache.get('characters', []):
            if c.get('user_id') == user_id and c.get('slot') == slot:
                return c
        return None

    def get_all_slots_for_user(self, user_id: str) -> List[Dict]:
        """Ottieni tutti i personaggi di un utente."""
        return [c for c in self._cache.get('characters', [])
                if c.get('user_id') == user_id]

    def count_characters_for_user(self, user_id: str) -> int:
        """Conta personaggi di un utente."""
        return len(self.get_all_slots_for_user(user_id))
