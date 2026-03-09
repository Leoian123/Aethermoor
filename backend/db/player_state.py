# player_state.py - Gestione posizione assoluta del giocatore
"""
La posizione del giocatore è uno STATO ASSOLUTO.
Il modello NON può cambiarla senza tag esplicito.
Il modello riceve la posizione come FATTO nel prompt.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class PlayerPosition:
    """
    Posizione gerarchica del giocatore.
    Ogni livello è esplicito e non negoziabile.
    """
    region_id: str          # "valeria"
    zone_id: str            # "lumengarde"  
    location_id: str        # "albachiara"
    sublocation_id: str     # "albachiara.piazza" o "" se all'aperto nella location
    
    def get_full_path(self) -> str:
        """Ritorna il path completo per debug/logging"""
        parts = [self.region_id, self.zone_id, self.location_id]
        if self.sublocation_id:
            parts.append(self.sublocation_id)
        return " > ".join(parts)
    
    def get_current_id(self) -> str:
        """Ritorna l'ID della posizione più specifica"""
        return self.sublocation_id if self.sublocation_id else self.location_id
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "region_id": self.region_id,
            "zone_id": self.zone_id,
            "location_id": self.location_id,
            "sublocation_id": self.sublocation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'PlayerPosition':
        return cls(
            region_id=data.get("region_id", ""),
            zone_id=data.get("zone_id", ""),
            location_id=data.get("location_id", ""),
            sublocation_id=data.get("sublocation_id", "")
        )


@dataclass
class PlayerState:
    """
    Stato completo del giocatore nel mondo.
    Include posizione + dati procedurali scoperti.
    """
    character_id: str
    position: PlayerPosition
    
    # Sublocation procedurali scoperte (non nel seed)
    discovered_sublocations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Connessioni procedurali scoperte
    discovered_connections: List[Dict[str, str]] = field(default_factory=list)
    
    # Storia visite per location (per recap)
    visit_history: Dict[str, List[str]] = field(default_factory=dict)  # location_id -> [timestamps]
    
    # NPC disposition overrides (se cambia da default)
    npc_dispositions: Dict[str, str] = field(default_factory=dict)
    
    # Flags globali di stato
    flags: Dict[str, Any] = field(default_factory=dict)
    
    # ═══════════════════════════════════════════════════════════════
    # STATS & CHARACTER DATA (per applicators)
    # ═══════════════════════════════════════════════════════════════
    
    name: str = ""
    class_name: str = ""
    level: int = 1
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def record_visit(self):
        """Registra una visita alla posizione corrente"""
        loc_id = self.position.get_current_id()
        if loc_id not in self.visit_history:
            self.visit_history[loc_id] = []
        self.visit_history[loc_id].append(datetime.now().isoformat())
    
    def get_visit_count(self, location_id: str) -> int:
        """Numero di visite a una location"""
        return len(self.visit_history.get(location_id, []))
    
    def is_first_visit(self, location_id: str = None) -> bool:
        """È la prima visita a questa location?"""
        loc_id = location_id or self.position.get_current_id()
        return self.get_visit_count(loc_id) <= 1
    
    # ═══════════════════════════════════════════════════════════════
    # PROCEDURAL SUBLOCATIONS
    # ═══════════════════════════════════════════════════════════════
    
    def add_procedural_sublocation(self, subloc_id: str, data: Dict[str, Any]):
        """Aggiunge una sublocation scoperta proceduralmente"""
        # Valida che l'ID sia figlio della location corrente
        if not subloc_id.startswith(self.position.location_id + "."):
            raise ValueError(f"Sublocation {subloc_id} non è figlia di {self.position.location_id}")
        self.discovered_sublocations[subloc_id] = data
    
    def has_procedural_sublocation(self, subloc_id: str) -> bool:
        """Verifica se una sublocation procedurale esiste"""
        return subloc_id in self.discovered_sublocations
    
    def get_procedural_sublocation(self, subloc_id: str) -> Optional[Dict[str, Any]]:
        """Ottieni dati di una sublocation procedurale"""
        return self.discovered_sublocations.get(subloc_id)
    
    # ═══════════════════════════════════════════════════════════════
    # NPC DISPOSITIONS
    # ═══════════════════════════════════════════════════════════════
    
    def get_npc_disposition(self, npc_id: str, default: str = "neutral") -> str:
        """Ottieni disposition NPC (override o default)"""
        return self.npc_dispositions.get(npc_id, default)
    
    def set_npc_disposition(self, npc_id: str, disposition: str):
        """Imposta disposition NPC"""
        self.npc_dispositions[npc_id] = disposition
    
    # ═══════════════════════════════════════════════════════════════
    # INVENTORY (per applicators)
    # ═══════════════════════════════════════════════════════════════
    
    def add_item(self, item_name: str) -> bool:
        """Aggiunge item all'inventario"""
        if "inventory" not in self.stats:
            self.stats["inventory"] = []
        if item_name not in self.stats["inventory"]:
            self.stats["inventory"].append(item_name)
            return True
        return False
    
    def remove_item(self, item_name: str) -> bool:
        """Rimuove item dall'inventario"""
        if "inventory" in self.stats and item_name in self.stats["inventory"]:
            self.stats["inventory"].remove(item_name)
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════
    # SERIALIZATION
    # ═══════════════════════════════════════════════════════════════
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "position": self.position.to_dict(),
            "discovered_sublocations": self.discovered_sublocations,
            "discovered_connections": self.discovered_connections,
            "visit_history": self.visit_history,
            "npc_dispositions": self.npc_dispositions,
            "flags": self.flags,
            "name": self.name,
            "class_name": self.class_name,
            "level": self.level,
            "stats": self.stats,
        }
    
    def __post_init__(self):
        """Assicura che stats e flags abbiano i default necessari."""
        if "corone" not in self.stats:
            self.stats["corone"] = 0
        if "checkpoints" not in self.flags:
            self.flags["checkpoints"] = []

    def save_checkpoint(self):
        """
        Salva la posizione corrente come checkpoint per il respawn.

        Chiamato automaticamente su cambio location e completamento quest.
        Mantiene solo gli ultimi 5 checkpoint (LIFO).
        """
        checkpoint = self.position.to_dict()

        # Evita duplicati consecutivi
        checkpoints = self.flags.get("checkpoints", [])
        if checkpoints and checkpoints[-1] == checkpoint:
            return

        checkpoints.append(checkpoint)
        # Tieni solo gli ultimi 5
        self.flags["checkpoints"] = checkpoints[-5:]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerState':
        return cls(
            character_id=data["character_id"],
            position=PlayerPosition.from_dict(data["position"]),
            discovered_sublocations=data.get("discovered_sublocations", {}),
            discovered_connections=data.get("discovered_connections", []),
            visit_history=data.get("visit_history", {}),
            npc_dispositions=data.get("npc_dispositions", {}),
            flags=data.get("flags", {}),
            name=data.get("name", ""),
            class_name=data.get("class_name", ""),
            level=data.get("level", 1),
            stats=data.get("stats", {}),
        )


