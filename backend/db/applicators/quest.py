"""
Applica azioni quest al PlayerState e MockDB.

Gestisce il ciclo di vita delle quest:
QUEST_START → QUEST_PROGRESS (0..N) → QUEST_COMPLETE | QUEST_FAIL

Per i reward, orchestra gli applicator meccanici esistenti
(apply_xp, apply_item) così da ereditare la logica di level-up,
Manwha hack, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from statisfy_tags import (
    QuestStartAction,
    QuestProgressAction,
    QuestCompleteAction,
    QuestFailAction,
    XPAction,
    ItemAction,
)

if TYPE_CHECKING:
    from ..player_state import PlayerStateManager

from ..mock_db import db
from .mechanical import MechanicalApplicator


@dataclass
class QuestApplicator:
    """
    Applica azioni quest dal parser al player/world state.

    Ogni quest è un'entity world-level (tabella `quests`)
    con relazione N:N verso characters (tabella `character_quests`).
    """

    state_manager: "PlayerStateManager"
    character_id: str

    def __post_init__(self):
        self.state = self.state_manager.load_state(self.character_id)

    # ═══════════════════════════════════════════════════════════════
    # QUEST START
    # ═══════════════════════════════════════════════════════════════

    def apply_quest_start(self, action: QuestStartAction) -> dict:
        """
        Crea la quest entity e la assegna al character corrente.

        1. Crea record in `quests` (world-level entity)
        2. Crea record in `character_quests` con status=active
        3. Inizializza objectives_progress
        """
        # Verifica se la quest esiste già (evita duplicati per nome)
        existing_quest = db.get_quest_by_name(action.quest_name)

        if existing_quest:
            quest_id = existing_quest['id']
            # Verifica che il character non l'abbia già attiva
            active = db.get_character_quest_by_name(
                self.character_id, action.quest_name, status='active'
            )
            if active:
                return {
                    "type": "quest_start",
                    "quest_name": action.quest_name,
                    "status": "already_active",
                    "quest_id": quest_id,
                }
        else:
            # Crea quest entity
            quest_id = db._generate_id('quest')
            quest_data = {
                'id': quest_id,
                'name': action.quest_name,
                'rarity': action.rarity.value,
                'scope': action.scope.value,
                'level': action.level,
                'objectives': [
                    {'description': obj, 'target': 1}
                    for obj in action.objectives
                ],
                'gold_range': list(action.gold_range) if action.gold_range else None,
                'xp_range': list(action.xp_range) if action.xp_range else None,
                'rep_range': list(action.rep_range) if action.rep_range else None,
                'created_by': self.character_id,
                'created_at': datetime.now().isoformat(),
            }
            db.insert('quests', quest_data)

        # Crea character_quest
        objectives_progress = [
            {'description': obj, 'current': 0, 'target': 1}
            for obj in action.objectives
        ]

        char_quest = {
            'id': db._generate_id('cq'),
            'character_id': self.character_id,
            'quest_id': quest_id,
            'status': 'active',
            'objectives_progress': objectives_progress,
            'rewards_received': {},
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
        }
        db.insert('character_quests', char_quest)

        return {
            "type": "quest_start",
            "quest_name": action.quest_name,
            "quest_id": quest_id,
            "rarity": action.rarity.value,
            "scope": action.scope.value,
            "objectives": list(action.objectives),
            "status": "created",
        }

    # ═══════════════════════════════════════════════════════════════
    # QUEST PROGRESS
    # ═══════════════════════════════════════════════════════════════

    def apply_quest_progress(self, action: QuestProgressAction) -> dict:
        """
        Aggiorna il progresso di un obiettivo nella quest.

        Matcha l'obiettivo per testo (case-insensitive).
        """
        cq = db.get_character_quest_by_name(
            self.character_id, action.quest_name, status='active'
        )
        if not cq:
            return {
                "type": "quest_progress",
                "quest_name": action.quest_name,
                "status": "quest_not_found",
            }

        # Aggiorna progress dell'obiettivo
        objectives = cq.get('objectives_progress', [])
        objective_found = False

        for obj in objectives:
            # Match per testo obiettivo (case-insensitive) o primo obiettivo se non specificato
            if (action.objective and
                    obj['description'].lower() == action.objective.lower()):
                obj['current'] = action.current
                obj['target'] = action.target
                objective_found = True
                break
            elif not action.objective and len(objectives) == 1:
                # Se non specificato e c'è un solo obiettivo, aggiorna quello
                obj['current'] = action.current
                obj['target'] = action.target
                objective_found = True
                break

        if not objective_found and action.objective:
            # Obiettivo non trovato — aggiungilo
            objectives.append({
                'description': action.objective,
                'current': action.current,
                'target': action.target,
            })

        # Salva aggiornamento
        db.update('character_quests', cq['id'], {
            'objectives_progress': objectives,
        })

        return {
            "type": "quest_progress",
            "quest_name": action.quest_name,
            "objective": action.objective,
            "current": action.current,
            "target": action.target,
            "status": "updated",
        }

    # ═══════════════════════════════════════════════════════════════
    # QUEST COMPLETE
    # ═══════════════════════════════════════════════════════════════

    def apply_quest_complete(self, action: QuestCompleteAction) -> dict:
        """
        Completa la quest e applica i reward.

        Orchestra gli applicator meccanici esistenti per:
        - XP → apply_xp (con bonus INT, level-up, Manwha hack)
        - Items → apply_item (PlayerState + MockDB)
        - Corone → incremento diretto su stats + DB
        - Reputazione → placeholder (futuro)
        """
        cq = db.get_character_quest_by_name(
            self.character_id, action.quest_name, status='active'
        )
        if not cq:
            return {
                "type": "quest_complete",
                "quest_name": action.quest_name,
                "status": "quest_not_found",
            }

        # Marca come completata
        db.update('character_quests', cq['id'], {
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
        })

        # ── Reward orchestration ─────────────────────────────────
        rewards_applied = {}
        reward_details = []

        mech = MechanicalApplicator(
            state_manager=self.state_manager,
            character_id=self.character_id,
        )

        # XP
        if action.xp and action.xp > 0:
            xp_result = mech.apply_xp(XPAction(amount=action.xp))
            rewards_applied['xp'] = action.xp
            reward_details.append(xp_result)

        # Items
        items_added = []
        for item_name in action.items:
            item_result = mech.apply_item(ItemAction(item_name=item_name))
            items_added.append(item_name)
            reward_details.append(item_result)
        if items_added:
            rewards_applied['items'] = items_added

        # Corone (gold)
        if action.gold and action.gold > 0:
            old_corone = self.state.stats.get("corone", 0)
            new_corone = old_corone + action.gold
            self.state.stats["corone"] = new_corone
            rewards_applied['corone'] = action.gold

            # Sync a MockDB
            db.update_character_fields(self.character_id, {'corone': new_corone})

            reward_details.append({
                "type": "corone",
                "amount": action.gold,
                "old": old_corone,
                "new": new_corone,
            })

        # Reputazione (placeholder)
        if action.reputation and action.reputation > 0:
            rewards_applied['reputation'] = action.reputation
            reward_details.append({
                "type": "reputation",
                "amount": action.reputation,
                "status": "noted",  # Sarà implementato con ReputationApplicator
            })

        # Salva rewards nel record quest
        db.update('character_quests', cq['id'], {
            'rewards_received': rewards_applied,
        })

        # Salva PlayerState
        mech.save()

        # Checkpoint automatico al completamento quest
        self.state.save_checkpoint()

        return {
            "type": "quest_complete",
            "quest_name": action.quest_name,
            "rewards": rewards_applied,
            "reward_details": reward_details,
            "status": "completed",
        }

    # ═══════════════════════════════════════════════════════════════
    # QUEST FAIL
    # ═══════════════════════════════════════════════════════════════

    def apply_quest_fail(self, action: QuestFailAction) -> dict:
        """
        Fallisce la quest e applica eventuali penalità.

        Penalità supportate: corone, xp, reputation.
        """
        cq = db.get_character_quest_by_name(
            self.character_id, action.quest_name, status='active'
        )
        if not cq:
            return {
                "type": "quest_fail",
                "quest_name": action.quest_name,
                "status": "quest_not_found",
            }

        # Marca come fallita
        db.update('character_quests', cq['id'], {
            'status': 'failed',
            'completed_at': datetime.now().isoformat(),
        })

        penalty_applied = {}

        if action.penalty_type and action.penalty_amount > 0:
            if action.penalty_type == "corone" or action.penalty_type == "gold":
                old_corone = self.state.stats.get("corone", 0)
                new_corone = max(0, old_corone - action.penalty_amount)
                self.state.stats["corone"] = new_corone
                db.update_character_fields(self.character_id, {'corone': new_corone})
                penalty_applied = {
                    "type": "corone",
                    "amount": action.penalty_amount,
                    "old": old_corone,
                    "new": new_corone,
                }
            elif action.penalty_type == "reputation":
                penalty_applied = {
                    "type": "reputation",
                    "amount": action.penalty_amount,
                    "status": "noted",
                }
            elif action.penalty_type == "xp":
                old_xp = self.state.stats.get("xp", 0)
                new_xp = max(0, old_xp - action.penalty_amount)
                self.state.stats["xp"] = new_xp
                penalty_applied = {
                    "type": "xp",
                    "amount": action.penalty_amount,
                    "old": old_xp,
                    "new": new_xp,
                }

        return {
            "type": "quest_fail",
            "quest_name": action.quest_name,
            "penalty": penalty_applied,
            "status": "failed",
        }

    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════

    def save(self):
        """Salva lo stato dopo tutte le modifiche."""
        self.state_manager.save_state(self.character_id)
