"""
Validazione e correzione dei tag meccanici generati dal GM.

Quando il GM usa tag tradizionali (es. [DMG: 15 fire | source: fireball]),
il validatore controlla che i numeri siano coerenti con le formule skill
e li corregge se la deviazione e' troppo alta.

Gestisce anche la validazione del mana.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from statisfy_tags import (
    DamageAction,
    ManaAction,
)

from .formula import FormulaEvaluator, FormulaError

if TYPE_CHECKING:
    from ..mock_db import MockDB
    from ..player_state import PlayerState


class ActionValidator:
    """Valida e corregge tag meccanici generati dal GM."""

    # Deviazione massima tollerata prima di correggere
    TOLERANCE_PCT = 0.25

    def __init__(self, character_id: str, db: "MockDB"):
        self.character_id = character_id
        self.db = db
        self._formula = FormulaEvaluator()

    def validate_damage(
        self, action: DamageAction
    ) -> tuple[DamageAction, str | None]:
        """
        Valida un DamageAction con campo source contro la formula skill.

        Se la deviazione dal valore calcolato supera TOLERANCE_PCT,
        crea un nuovo DamageAction con il valore corretto.

        Returns:
            (azione_possibilmente_corretta, warning_o_None)
        """
        if not action.source:
            return action, None

        # Cerca skill per tag
        skill = self.db.get_skill_by_tag(action.source)

        # Prova anche per nome (il GM potrebbe usare il nome italiano)
        if not skill:
            skill = self._find_skill_by_name(action.source)

        if not skill:
            return action, None  # Non validabile, pass-through

        effects = skill.get("effects", {})
        if "damage" not in effects:
            return action, None

        # Recupera mastery
        char_skills = self.db.get_where(
            "character_skills",
            character_id=self.character_id,
            skill_id=skill["id"],
        )
        mastery = char_skills[0].get("mastery", 1) if char_skills else 1

        # Recupera stats
        char_full = self.db.get_character_full(self.character_id)
        if not char_full:
            return action, None

        derived = char_full.get("derived", {})
        context = {
            "mastery": mastery,
            "level": char_full.get("level", 1),
            "str": char_full.get("total_stats", {}).get("str", 10),
            "dex": char_full.get("total_stats", {}).get("dex", 10),
            "vit": char_full.get("total_stats", {}).get("vit", 10),
            "int": char_full.get("total_stats", {}).get("int", 10),
        }

        try:
            expected = self._formula.evaluate(str(effects["damage"]), context)
        except FormulaError:
            return action, None

        # Moltiplicatore
        if skill.get("category") == "sphere":
            expected *= derived.get("magic_dmg_mult", 1.0)
        else:
            expected *= derived.get("phys_dmg_mult", 1.0)

        expected = max(1, int(expected))

        # Controlla tolleranza
        if expected == 0:
            return action, None

        deviation = abs(action.amount - expected) / expected
        if deviation > self.TOLERANCE_PCT:
            corrected = DamageAction(
                amount=expected,
                damage_type=action.damage_type,
                target=action.target,
                source=action.source,
            )
            warning = (
                f"DMG corretto: GM={action.amount}, "
                f"formula={expected} "
                f"(skill={skill['tag']}, mastery={mastery}, "
                f"dev={deviation:.0%})"
            )
            return corrected, warning

        return action, None

    def validate_mana(
        self, action: ManaAction, player_state: "PlayerState"
    ) -> tuple[bool, str | None]:
        """
        Controlla se il giocatore ha abbastanza mana nella sfera.

        Returns:
            (e_valido, messaggio_errore_o_None)
        """
        mana_pool = player_state.stats.get("mana", {})
        current = mana_pool.get(action.sphere, 0)

        if current < action.cost:
            return False, (
                f"Mana insufficiente: serve {action.cost} {action.sphere}, "
                f"disponibile {current}"
            )
        return True, None

    def _find_skill_by_name(self, name: str) -> dict | None:
        """Cerca skill per nome (matching case-insensitive)."""
        name_lower = name.lower().strip().replace("_", " ")

        for skill in self.db.get_all("skills"):
            if not isinstance(skill, dict):
                continue
            # Match per nome italiano
            if skill.get("name", "").lower() == name_lower:
                return skill
            # Match per tag normalizzato
            tag = skill.get("tag", "").lower().replace("_", " ")
            if tag == name_lower:
                return skill

        return None