class PlayerStateManager:
    """
    Gestisce il salvataggio/caricamento dello stato giocatore.
    Singleton per accesso globale.
    """
    
    _instance = None
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), 'data', 'player_states')
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._states: Dict[str, PlayerState] = {}
        self._default_spawn = self._load_default_spawn()
    
    def _load_default_spawn(self) -> Dict[str, str]:
        """Carica lo spawn point dal seed"""
        seed_path = os.path.join(os.path.dirname(__file__), 'data', 'world_seed.json')
        try:
            with open(seed_path, 'r', encoding='utf-8') as f:
                seed = json.load(f)
                spawn_id = seed.get("meta", {}).get("default_spawn", "albachiara.piazza")
                # Parse spawn_id per estrarre la gerarchia
                # albachiara.piazza → location=albachiara, sublocation=albachiara.piazza
                parts = spawn_id.split(".")
                return {
                    "region_id": "valeria",
                    "zone_id": "lumengarde",
                    "location_id": parts[0],
                    "sublocation_id": spawn_id if len(parts) > 1 else ""
                }
        except:
            return {
                "region_id": "valeria",
                "zone_id": "lumengarde", 
                "location_id": "albachiara",
                "sublocation_id": "albachiara.piazza"
            }
    
    def _get_path(self, character_id: str) -> str:
        return os.path.join(self.data_dir, f"{character_id}_state.json")
    
    def get_state(self, character_id: str) -> PlayerState:
        """Ottieni o crea lo stato per un personaggio"""
        if character_id not in self._states:
            path = self._get_path(character_id)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self._states[character_id] = PlayerState.from_dict(json.load(f))
            else:
                # Nuovo personaggio → spawn point
                self._states[character_id] = PlayerState(
                    character_id=character_id,
                    position=PlayerPosition.from_dict(self._default_spawn)
                )
                self._states[character_id].record_visit()
                self.save_state(character_id)
        
        return self._states[character_id]
    
    def load_state(self, character_id: str) -> PlayerState:
        """Alias di get_state per compatibilità con applicators"""
        return self.get_state(character_id)
    
    def save_state(self, character_id: str):
        """Salva lo stato su file"""
        if character_id in self._states:
            path = self._get_path(character_id)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._states[character_id].to_dict(), f, indent=2, ensure_ascii=False)
    
    def delete_state(self, character_id: str):
        """Elimina lo stato di un personaggio"""
        if character_id in self._states:
            del self._states[character_id]
        path = self._get_path(character_id)
        if os.path.exists(path):
            os.remove(path)
    
    def move_player(
        self,
        character_id: str,
        region_id: str = None,
        zone_id: str = None,
        location_id: str = None,
        sublocation_id: str = None
    ) -> PlayerState:
        """
        Muove il giocatore. Solo i parametri forniti vengono aggiornati.
        Validazione: sublocation deve essere figlia di location.
        """
        state = self.get_state(character_id)
        
        if region_id:
            state.position.region_id = region_id
        if zone_id:
            state.position.zone_id = zone_id
        if location_id:
            state.position.location_id = location_id
            # Reset sublocation quando cambi location
            state.position.sublocation_id = ""
        if sublocation_id is not None:  # Può essere "" per uscire
            # Valida che sia figlia della location
            if sublocation_id and not sublocation_id.startswith(state.position.location_id):
                raise ValueError(f"Sublocation {sublocation_id} non è in {state.position.location_id}")
            state.position.sublocation_id = sublocation_id
        
        state.record_visit()
        self.save_state(character_id)
        return state


def get_player_state_manager() -> PlayerStateManager:
    """Singleton per PlayerStateManager"""
    if PlayerStateManager._instance is None:
        PlayerStateManager._instance = PlayerStateManager()
    return PlayerStateManager._instance
