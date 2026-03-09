"""
Risolutore di tag di intento (CAST, ATTACK) in azioni concrete.

Trasforma tag leggeri generati dal GM in azioni meccaniche
precise calcolate dalle formule skill + stats del personaggio.

Esempio:
    CastAction("SPHERE_IGNIS_FIREBALL", target="enemy")
    → [ManaAction(cost=5, sphere="ignis"),
       DamageAction(amount=28, damage_type="fire", target=ENEMY),
       SpellAction(outcome=SUCCESS, effect="Palla di Fuoco")]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from statisfy_tags import (
    CastAction,
    AttackAction,
    DamageAction,
    HealAction,
    ManaAction,
    SpellAction,
    ConditionAction,
    DamageTarget,
    SpellOutcome,
)

from .formula import FormulaEvaluator, FormulaError

if TYPE_CHECKING:
    from ..mock_db import MockDB


class IntentResolver:
    """
    Risolve CastAction/AttackAction in sequenze di azioni concrete.

    Usa i dati skill dal DB + stats personaggio per calcolare
    valori precisi di danno, cura, costo mana.
    """

    def __init__(self, character_id: str, db: "MockDB"):
        self.character_id = character_id
        self.db = db
        self._formula = FormulaEvaluator()

    def resolve(self, action: Any) -> list:
        """
        Dispatch principale. Ritorna lista di azioni risolte.

        - CastAction → [ManaAction, DamageAction/HealAction, SpellAction, ...]
        - AttackAction → [DamageAction, ...]
        - Altro → [action] (pass-through)
        """
        match action:
            case CastAction():
                return self._resolve_cast(action)
            case AttackAction():
                return self._resolve_attack(action)
            case _:
                return [action]

    def _resolve_cast(self, action: CastAction) -> list:
        """
        Risolve un CastAction in azioni concrete.

        1. Cerca skill per tag nel DB
        2. Recupera mastery del personaggio
        3. Recupera stats derivate (magic_dmg_mult)
        4. Valuta formula danno/cura
        5. Genera: ManaAction + DamageAction/HealAction + SpellAction
        """
        skill = self.db.get_skill_by_tag(action.skill_tag)
        if not skill:
            # Skill sconosciuta - ritorna warning log
            return [SpellAction(
                outcome=SpellOutcome.FAIL,
                effect=f"skill_not_found:{action.skill_tag}",
            )]

        # Mastery del personaggio per questa skill
        mastery = self._get_mastery(skill["id"])

        # Stats complete del personaggio
        char_full = self.db.get_character_full(self.character_id)
        if not char_full:
            return [SpellAction(outcome=SpellOutcome.FAIL, effect="char_not_found")]

        derived = char_full.get("derived", {})
        total_stats = char_full.get("total_stats", {})

        # Contesto per valutazione formule
        context = {
            "mastery": mastery,
            "level": char_full.get("level", 1),
            "str": total_stats.get("str", 10),
            "dex": total_stats.get("dex", 10),
            "vit": total_stats.get("vit", 10),
            "int": total_stats.get("int", 10),
        }

        effects = skill.get("effects", {})
        resolved: list = []

        # ── 1. Costo mana ──
        mana_cost = skill.get("base_cost", 0)
        sphere = self._extract_sphere(skill)
        if mana_cost > 0:
            resolved.append(ManaAction(cost=mana_cost, sphere=sphere))

        # ── 2. Danno (se la skill ha formula danno) ──
        if "damage" in effects:
            try:
                raw_damage = self._formula.evaluate(
                    str(effects["damage"]), context
                )
            except FormulaError:
                raw_damage = 0

            # Moltiplicatore: magico per sphere, fisico per martial
            if skill.get("category") == "sphere":
                multiplier = derived.get("magic_dmg_mult", 1.0)
            else:
                multiplier = derived.get("phys_dmg_mult", 1.0)

            final_damage = max(1, int(raw_damage * multiplier))
            target = self._parse_target(action.target)

            resolved.append(DamageAction(
                amount=final_damage,
                damage_type=effects.get("type", "physical"),
                target=target,
                source=skill["tag"],
            ))

        # ── 3. Cura (se la skill ha formula cura) ──
        if "heal" in effects:
            try:
                heal_amount = self._formula.evaluate(
                    str(effects["heal"]), context
                )
            except FormulaError:
                heal_amount = 0

            resolved.append(HealAction(amount=max(1, int(heal_amount))))

        # ── 4. Condizione applicata (se la skill causa una condizione) ──
        if "condition" in effects:
            resolved.append(ConditionAction(
                condition_name=effects["condition"],
                duration=effects.get("condition_duration"),
            ))

        # ── 5. Esito spell ──
        resolved.append(SpellAction(
            outcome=SpellOutcome.SUCCESS,
            effect=skill.get("name", action.skill_tag),
        ))

        return resolved

    def _resolve_attack(self, action: AttackAction) -> list:
        """
        Risolve un AttackAction (skill martial/fisico).

        Stessa logica di _resolve_cast ma con phys_dmg_mult
        e senza costo mana per skill con base_cost == 0.
        """
        # Usa la stessa logica di cast, le differenze sono
        # gia' gestite dalla categoria skill (sphere vs martial)
        cast_equivalent = CastAction(
            skill_tag=action.skill_tag,
            target=action.target,
        )
        return self._resolve_cast(cast_equivalent)

    def _get_mastery(self, skill_id: str) -> int:
        """Recupera il livello di mastery del personaggio per una skill."""
        char_skills = self.db.get_where(
            "character_skills",
            character_id=self.character_id,
            skill_id=skill_id,
        )
        if char_skills:
            return char_skills[0].get("mastery", 1)
        return 1  # Default: mastery base

    @staticmethod
    def _extract_sphere(skill: dict) -> str:
        """
        Estrae il nome della sfera dal tag skill.

        SPHERE_IGNIS_FIREBALL → "ignis"
        SPHERE_AQUA_HEAL → "aqua"
        MARTIAL_SWORD_SLASH → "stamina" (fallback per skill non-sfera)
        """
        tag = skill.get("tag", "")
        parts = tag.upper().split("_")

        if len(parts) >= 2 and parts[0] == "SPHERE":
            return parts[1].lower()

        # Skill non-sfera: usa "stamina" come pseudo-risorsa
        return "stamina"

    @staticmethod
    def _parse_target(target_str: str) -> DamageTarget:
        """Converte stringa target in DamageTarget enum."""
        target_map = {
            "self": DamageTarget.SELF,
            "enemy": DamageTarget.ENEMY,
            "ally": DamageTarget.ALLY,
        }
        return target_map.get(target_str.lower().strip(), DamageTarget.ENEMY)
