"""
Applica azioni meccaniche al PlayerState.

Questo modulo connette le dataclass di statisfy-tags
allo stato del personaggio in Aethermoor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from statisfy_tags import (
    DamageAction,
    HealAction,
    NameAction,
    ClassAction,
    LevelAction,
    XPAction,
    ConditionAction,
    ConditionRemoveAction,
    ItemAction,
    ItemRemoveAction,
    SphereAction,
    ManaAction,
    SpellAction,
    EchoAction,
    BacklashAction,
    RollAction,
    NPCAction,
    LoreAction,
    CoroneAction,
    DamageTarget,
)

if TYPE_CHECKING:
    from ..player_state import PlayerStateManager

from ..mock_db import db


@dataclass
class MechanicalApplicator:
    """
    Applica azioni meccaniche dal parser al player state.

    Ogni metodo apply_* prende una dataclass immutabile
    e modifica lo stato del personaggio di conseguenza.

    I valori vengono cappati server-side in base al livello
    per prevenire exploit da prompt injection o valori anomali del GM.
    """

    # Cap per livello — il valore massimo è max(floor, level * multiplier)
    _CAP_DMG_MULT = 30
    _CAP_DMG_FLOOR = 50
    _CAP_XP_MULT = 25
    _CAP_XP_FLOOR = 50
    _CAP_CORONE_MULT = 50
    _CAP_CORONE_FLOOR = 100

    state_manager: "PlayerStateManager"
    character_id: str

    def __post_init__(self):
        self.state = self.state_manager.load_state(self.character_id)
        self._level = self.state.level if hasattr(self.state, 'level') else 1

    def _cap(self, value: int, multiplier: int, floor: int) -> int:
        """Limita un valore in base al livello del personaggio."""
        cap = max(floor, self._level * multiplier)
        return min(abs(value), cap)
    
    # ═══════════════════════════════════════════════════════════════
    # COMBAT & HEALTH
    # ═══════════════════════════════════════════════════════════════
    
    def apply_damage(self, action: DamageAction) -> dict:
        """Applica danni. Solo target=self modifica lo stato.
        Il valore viene cappato server-side in base al livello."""
        capped_amount = self._cap(
            action.amount, self._CAP_DMG_MULT, self._CAP_DMG_FLOOR
        )

        if action.target == DamageTarget.SELF:
            old_hp = self.state.stats.get("current_hp", 100)
            new_hp = max(0, old_hp - capped_amount)
            self.state.stats["current_hp"] = new_hp

            # Gestione backlash speciale
            if action.source == "backlash":
                self._add_condition("magical_exhaustion", "1_scene")

            return {
                "type": "damage",
                "amount": capped_amount,
                "damage_type": action.damage_type,
                "old_hp": old_hp,
                "new_hp": new_hp,
                "source": action.source,
                "capped": capped_amount != action.amount,
            }

        # Danni a nemici - log solo per analytics
        return {
            "type": "damage",
            "amount": capped_amount,
            "target": action.target.value,
        }
    
    def apply_heal(self, action: HealAction) -> dict:
        """Applica guarigione. Cap a hp_max derivato dal DB."""
        old_hp = self.state.stats.get("current_hp", 100)

        # Usa hp_max calcolato dalle stats derivate
        char = db.get_character_full(self.character_id)
        max_hp = char['derived']['hp_max'] if char and char.get('derived') else 100

        new_hp = min(max_hp, old_hp + action.amount)
        self.state.stats["current_hp"] = new_hp

        return {
            "type": "heal",
            "amount": action.amount,
            "old_hp": old_hp,
            "new_hp": new_hp,
            "hp_max": max_hp,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # CHARACTER IDENTITY
    # ═══════════════════════════════════════════════════════════════
    
    def apply_name(self, action: NameAction) -> dict:
        """Imposta nome personaggio."""
        old_name = self.state.name
        self.state.name = action.name
        return {"type": "name", "old": old_name, "new": action.name}
    
    def apply_class(self, action: ClassAction) -> dict:
        """Imposta classe personaggio."""
        old_class = getattr(self.state, "class_name", None)
        self.state.class_name = action.character_class
        return {"type": "class", "old": old_class, "new": action.character_class}
    
    def apply_level(self, action: LevelAction) -> dict:
        """Modifica livello."""
        old_level = self.state.level
        self.state.level = action.level
        return {"type": "level", "old": old_level, "new": action.level}
    
    def apply_xp(self, action: XPAction) -> dict:
        """Aggiunge esperienza con bonus INT e gestisce level-up.

        Level-up: soglia = 100 * livello_attuale.
        Ogni level-up concede +1 automatico a tutte le stats
        e 10 punti liberi da investire (via UI).
        Il valore XP viene cappato server-side.
        """
        from stats import STAT_KEYS, empty_stat_bonuses

        # Cap XP in base al livello
        capped_amount = self._cap(
            action.amount, self._CAP_XP_MULT, self._CAP_XP_FLOOR
        )

        old_xp = self.state.stats.get("xp", 0)
        old_level = self.state.level

        # Applica bonus XP da INT
        char = db.get_character_full(self.character_id)
        xp_bonus_pct = 0
        if char and char.get('derived'):
            xp_bonus_pct = char['derived'].get('xp_bonus', 0)

        effective_xp = int(capped_amount * (1 + xp_bonus_pct / 100))
        new_xp = old_xp + effective_xp

        # Level-up loop
        levels_gained = 0
        threshold = 100 * self.state.level
        while new_xp >= threshold:
            new_xp -= threshold
            self.state.level += 1
            levels_gained += 1
            threshold = 100 * self.state.level

        self.state.stats["xp"] = new_xp

        # Se c'e' stato level-up, aggiorna stat_bonuses e replenish HP/Mana
        hp_replenished = None
        mana_replenished = None

        if levels_gained > 0:
            raw_char = db.get_by_id('characters', self.character_id)
            bonuses = raw_char.get('stat_bonuses', empty_stat_bonuses()) if raw_char else empty_stat_bonuses()

            for stat in STAT_KEYS:
                bonuses['level_up'][stat] = bonuses['level_up'].get(stat, 0) + levels_gained

            db.update_character_fields(self.character_id, {'stat_bonuses': bonuses})

            # Replenish HP e Mana al massimo (Manwha hack)
            # Ricalcola stats con i nuovi bonus per ottenere hp_max/mana_max aggiornati
            char_fresh = db.get_character_full(self.character_id)
            if char_fresh:
                hp_replenished = char_fresh['hp_max']
                mana_replenished = char_fresh['mana_max']

                # Aggiorna PlayerState
                self.state.stats["current_hp"] = hp_replenished
                if "mana" not in self.state.stats:
                    self.state.stats["mana"] = {}
                self.state.stats["mana"] = {"base": mana_replenished}

                # Persisti replenish nel DB
                db.update_character_fields(self.character_id, {
                    'hp_current': hp_replenished,
                    'mana_current': mana_replenished,
                })

        result = {
            "type": "xp",
            "gained_raw": capped_amount,
            "gained_effective": effective_xp,
            "xp_bonus_pct": xp_bonus_pct,
            "old_xp": old_xp,
            "new_xp": new_xp,
            "old_level": old_level,
            "new_level": self.state.level,
            "levels_gained": levels_gained,
            "capped": capped_amount != action.amount,
        }

        if hp_replenished is not None:
            result["hp_replenished"] = hp_replenished
            result["mana_replenished"] = mana_replenished

        return result
    
    # ═══════════════════════════════════════════════════════════════
    # CONDITIONS
    # ═══════════════════════════════════════════════════════════════
    
    def _add_condition(self, name: str, duration: str | None = None):
        """Helper interno per aggiungere condition."""
        if "conditions" not in self.state.stats:
            self.state.stats["conditions"] = []
        
        # Evita duplicati
        existing = [c for c in self.state.stats["conditions"] if c["name"] == name]
        if not existing:
            self.state.stats["conditions"].append({
                "name": name,
                "duration": duration,
            })
    
    def apply_condition(self, action: ConditionAction) -> dict:
        """Aggiunge una condizione."""
        self._add_condition(action.condition_name, action.duration)
        return {
            "type": "condition_add",
            "condition": action.condition_name,
            "duration": action.duration,
        }
    
    def apply_condition_remove(self, action: ConditionRemoveAction) -> dict:
        """Rimuove una condizione."""
        if "conditions" in self.state.stats:
            before = len(self.state.stats["conditions"])
            self.state.stats["conditions"] = [
                c for c in self.state.stats["conditions"]
                if c["name"] != action.condition_name
            ]
            after = len(self.state.stats["conditions"])
            removed = before - after
        else:
            removed = 0
        
        return {
            "type": "condition_remove",
            "condition": action.condition_name,
            "removed": removed > 0,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # INVENTORY
    # ═══════════════════════════════════════════════════════════════
    
    def apply_item(self, action: ItemAction) -> dict:
        """Aggiunge oggetto all'inventario (PlayerState + MockDB)."""
        if hasattr(self.state, "add_item"):
            self.state.add_item(action.item_name)
        else:
            if "inventory" not in self.state.stats:
                self.state.stats["inventory"] = []
            self.state.stats["inventory"].append(action.item_name)

        # Sync a MockDB
        db.add_to_inventory(self.character_id, action.item_name, 1)

        return {"type": "item_add", "item": action.item_name}

    def apply_item_remove(self, action: ItemRemoveAction) -> dict:
        """Rimuove oggetto dall'inventario (PlayerState + MockDB)."""
        removed = False

        if hasattr(self.state, "remove_item"):
            removed = self.state.remove_item(action.item_name)
        elif "inventory" in self.state.stats:
            if action.item_name in self.state.stats["inventory"]:
                self.state.stats["inventory"].remove(action.item_name)
                removed = True

        # Sync a MockDB
        db.remove_from_inventory(self.character_id, action.item_name, 1)

        return {"type": "item_remove", "item": action.item_name, "removed": removed}

    # ═══════════════════════════════════════════════════════════════
    # ECONOMY
    # ═══════════════════════════════════════════════════════════════

    def apply_corone(self, action: CoroneAction) -> dict:
        """Modifica le corone del giocatore (PlayerState + MockDB).
        Il valore viene cappato server-side in base al livello."""
        if "corone" not in self.state.stats:
            self.state.stats["corone"] = 0

        # Cap il valore assoluto, preserva il segno
        capped_abs = self._cap(
            action.amount, self._CAP_CORONE_MULT, self._CAP_CORONE_FLOOR
        )
        capped_amount = capped_abs if action.amount >= 0 else -capped_abs

        old_corone = self.state.stats["corone"]
        new_corone = max(0, old_corone + capped_amount)
        self.state.stats["corone"] = new_corone

        # Sync diretto a MockDB
        db.update_character_fields(self.character_id, {"corone": new_corone})

        return {
            "type": "corone",
            "amount": capped_amount,
            "old_corone": old_corone,
            "new_corone": new_corone,
            "capped": capped_abs != abs(action.amount),
        }

    # ═══════════════════════════════════════════════════════════════
    # MAGIC SYSTEM - LE DIECI SFERE
    # ═══════════════════════════════════════════════════════════════
    
    def apply_sphere(self, action: SphereAction) -> dict:
        """Modifica affinità con una sfera."""
        if "spheres" not in self.state.stats:
            self.state.stats["spheres"] = {}
        
        current = self.state.stats["spheres"].get(action.sphere, 0)
        new_value = current + action.delta
        self.state.stats["spheres"][action.sphere] = new_value
        
        return {
            "type": "sphere",
            "sphere": action.sphere,
            "delta": action.delta,
            "old_value": current,
            "new_value": new_value,
        }
    
    def apply_mana(self, action: ManaAction) -> dict:
        """Consuma mana da una sfera."""
        if "mana" not in self.state.stats:
            self.state.stats["mana"] = {}
        
        # Default 10 mana per sfera
        current = self.state.stats["mana"].get(action.sphere, 10)
        new_value = max(0, current - action.cost)
        self.state.stats["mana"][action.sphere] = new_value
        
        return {
            "type": "mana",
            "sphere": action.sphere,
            "cost": action.cost,
            "old_value": current,
            "remaining": new_value,
        }
    
    def apply_spell(self, action: SpellAction) -> dict:
        """Registra esito incantesimo (per analytics)."""
        return {
            "type": "spell",
            "outcome": action.outcome.value,
            "effect": action.effect,
        }
    
    def apply_echo(self, action: EchoAction) -> dict:
        """Traccia risonanza con Progenitore."""
        if "echoes" not in self.state.stats:
            self.state.stats["echoes"] = {}
        
        # Converti intensità in valore numerico
        intensity_map = {"low": 1, "moderate": 2, "high": 3}
        intensity_value = intensity_map.get(action.intensity.value, 1)
        
        current = self.state.stats["echoes"].get(action.progenitor, 0)
        new_value = current + intensity_value
        self.state.stats["echoes"][action.progenitor] = new_value
        
        return {
            "type": "echo",
            "progenitor": action.progenitor,
            "intensity": action.intensity.value,
            "cumulative": new_value,
        }
    
    def apply_backlash(self, action: BacklashAction) -> dict:
        """Registra contraccolpo (effetti applicati via DMG/CONDITION)."""
        return {
            "type": "backlash",
            "backlash_type": action.backlash_type,
            "severity": action.severity.value,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # ROLLS & CHECKS
    # ═══════════════════════════════════════════════════════════════
    
    def apply_roll(self, action: RollAction) -> dict:
        """Registra esito di un check."""
        return {
            "type": "roll",
            "roll_type": action.roll_type,
            "result": action.result,
            "dc": action.dc,
            "success": action.success,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # NPC & LORE
    # ═══════════════════════════════════════════════════════════════
    
    def apply_npc(self, action: NPCAction) -> dict:
        """Registra interazione NPC."""
        # Nota: la disposition viene gestita da NPCDispositionAction (spaziale)
        return {
            "type": "npc_interaction",
            "npc": action.npc_name,
            "disposition": action.disposition.value,
        }
    
    def apply_lore(self, action: LoreAction) -> dict:
        """Sblocca conoscenza."""
        if "lore" not in self.state.stats:
            self.state.stats["lore"] = {}
        
        if action.category not in self.state.stats["lore"]:
            self.state.stats["lore"][action.category] = []
        
        # Evita duplicati
        if action.info not in self.state.stats["lore"][action.category]:
            self.state.stats["lore"][action.category].append(action.info)
        
        return {
            "type": "lore",
            "category": action.category,
            "info": action.info,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════
    
    def save(self):
        """Salva lo stato dopo tutte le modifiche."""
        self.state_manager.save_state(self.character_id)
