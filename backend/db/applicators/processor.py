"""
Processore principale per risposte GM.

Questo modulo è il punto d'ingresso per processare le risposte
del Game Master, estraendo e applicando tutti i tag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from statisfy_tags import (
    parse_gm_response,
    strip_all_tags,
    ParseResult,
    # Mechanical
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
    CastAction,
    AttackAction,
    RollAction,
    NPCAction,
    LoreAction,
    CoroneAction,
    # Spatial
    MoveAction,
    EnterAction,
    ExitAction,
    CreateSublocationAction,
    LocationCreateAction,
    EdgeCreateAction,
    EdgeModifyAction,
    LocationUpdateAction,
    NPCDispositionAction,
    # Quest
    QuestStartAction,
    QuestProgressAction,
    QuestCompleteAction,
    QuestFailAction,
    # Progression
    TitleAction,
    TitleRemoveAction,
    ReputationAction,
    SkillAction,
    SkillEvolveAction,
    MasteryAction,
    StatUnlockAction,
)

from .mechanical import MechanicalApplicator
from .spatial import SpatialApplicator
from .quest import QuestApplicator
from ..player_state import get_player_state_manager
from ..world_manager import get_world_manager
from ..mock_db import db
from ..rules_engine import RulesEngine


@dataclass
class ProcessingReport:
    """
    Report del processing di una risposta GM.
    
    Contiene il testo pulito e tutti i risultati
    delle azioni applicate.
    """
    clean_text: str
    mechanical_applied: list = field(default_factory=list)
    spatial_applied: list = field(default_factory=list)
    quest_applied: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    death_event: dict | None = None
    expired_conditions: list = field(default_factory=list)
    rules_warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Converte in dict per JSON response."""
        # Calcola alias per compatibilità con frontend esistente
        movements = [
            a for a in self.spatial_applied
            if a.get("type") in ("move", "enter", "exit") and a.get("success", True)
        ]
        locations_created = [
            a for a in self.spatial_applied
            if a.get("type") == "create_sublocation" and a.get("success", True)
        ]
        modifications = [
            a for a in self.spatial_applied
            if a.get("type") == "npc_disposition"
        ]

        return {
            "clean_text": self.clean_text,
            "mechanical_applied": self.mechanical_applied,
            "spatial_applied": self.spatial_applied,
            "quest_applied": self.quest_applied,
            "errors": self.errors,
            # Alias per compatibilità con frontend esistente
            "movements": movements,
            "locations_created": locations_created,
            "modifications": modifications,
            # Rules Engine
            "death": self.death_event,
            "expired_conditions": self.expired_conditions,
            "rules_warnings": self.rules_warnings,
            # Statistiche
            "action_count": len(self.mechanical_applied) + len(self.spatial_applied) + len(self.quest_applied),
            "error_count": len(self.errors),
        }
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class GMResponseProcessor:
    """
    Processore principale per risposte del Game Master.
    
    Sostituisce le funzioni in world_parser.py e location_parser.py.
    
    Usage:
        processor = GMResponseProcessor("character_123")
        report = processor.process(gm_response_text)
        
        # Per display
        display(report.clean_text)
        
        # Per debug
        print(report.to_dict())
    """
    
    def __init__(self, character_id: str):
        self.character_id = character_id
        self.state_manager = get_player_state_manager()
        self.world_manager = get_world_manager()
    
    def process(self, gm_response: str) -> ProcessingReport:
        """
        Processa una risposta del GM.

        1. Parsa tutti i tag usando statisfy-tags
        2. Rules Engine: tick condizioni, risolvi intent, valida, rileva morte
        3. Applica azioni risolte al player state
        4. Gestisce evento morte (penalita' + respawn)
        5. Salva stati e sync a MockDB

        Args:
            gm_response: Testo completo della risposta GM con tag inline

        Returns:
            ProcessingReport con testo pulito e risultati applicazione
        """
        # Step 1: Parse usando la libreria
        result = parse_gm_response(gm_response)

        # Prepara report
        report = ProcessingReport(clean_text=result.clean_text)

        # Step 2: Rules Engine — risolvi, valida, tick condizioni, rileva morte
        rules_engine = RulesEngine(self.character_id, db)
        player_state = self.state_manager.load_state(self.character_id)
        resolved = rules_engine.process(result, player_state)

        # Riporta warnings e condizioni scadute
        report.rules_warnings = resolved.warnings
        report.expired_conditions = resolved.expired_conditions

        # Step 3: Applica azioni meccaniche RISOLTE
        mech_applicator = MechanicalApplicator(
            state_manager=self.state_manager,
            character_id=self.character_id,
        )

        for action in resolved.mechanical:
            try:
                applied = self._apply_mechanical(mech_applicator, action)
                report.mechanical_applied.append(applied)
            except Exception as e:
                tag_name = getattr(action, "tag_name", type(action).__name__)
                report.errors.append({
                    "tag": tag_name,
                    "error": str(e),
                    "action": repr(action),
                })

        # Step 4: Gestisci evento morte
        if resolved.death_event:
            death = resolved.death_event

            # Applica azioni penalita' (LevelAction, ConditionAction, HealAction)
            for penalty_action in death.penalty_actions:
                try:
                    applied = self._apply_mechanical(mech_applicator, penalty_action)
                    report.mechanical_applied.append(applied)
                except Exception as e:
                    tag_name = getattr(penalty_action, "tag_name", "DEATH_PENALTY")
                    report.errors.append({
                        "tag": tag_name,
                        "error": str(e),
                    })

            # Respawn: sposta al checkpoint
            respawn = death.respawn_location
            if respawn:
                try:
                    self.state_manager.move_player(
                        self.character_id,
                        region_id=respawn.get("region_id", ""),
                        zone_id=respawn.get("zone_id", ""),
                        location_id=respawn.get("location_id", ""),
                        sublocation_id=respawn.get("sublocation_id", ""),
                    )
                except Exception as e:
                    report.errors.append({
                        "tag": "RESPAWN",
                        "error": f"Errore respawn: {str(e)}",
                    })

            report.death_event = death.to_dict()

        # Step 5: Applica azioni spaziali (invariato)
        spatial_applicator = SpatialApplicator(
            world_manager=self.world_manager,
            state_manager=self.state_manager,
            character_id=self.character_id,
        )

        for action in resolved.spatial:
            try:
                applied = self._apply_spatial(spatial_applicator, action)
                report.spatial_applied.append(applied)
            except Exception as e:
                report.errors.append({
                    "tag": action.tag_name,
                    "error": str(e),
                    "action": repr(action),
                })

        # Step 6: Applica azioni quest (invariato)
        quest_applicator = QuestApplicator(
            state_manager=self.state_manager,
            character_id=self.character_id,
        )

        for action in resolved.quest:
            try:
                applied = self._apply_quest(quest_applicator, action)
                report.quest_applied.append(applied)
            except Exception as e:
                report.errors.append({
                    "tag": action.tag_name,
                    "error": str(e),
                    "action": repr(action),
                })

        # Step 7: Salva stati (PlayerState files)
        try:
            mech_applicator.save()
            spatial_applicator.save()
            quest_applicator.save()
        except Exception as e:
            report.errors.append({
                "tag": "SAVE",
                "error": f"Errore salvataggio stato: {str(e)}",
            })

        # Step 8: Sync cambiamenti a MockDB (source of truth)
        try:
            self._sync_to_mock_db(mech_applicator)
        except Exception as e:
            report.errors.append({
                "tag": "SYNC_DB",
                "error": f"Errore sync MockDB: {str(e)}",
            })

        return report

    def _sync_to_mock_db(self, mech_applicator: MechanicalApplicator):
        """Sincronizza le modifiche dal PlayerState al MockDB."""
        state = mech_applicator.state
        stats = state.stats

        changes = {}

        # HP
        if "current_hp" in stats:
            changes["hp_current"] = stats["current_hp"]

        # Mana totale (somma dei mana per sfera)
        if "mana" in stats:
            total_mana = sum(stats["mana"].values())
            changes["mana_current"] = total_mana

        # XP e livello
        if "xp" in stats:
            changes["xp"] = stats["xp"]
        if hasattr(state, "level"):
            changes["level"] = state.level

        # Corone
        if "corone" in stats:
            changes["corone"] = stats["corone"]

        # Condizioni, sfere, echoes, lore
        if "conditions" in stats:
            changes["conditions"] = stats["conditions"]
        if "spheres" in stats:
            changes["spheres"] = stats["spheres"]
        if "echoes" in stats:
            changes["echoes"] = stats["echoes"]
        if "lore" in stats:
            changes["lore"] = stats["lore"]

        if changes:
            db.update_character_fields(self.character_id, changes)
    
    def _apply_mechanical(self, applicator: MechanicalApplicator, action: Any) -> dict:
        """Dispatch azione meccanica al metodo corretto."""
        match action:
            case DamageAction():
                return applicator.apply_damage(action)
            case HealAction():
                return applicator.apply_heal(action)
            case NameAction():
                return applicator.apply_name(action)
            case ClassAction():
                return applicator.apply_class(action)
            case LevelAction():
                return applicator.apply_level(action)
            case XPAction():
                return applicator.apply_xp(action)
            case ConditionAction():
                return applicator.apply_condition(action)
            case ConditionRemoveAction():
                return applicator.apply_condition_remove(action)
            case ItemAction():
                return applicator.apply_item(action)
            case ItemRemoveAction():
                return applicator.apply_item_remove(action)
            case SphereAction():
                return applicator.apply_sphere(action)
            case ManaAction():
                return applicator.apply_mana(action)
            case SpellAction():
                return applicator.apply_spell(action)
            case EchoAction():
                return applicator.apply_echo(action)
            case BacklashAction():
                return applicator.apply_backlash(action)
            case RollAction():
                return applicator.apply_roll(action)
            case NPCAction():
                return applicator.apply_npc(action)
            case LoreAction():
                return applicator.apply_lore(action)
            case CoroneAction():
                return applicator.apply_corone(action)
            # ── Intent (safety net - normalmente risolti dal Rules Engine) ──
            case CastAction():
                return {"type": "cast", "skill": action.skill_tag, "target": action.target, "status": "unresolved_passthrough"}
            case AttackAction():
                return {"type": "attack", "skill": action.skill_tag, "target": action.target, "status": "unresolved_passthrough"}
            # ── Progression (placeholder) ──────────────────────────
            case TitleAction():
                return {"type": "title", "title": action.title_name, "rarity": action.rarity.value, "status": "not_implemented"}
            case TitleRemoveAction():
                return {"type": "title_remove", "title": action.title_name, "status": "not_implemented"}
            case ReputationAction():
                return {"type": "reputation", "target": action.target, "amount": action.amount, "status": "not_implemented"}
            case SkillAction():
                return {"type": "skill", "skill": action.skill_name, "method": action.method.value, "status": "not_implemented"}
            case SkillEvolveAction():
                return {"type": "skill_evolve", "skill": action.skill_name, "into": action.into, "status": "not_implemented"}
            case MasteryAction():
                return {"type": "mastery", "skill": action.skill_name, "grade": action.grade, "status": "not_implemented"}
            case StatUnlockAction():
                return {"type": "stat_unlock", "stat": action.stat_name, "category": action.category.value, "status": "not_implemented"}
            case _:
                return {"type": "unknown", "action": repr(action)}

    def _apply_quest(self, applicator: QuestApplicator, action: Any) -> dict:
        """Dispatch azione quest al metodo corretto."""
        match action:
            case QuestStartAction():
                return applicator.apply_quest_start(action)
            case QuestProgressAction():
                return applicator.apply_quest_progress(action)
            case QuestCompleteAction():
                return applicator.apply_quest_complete(action)
            case QuestFailAction():
                return applicator.apply_quest_fail(action)
            case _:
                return {"type": "unknown_quest", "action": repr(action)}

    def _apply_spatial(self, applicator: SpatialApplicator, action: Any) -> dict:
        """Dispatch azione spaziale al metodo corretto."""
        match action:
            case MoveAction():
                return applicator.apply_move(action)
            case EnterAction():
                return applicator.apply_enter(action)
            case ExitAction():
                return applicator.apply_exit(action)
            case CreateSublocationAction():
                return applicator.apply_create_sublocation(action)
            case LocationCreateAction():
                return applicator.apply_location_create(action)
            case EdgeCreateAction():
                return applicator.apply_edge_create(action)
            case EdgeModifyAction():
                return applicator.apply_edge_modify(action)
            case LocationUpdateAction():
                return applicator.apply_location_update(action)
            case NPCDispositionAction():
                return applicator.apply_npc_disposition(action)
            case _:
                return {"type": "unknown", "action": repr(action)}


# ═══════════════════════════════════════════════════════════════════════════════
# FUNZIONI DI COMPATIBILITÀ (drop-in replacement)
# ═══════════════════════════════════════════════════════════════════════════════

def process_gm_response(character_id: str, gm_response: str) -> dict:
    """
    Drop-in replacement per world_parser.process_gm_response()
    
    Mantiene la stessa firma e formato di output per compatibilità
    con il codice esistente.
    """
    processor = GMResponseProcessor(character_id)
    report = processor.process(gm_response)
    return report.to_dict()


def strip_gm_tags(text: str) -> str:
    """
    Drop-in replacement per world_parser.strip_gm_tags()
    
    Usa la funzione della libreria statisfy-tags.
    """
    return strip_all_tags(text)
