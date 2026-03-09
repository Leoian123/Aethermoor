"""
Sistema di morte e respawn.

Gestisce la rilevazione della morte (HP <= 0), il calcolo
delle penalita' secondo il design doc, e il respawn al
checkpoint.

Regole dal design doc:
- Morte: HP raggiunge 0
- Penalita': new_level = floor(level - 1.5)
- Malus: -10% tutte stats per 60 tick (~1 ora)
- Protezione newbie: level 1-2 immuni
- Equipaggiamento intatto
- Respawn ultimo checkpoint
- Recovery: +50% EXP bonus per 30 tick
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from statisfy_tags import (
    LevelAction,
    ConditionAction,
    HealAction,
)

if TYPE_CHECKING:
    from ..player_state import PlayerState


@dataclass
class DeathEvent:
    """Rappresenta una morte e le sue conseguenze."""

    old_level: int
    new_level: int
    level_loss: int
    xp_lost: int
    respawn_location: dict[str, str]
    is_newbie: bool
    penalty_actions: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "death",
            "old_level": self.old_level,
            "new_level": self.new_level,
            "level_loss": self.level_loss,
            "xp_lost": self.xp_lost,
            "respawn": self.respawn_location,
            "is_newbie": self.is_newbie,
        }


# Spawn di default (Albachiara piazza)
_DEFAULT_SPAWN = {
    "region_id": "valeria",
    "zone_id": "lumengarde",
    "location_id": "albachiara",
    "sublocation_id": "albachiara.piazza",
}

NEWBIE_MAX_LEVEL = 2
DEATH_MALUS_DURATION = "60"       # tick (~1 ora)
RECOVERY_BONUS_DURATION = "30"    # tick (~30 min)


class DeathHandler:
    """Gestisce morte, penalita' e respawn."""

    def check_death(
        self,
        player_state: "PlayerState",
        total_damage_to_self: int,
    ) -> bool:
        """Controlla se il danno in arrivo uccide il personaggio."""
        current_hp = player_state.stats.get("current_hp", 1)
        return (current_hp - total_damage_to_self) <= 0

    def handle_death(self, player_state: "PlayerState") -> DeathEvent:
        """
        Calcola penalita' di morte e genera azioni per il respawn.

        Dalla tabella del design doc:
            Lv 47 → 45 (loss 2)
            Lv 50 → 48 (loss 2)
            Lv 1-2 → invariato (protezione newbie)
        """
        old_level = player_state.level
        xp_lost = player_state.stats.get("xp", 0)
        respawn = self._get_last_checkpoint(player_state)

        # ── Protezione newbie ──
        if old_level <= NEWBIE_MAX_LEVEL:
            return DeathEvent(
                old_level=old_level,
                new_level=old_level,
                level_loss=0,
                xp_lost=0,
                respawn_location=respawn,
                is_newbie=True,
                penalty_actions=[
                    HealAction(amount=99999),  # Cap a hp_max dall'applicator
                ],
            )

        # ── Penalita' standard ──
        # floor(level - 1.5): Lv47 → 45, Lv50 → 48, Lv10 → 8
        new_level = max(1, math.floor(old_level - 1.5))
        level_loss = old_level - new_level

        penalty_actions = [
            # Riduce livello
            LevelAction(level=new_level),
            # Malus -10% stats (gestito da apply_condition_modifiers in stats.py)
            ConditionAction(
                condition_name="death_malus",
                duration=DEATH_MALUS_DURATION,
            ),
            # Bonus recovery +50% EXP
            ConditionAction(
                condition_name="death_recovery_bonus",
                duration=RECOVERY_BONUS_DURATION,
            ),
            # Full heal al respawn
            HealAction(amount=99999),
        ]

        return DeathEvent(
            old_level=old_level,
            new_level=new_level,
            level_loss=level_loss,
            xp_lost=xp_lost,
            respawn_location=respawn,
            is_newbie=False,
            penalty_actions=penalty_actions,
        )

    @staticmethod
    def _get_last_checkpoint(player_state: "PlayerState") -> dict[str, str]:
        """
        Recupera l'ultimo checkpoint salvato.

        Cerca in state.flags["checkpoints"] (LIFO).
        Fallback: spawn di default (Albachiara).
        """
        checkpoints = player_state.flags.get("checkpoints", [])
        if checkpoints:
            return dict(checkpoints[-1])  # Copia
        return dict(_DEFAULT_SPAWN)
