"""
Rules Engine — Orchestratore principale.

Coordina risoluzione intent, validazione, tick condizioni
e rilevazione morte in un unico passaggio deterministico.

Flusso:
    parse_gm_response() → RulesEngine.process() → applicators
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from statisfy_tags import (
    CastAction,
    AttackAction,
    DamageAction,
    ManaAction,
    DamageTarget,
)

from .resolver import IntentResolver
from .validator import ActionValidator
from .conditions import ConditionTicker
from .death import DeathHandler, DeathEvent

if TYPE_CHECKING:
    from statisfy_tags import ParseResult
    from ..player_state import PlayerState
    from ..mock_db import MockDB


@dataclass
class ResolvedResult:
    """Output del rules engine dopo la risoluzione."""

    mechanical: list = field(default_factory=list)
    spatial: list = field(default_factory=list)
    quest: list = field(default_factory=list)
    death_event: DeathEvent | None = None
    expired_conditions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RulesEngine:
    """
    Motore di regole deterministico per Statisfy RPG.

    Si inserisce tra il parser statisfy-tags e gli applicators.
    Trasforma azioni di intento in azioni concrete e valida
    i tag generati dal GM.
    """

    def __init__(self, character_id: str, db: "MockDB"):
        self.character_id = character_id
        self.db = db
        self.resolver = IntentResolver(character_id, db)
        self.validator = ActionValidator(character_id, db)
        self.death_handler = DeathHandler()
        self.condition_ticker = ConditionTicker()

    def process(
        self,
        parse_result: "ParseResult",
        player_state: "PlayerState",
    ) -> ResolvedResult:
        """
        Processa le azioni parsate e ritorna azioni risolte.

        Steps:
            1. Tick condizioni (scade quelle vecchie)
            2. Risolvi intent (CAST/ATTACK → azioni concrete)
            3. Deduplicazione (evita doppio danno)
            4. Valida danni (correggi numeri GM)
            5. Valida mana (abbastanza mana?)
            6. Rileva morte (HP ≤ 0 dopo danno?)
        """
        result = ResolvedResult()

        # Spatial e quest passano attraverso senza modifiche
        result.spatial = list(parse_result.spatial)
        result.quest = list(parse_result.quest)

        # ── Step 1: Tick condizioni ──
        expired_actions, expired_names = self.condition_ticker.tick(
            player_state
        )
        result.expired_conditions = expired_names

        # Le ConditionRemoveAction vengono messe in testa alla lista meccanica
        resolved_mechanical: list = list(expired_actions)

        # ── Step 2: Risolvi intent tags ──
        # Traccia quali skill sono state risolte (per deduplicazione)
        resolved_skill_tags: set[str] = set()

        for action in parse_result.mechanical:
            match action:
                case CastAction(skill_tag=tag):
                    resolved_skill_tags.add(tag.upper())
                    resolved_actions = self.resolver.resolve(action)
                    resolved_mechanical.extend(resolved_actions)

                case AttackAction(skill_tag=tag):
                    resolved_skill_tags.add(tag.upper())
                    resolved_actions = self.resolver.resolve(action)
                    resolved_mechanical.extend(resolved_actions)

                case _:
                    resolved_mechanical.append(action)

        # ── Step 3: Deduplicazione ──
        # Se il GM ha usato sia [CAST: X] che [DMG: Y | source: X],
        # rimuovi il DMG duplicato
        if resolved_skill_tags:
            resolved_mechanical = self._deduplicate(
                resolved_mechanical, resolved_skill_tags
            )

        # ── Step 4: Valida danni con source ──
        validated_mechanical: list = []
        for action in resolved_mechanical:
            if isinstance(action, DamageAction) and action.source:
                # Se questa action e' stata generata dal resolver,
                # non rivalidarla (e' gia' corretta)
                source_upper = action.source.upper()
                if source_upper not in resolved_skill_tags:
                    action, warning = self.validator.validate_damage(action)
                    if warning:
                        result.warnings.append(warning)
            validated_mechanical.append(action)

        # ── Step 5: Valida mana ──
        final_mechanical = self._validate_mana_groups(
            validated_mechanical, player_state, result
        )

        # ── Step 6: Rileva morte ──
        total_dmg_to_self = sum(
            a.amount
            for a in final_mechanical
            if isinstance(a, DamageAction) and a.target == DamageTarget.SELF
        )

        if total_dmg_to_self > 0:
            if self.death_handler.check_death(player_state, total_dmg_to_self):
                death_event = self.death_handler.handle_death(player_state)
                result.death_event = death_event

                # Azzera XP direttamente (apply_xp aggiunge, non setta)
                player_state.stats["xp"] = 0

        result.mechanical = final_mechanical
        return result

    def _deduplicate(
        self, actions: list, resolved_tags: set[str]
    ) -> list:
        """
        Rimuovi DamageAction/ManaAction/SpellAction con source che
        corrisponde a un tag gia' risolto da un CastAction/AttackAction.

        Evita doppio danno quando il GM scrive sia il tag intent
        che i tag risolti per la stessa skill.
        """
        deduplicated: list = []
        for action in actions:
            if isinstance(action, DamageAction) and action.source:
                if action.source.upper() in resolved_tags:
                    # Controlla se e' un duplicato dal GM (non dal resolver).
                    # Le azioni dal resolver sono gia' nella lista resolved_tags,
                    # ma hanno source impostato dal resolver stesso.
                    # Teniamo solo la prima occorrenza per ogni source.
                    # Contiamo quante ne abbiamo gia'
                    existing = [
                        a for a in deduplicated
                        if isinstance(a, DamageAction)
                        and a.source
                        and a.source.upper() == action.source.upper()
                    ]
                    if existing:
                        continue  # Duplicato, skip

            deduplicated.append(action)

        return deduplicated

    def _validate_mana_groups(
        self,
        actions: list,
        player_state: "PlayerState",
        result: ResolvedResult,
    ) -> list:
        """
        Valida mana per ogni ManaAction.

        Se il mana e' insufficiente, rimuove l'intera sequenza
        di azioni associate alla stessa skill (ManaAction +
        DamageAction/HealAction + SpellAction con stesso source).
        """
        # Prima passa: identifica ManaAction con mana insufficiente
        insufficient_spheres: set[str] = set()

        for action in actions:
            if isinstance(action, ManaAction):
                valid, error = self.validator.validate_mana(
                    action, player_state
                )
                if not valid:
                    insufficient_spheres.add(action.sphere)
                    if error:
                        result.warnings.append(error)

        if not insufficient_spheres:
            return actions

        # Seconda passa: rimuovi azioni collegate a sfere con mana insufficiente
        filtered: list = []
        for action in actions:
            if isinstance(action, ManaAction):
                if action.sphere in insufficient_spheres:
                    continue

            if isinstance(action, DamageAction) and action.source:
                # Controlla se la skill e' di una sfera insufficiente
                skill = self.db.get_skill_by_tag(action.source)
                if skill:
                    tag = skill.get("tag", "")
                    parts = tag.upper().split("_")
                    if len(parts) >= 2 and parts[0] == "SPHERE":
                        sphere = parts[1].lower()
                        if sphere in insufficient_spheres:
                            continue

            filtered.append(action)

        return filtered
