# location_memory.py - Gestione memoria chat per location
"""
Salva e recupera la storia delle chat per ogni location.
Quando il giocatore torna in una location, recupera il contesto.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field


@dataclass
class LocationMemory:
    """Memoria di una singola location per un personaggio"""
    location_id: str
    character_id: str
    
    # Chat history
    messages: List[Dict[str, str]] = field(default_factory=list)
    
    # Stato location
    flags: Dict[str, Any] = field(default_factory=dict)
    npc_dispositions: Dict[str, str] = field(default_factory=dict)
    items_here: List[str] = field(default_factory=list)
    
    # Eventi chiave (per riassunto)
    key_events: List[str] = field(default_factory=list)
    
    # Meta
    visit_count: int = 0
    first_visited: Optional[str] = None
    last_visited: Optional[str] = None
    
    def add_message(self, role: str, content: str):
        """Aggiunge un messaggio alla history"""
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_event(self, event: str):
        """Aggiunge un evento chiave"""
        self.key_events.append(event)
        # Mantieni solo ultimi 10 eventi
        if len(self.key_events) > 10:
            self.key_events = self.key_events[-10:]
    
    def set_flag(self, key: str, value: Any):
        """Imposta un flag della location"""
        self.flags[key] = value
    
    def set_npc_disposition(self, npc: str, disposition: str):
        """Imposta la disposizione di un NPC"""
        self.npc_dispositions[npc] = disposition
    
    def record_visit(self):
        """Registra una visita"""
        now = datetime.now().isoformat()
        self.visit_count += 1
        self.last_visited = now
        if not self.first_visited:
            self.first_visited = now
    
    def get_recent_messages(self, n: int = 10) -> List[Dict]:
        """Ottiene gli ultimi N messaggi"""
        return self.messages[-n:] if self.messages else []
    
    def generate_recap(self, n_events: int = 3) -> str:
        """
        Genera un riassunto per quando il giocatore torna.
        Formato: "L'ultima volta che sei stato qui..."
        """
        if self.visit_count == 0:
            return ""
        
        if self.visit_count == 1 and not self.key_events:
            return ""
        
        recap_parts = []
        
        # Eventi recenti
        recent_events = self.key_events[-n_events:] if self.key_events else []
        if recent_events:
            events_text = "; ".join(recent_events)
            recap_parts.append(f"Eventi passati: {events_text}")
        
        # NPC e relazioni
        if self.npc_dispositions:
            relations = [f"{npc} ({disp})" for npc, disp in self.npc_dispositions.items()]
            recap_parts.append(f"Relazioni: {', '.join(relations)}")
        
        # Flags significativi
        significant_flags = {k: v for k, v in self.flags.items() if v is True}
        if significant_flags:
            flags_text = ", ".join(significant_flags.keys())
            recap_parts.append(f"Stato: {flags_text}")
        
        if not recap_parts:
            return ""
        
        return f"[MEMORIA DELLA LOCATION]\nL'ultima volta che sei stato qui: {' | '.join(recap_parts)}"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LocationMemory':
        return cls(**data)


class LocationMemoryManager:
    """Gestisce le memorie di tutte le location per tutti i personaggi"""
    
    def __init__(self, data_dir: str = "db/data/memories"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._cache: Dict[str, Dict[str, LocationMemory]] = {}
    
    def _get_filepath(self, character_id: str) -> str:
        return os.path.join(self.data_dir, f"{character_id}_memories.json")
    
    def _load_character_memories(self, character_id: str) -> Dict[str, LocationMemory]:
        """Carica tutte le memorie di un personaggio"""
        if character_id in self._cache:
            return self._cache[character_id]
        
        filepath = self._get_filepath(character_id)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                memories = {
                    loc_id: LocationMemory.from_dict(mem_data)
                    for loc_id, mem_data in data.items()
                }
        else:
            memories = {}
        
        self._cache[character_id] = memories
        return memories
    
    def _save_character_memories(self, character_id: str):
        """Salva tutte le memorie di un personaggio"""
        if character_id not in self._cache:
            return
        
        filepath = self._get_filepath(character_id)
        data = {
            loc_id: mem.to_dict()
            for loc_id, mem in self._cache[character_id].items()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_memory(self, character_id: str, location_id: str) -> LocationMemory:
        """Ottiene la memoria di una location (crea se non esiste)"""
        memories = self._load_character_memories(character_id)
        
        if location_id not in memories:
            memories[location_id] = LocationMemory(
                location_id=location_id,
                character_id=character_id
            )
        
        return memories[location_id]
    
    def save_memory(self, character_id: str, location_id: str, memory: LocationMemory):
        """Salva la memoria di una location"""
        memories = self._load_character_memories(character_id)
        memories[location_id] = memory
        self._save_character_memories(character_id)
    
    def record_visit(self, character_id: str, location_id: str):
        """Registra una visita a una location"""
        memory = self.get_memory(character_id, location_id)
        memory.record_visit()
        self.save_memory(character_id, location_id, memory)
    
    def add_message(self, character_id: str, location_id: str, role: str, content: str):
        """Aggiunge un messaggio alla history della location"""
        memory = self.get_memory(character_id, location_id)
        memory.add_message(role, content)
        self.save_memory(character_id, location_id, memory)
    
    def add_event(self, character_id: str, location_id: str, event: str):
        """Aggiunge un evento chiave"""
        memory = self.get_memory(character_id, location_id)
        memory.add_event(event)
        self.save_memory(character_id, location_id, memory)
    
    def get_recap(self, character_id: str, location_id: str) -> str:
        """Ottiene il riassunto per una location"""
        memory = self.get_memory(character_id, location_id)
        return memory.generate_recap()
    
    def get_recent_messages(self, character_id: str, location_id: str, n: int = 10) -> List[Dict]:
        """Ottiene gli ultimi N messaggi di una location"""
        memory = self.get_memory(character_id, location_id)
        return memory.get_recent_messages(n)
    
    def switch_location(self, character_id: str, from_location: str, to_location: str, 
                        current_messages: List[Dict]) -> Dict:
        """
        Gestisce il cambio di location.
        Salva la chat corrente, carica quella della nuova location.
        """
        # Salva messaggi della location che stiamo lasciando
        if from_location and current_messages:
            from_memory = self.get_memory(character_id, from_location)
            from_memory.messages = current_messages
            self.save_memory(character_id, from_location, from_memory)
        
        # Carica memoria della nuova location
        to_memory = self.get_memory(character_id, to_location)
        to_memory.record_visit()
        self.save_memory(character_id, to_location, to_memory)
        
        # Genera recap se non è la prima visita
        recap = to_memory.generate_recap() if to_memory.visit_count > 1 else ""
        
        return {
            'messages': to_memory.messages,
            'recap': recap,
            'visit_count': to_memory.visit_count,
            'flags': to_memory.flags,
            'npc_dispositions': to_memory.npc_dispositions,
            'key_events': to_memory.key_events
        }


# Singleton
_memory_manager: Optional[LocationMemoryManager] = None

def get_memory_manager() -> LocationMemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = LocationMemoryManager()
    return _memory_manager
