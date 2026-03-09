"""
Applica azioni spaziali al WorldManager.

Questo modulo connette le dataclass di statisfy-tags
al sistema di mondo gerarchico di Aethermoor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from statisfy_tags import (
    MoveAction,
    EnterAction,
    ExitAction,
    CreateSublocationAction,
    LocationCreateAction,
    EdgeCreateAction,
    EdgeModifyAction,
    LocationUpdateAction,
    NPCDispositionAction,
    MoveType,
)

if TYPE_CHECKING:
    from ..world_manager import WorldManager
    from ..player_state import PlayerStateManager


@dataclass
class SpatialApplicator:
    """
    Applica azioni spaziali dal parser al world state.
    
    Gestisce movimento, creazione sublocation procedurali,
    e modifiche alle disposizioni NPC.
    """
    
    world_manager: "WorldManager"
    state_manager: "PlayerStateManager"
    character_id: str
    
    def __post_init__(self):
        self.state = self.state_manager.load_state(self.character_id)
    
    # ═══════════════════════════════════════════════════════════════
    # MOVEMENT
    # ═══════════════════════════════════════════════════════════════
    
    def apply_move(self, action: MoveAction) -> dict:
        """
        Movimento a sublocation esistente nella stessa location.
        
        Valida che la destinazione esista e sia raggiungibile.
        """
        # Valida movimento contro il world manager
        valid, error = self._validate_movement(action.destination)
        
        if not valid:
            return {
                "type": "move",
                "success": False,
                "error": error,
                "destination": action.destination,
            }
        
        # Esegui movimento
        old_location = self.state.position.sublocation_id
        self.state.position.sublocation_id = action.destination

        # Checkpoint automatico ad ogni cambio location
        self.state.save_checkpoint()

        return {
            "type": "move",
            "success": True,
            "from": old_location,
            "to": action.destination,
        }
    
    def apply_enter(self, action: EnterAction) -> dict:
        """
        Entra in una sublocation figlia (più profonda nella gerarchia).
        
        La destinazione deve essere figlia diretta o indiretta
        della posizione corrente.
        """
        current = self.state.position.sublocation_id
        
        # Valida che la destinazione sia figlia
        if not action.destination.startswith(current + "."):
            return {
                "type": "enter",
                "success": False,
                "error": f"'{action.destination}' non è figlia di '{current}'",
                "destination": action.destination,
            }
        
        # Valida esistenza (se procedurale, deve essere già stata creata)
        exists = self._sublocation_exists(action.destination)
        if not exists:
            return {
                "type": "enter",
                "success": False,
                "error": f"Sublocation '{action.destination}' non esiste",
                "destination": action.destination,
            }
        
        old_location = current
        self.state.position.sublocation_id = action.destination
        
        return {
            "type": "enter",
            "success": True,
            "from": old_location,
            "to": action.destination,
        }
    
    def apply_exit(self, action: ExitAction) -> dict:
        """
        Torna al parent nella gerarchia spaziale.
        
        Se già al livello della location, non fa nulla.
        """
        current = self.state.position.sublocation_id
        parts = current.split(".")
        
        if len(parts) <= 1:
            return {
                "type": "exit",
                "success": False,
                "error": "Già al livello più alto della location",
                "current": current,
            }
        
        parent = ".".join(parts[:-1])
        self.state.position.sublocation_id = parent
        
        return {
            "type": "exit",
            "success": True,
            "from": current,
            "to": parent,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # LOCATION CREATION (procedurale)
    # ═══════════════════════════════════════════════════════════════
    
    def apply_create_sublocation(self, action: CreateSublocationAction) -> dict:
        """
        Crea una sublocation procedurale.
        
        L'ID deve iniziare con l'ID della location corrente.
        La sublocation viene salvata nello stato del personaggio.
        """
        current_location = self.state.position.location_id
        
        # Valida che l'ID inizi con la location corrente
        if not action.id.startswith(current_location + "."):
            return {
                "type": "create_sublocation",
                "success": False,
                "error": f"ID deve iniziare con '{current_location}.'",
                "attempted_id": action.id,
            }
        
        # Verifica che non esista già
        if self._sublocation_exists(action.id):
            return {
                "type": "create_sublocation",
                "success": False,
                "error": f"Sublocation '{action.id}' esiste già",
                "id": action.id,
            }
        
        # Determina parent
        parts = action.id.split(".")
        if len(parts) == 2:
            parent_id = current_location
        else:
            parent_id = ".".join(parts[:-1])
        
        # Crea struttura sublocation
        subloc_data = {
            "id": action.id,
            "parent_id": parent_id,
            "name": action.name,
            "description": action.description,
            "type": action.location_type.value,
            "tags": list(action.tags),
            "exits": {parent_id: f"torna a {parent_id.split('.')[-1]}"},
            "npcs_here": [],
            "children": [],
            "_procedural": True,
        }
        
        # Salva nel player state
        self.state.add_procedural_sublocation(action.id, subloc_data)
        
        # Aggiungi come figlio al parent se è una sublocation procedurale
        if parent_id != current_location:
            parent_subloc = self._get_procedural_sublocation(parent_id)
            if parent_subloc:
                if "children" not in parent_subloc:
                    parent_subloc["children"] = []
                if action.id not in parent_subloc["children"]:
                    parent_subloc["children"].append(action.id)
        
        return {
            "type": "create_sublocation",
            "success": True,
            "id": action.id,
            "name": action.name,
            "parent": parent_id,
            "location_type": action.location_type.value,
        }
    
    def apply_location_create(self, action: LocationCreateAction) -> dict:
        """
        Crea location nel grafo (legacy, usato da location_parser).
        
        Per ora ritorna solo log, la creazione di location
        vere richiede modifiche al seed o al grafo.
        """
        # TODO: Implementare se necessario per grafo dinamico
        return {
            "type": "location_create",
            "success": False,
            "error": "Creazione location non supportata (usa create_sublocation)",
            "id": action.id,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # EDGE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    def apply_edge_create(self, action: EdgeCreateAction) -> dict:
        """Crea collegamento tra location (legacy)."""
        # TODO: Implementare se necessario
        return {
            "type": "edge_create",
            "success": False,
            "error": "Edge creation non implementato",
            "from": action.from_id,
            "to": action.to_id,
        }
    
    def apply_edge_modify(self, action: EdgeModifyAction) -> dict:
        """Modifica stato edge (lock/unlock/reveal/hide)."""
        # TODO: Implementare se necessario
        return {
            "type": f"edge_{action.modification}",
            "success": False,
            "error": "Edge modification non implementato",
            "from": action.from_id,
            "to": action.to_id,
        }
    
    def apply_location_update(self, action: LocationUpdateAction) -> dict:
        """Aggiorna tag di una location."""
        # TODO: Implementare se necessario
        return {
            "type": "location_update",
            "success": False,
            "error": "Location update non implementato",
            "id": action.id,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # NPC DISPOSITION
    # ═══════════════════════════════════════════════════════════════
    
    def apply_npc_disposition(self, action: NPCDispositionAction) -> dict:
        """
        Modifica la disposizione di un NPC.
        
        La disposizione viene salvata nel player state.
        """
        old_value = self.state.get_npc_disposition(action.npc_id)
        self.state.set_npc_disposition(action.npc_id, action.value)
        
        return {
            "type": "npc_disposition",
            "npc_id": action.npc_id,
            "old_value": old_value,
            "new_value": action.value,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # VALIDATION HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_movement(self, destination: str) -> tuple[bool, str | None]:
        """
        Valida che il movimento sia possibile.
        
        Returns:
            (True, None) se valido
            (False, error_message) se non valido
        """
        # Verifica che la destinazione esista
        if not self._sublocation_exists(destination):
            return False, f"Destinazione '{destination}' non esiste"
        
        # TODO: Verificare che ci sia un percorso valido
        # Per ora accettiamo qualsiasi movimento a sublocation esistente
        
        return True, None
    
    def _sublocation_exists(self, subloc_id: str) -> bool:
        """Verifica se una sublocation esiste (seed o procedurale)."""
        # Controlla nel seed
        if self.world_manager.sublocation_exists_in_seed(subloc_id):
            return True
        
        # Controlla nelle sublocation procedurali del personaggio
        if self.state.has_procedural_sublocation(subloc_id):
            return True
        
        return False
    
    def _get_procedural_sublocation(self, subloc_id: str) -> dict | None:
        """Ottiene dati di una sublocation procedurale."""
        return self.state.get_procedural_sublocation(subloc_id)
    
    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════
    
    def save(self):
        """Salva lo stato dopo tutte le modifiche."""
        self.state_manager.save_state(self.character_id)
