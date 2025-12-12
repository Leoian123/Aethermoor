# world_manager.py - Gestione integrata mondo (seed + state procedurale)
"""
Combina:
- world_seed.json: dati geografici FISSI
- player_state: posizione + scoperte PROCEDURALI

Fornisce:
- Contesto completo per il GM
- Validazione movimenti
- Risoluzione NPC
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from .player_state import PlayerState, PlayerPosition, get_player_state_manager


class WorldManager:
    """
    Gestisce l'accesso al mondo combinando seed e stato procedurale.
    """
    
    _instance = None
    _seed: Dict[str, Any] = None
    
    def __init__(self):
        self._load_seed()
    
    def _load_seed(self):
        """Carica il seed del mondo"""
        seed_path = os.path.join(os.path.dirname(__file__), 'data', 'world_seed.json')
        with open(seed_path, 'r', encoding='utf-8') as f:
            WorldManager._seed = json.load(f)
    
    @property
    def seed(self) -> Dict[str, Any]:
        return WorldManager._seed
    
    # ═══════════════════════════════════════════════════════════════
    # GETTERS - Accesso dati seed
    # ═══════════════════════════════════════════════════════════════
    
    def get_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        return self.seed.get("regions", {}).get(region_id)
    
    def get_zone(self, zone_id: str) -> Optional[Dict[str, Any]]:
        return self.seed.get("zones", {}).get(zone_id)
    
    def get_location(self, location_id: str) -> Optional[Dict[str, Any]]:
        return self.seed.get("locations", {}).get(location_id)
    
    def get_sublocation(self, subloc_id: str, state: PlayerState = None) -> Optional[Dict[str, Any]]:
        """Cerca prima nel seed, poi nelle scoperte procedurali"""
        # Prima controlla seed
        subloc = self.seed.get("sublocations", {}).get(subloc_id)
        if subloc:
            return subloc
        
        # Poi controlla scoperte procedurali
        if state and subloc_id in state.discovered_sublocations:
            return state.discovered_sublocations[subloc_id]
        
        return None
    
    def get_npc(self, npc_id: str) -> Optional[Dict[str, Any]]:
        return self.seed.get("npcs", {}).get(npc_id)
    
    # ═══════════════════════════════════════════════════════════════
    # LOCATION RESOLUTION - Trova tutte le sublocation di una location
    # ═══════════════════════════════════════════════════════════════
    
    def get_sublocations_for_location(
        self, 
        location_id: str, 
        state: PlayerState = None,
        include_procedural: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Ritorna tutte le sublocation di una location.
        Combina seed + procedurali.
        """
        results = []
        
        # Dal seed
        location = self.get_location(location_id)
        if location:
            for subloc_id in location.get("sublocations", []):
                subloc = self.get_sublocation(subloc_id)
                if subloc:
                    subloc["_source"] = "seed"
                    results.append(subloc)
        
        # Procedurali
        if include_procedural and state:
            for subloc_id, subloc_data in state.discovered_sublocations.items():
                if subloc_id.startswith(location_id + "."):
                    subloc_data["_source"] = "procedural"
                    results.append(subloc_data)
        
        return results
    
    def get_children(self, subloc_id: str, state: PlayerState = None) -> List[Dict[str, Any]]:
        """Ritorna i figli di una sublocation (es. cantina sotto locanda)"""
        subloc = self.get_sublocation(subloc_id, state)
        if not subloc:
            return []
        
        children = []
        for child_id in subloc.get("children", []):
            child = self.get_sublocation(child_id, state)
            if child:
                children.append(child)
        
        return children
    
    # ═══════════════════════════════════════════════════════════════
    # NPC RESOLUTION - Trova NPC in una location
    # ═══════════════════════════════════════════════════════════════
    
    def get_npcs_at_location(
        self, 
        subloc_id: str, 
        state: PlayerState = None
    ) -> List[Dict[str, Any]]:
        """Ritorna gli NPC presenti in una sublocation con disposition"""
        subloc = self.get_sublocation(subloc_id, state)
        if not subloc:
            return []
        
        npcs = []
        for npc_id in subloc.get("npcs_here", []):
            npc = self.get_npc(npc_id)
            if npc:
                npc_copy = npc.copy()
                # Applica disposition override se presente
                if state:
                    default_disp = npc.get("disposition_default", "neutral")
                    npc_copy["disposition"] = state.get_npc_disposition(npc_id, default_disp)
                else:
                    npc_copy["disposition"] = npc.get("disposition_default", "neutral")
                npcs.append(npc_copy)
        
        return npcs
    
    def get_npc_pool_for_location(self, location_id: str) -> List[Dict[str, Any]]:
        """Ritorna tutti gli NPC della pool di una location"""
        location = self.get_location(location_id)
        if not location:
            return []
        
        npcs = []
        for npc_id in location.get("npc_pool", []):
            npc = self.get_npc(npc_id)
            if npc:
                npcs.append(npc)
        
        return npcs
    
    # ═══════════════════════════════════════════════════════════════
    # MOVEMENT VALIDATION
    # ═══════════════════════════════════════════════════════════════
    
    def validate_movement(
        self,
        state: PlayerState,
        target_id: str,
        movement_type: str = "auto"
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        Valida un movimento e ritorna i nuovi valori di posizione.
        
        movement_type:
        - "sublocation": entra/esci da sublocation
        - "location": cambia location nella stessa zona
        - "zone": cambia zona nella stessa regione
        - "region": cambia regione (viaggio lungo)
        - "auto": determina automaticamente dal target_id
        
        Returns: (valid, error_message, new_position_dict)
        """
        current = state.position
        
        # Auto-detect movement type
        if movement_type == "auto":
            if target_id in self.seed.get("regions", {}):
                movement_type = "region"
            elif target_id in self.seed.get("zones", {}):
                movement_type = "zone"
            elif target_id in self.seed.get("locations", {}):
                movement_type = "location"
            elif "." in target_id:
                movement_type = "sublocation"
            else:
                return False, f"Target sconosciuto: {target_id}", {}
        
        new_pos = current.to_dict()
        
        if movement_type == "sublocation":
            # Verifica che sia raggiungibile
            subloc = self.get_sublocation(target_id, state)
            if not subloc:
                return False, f"Sublocation {target_id} non esiste", {}
            
            # Deve essere nella stessa location O figlia della sublocation corrente
            parent_id = subloc.get("parent_id", "")
            current_subloc = current.sublocation_id
            
            # Caso 1: Entra da location (sublocation diretta)
            if parent_id == current.location_id:
                new_pos["sublocation_id"] = target_id
                return True, "", new_pos
            
            # Caso 2: Entra in figlio della sublocation corrente
            if parent_id == current_subloc:
                new_pos["sublocation_id"] = target_id
                return True, "", new_pos
            
            # Caso 3: Esce al parent
            if target_id == parent_id or target_id == current.location_id:
                new_pos["sublocation_id"] = target_id if target_id != current.location_id else ""
                return True, "", new_pos
            
            # Caso 4: Movimento orizzontale (stesso parent)
            current_subloc_data = self.get_sublocation(current_subloc, state)
            if current_subloc_data:
                exits = current_subloc_data.get("exits", {})
                if target_id in exits:
                    new_pos["sublocation_id"] = target_id
                    return True, "", new_pos
            
            return False, f"Non puoi raggiungere {target_id} da {current_subloc}", {}
        
        elif movement_type == "location":
            location = self.get_location(target_id)
            if not location:
                return False, f"Location {target_id} non esiste", {}
            
            # Deve essere nella stessa zona
            if location.get("zone_id") != current.zone_id:
                return False, f"Location {target_id} non è in {current.zone_id}", {}
            
            new_pos["location_id"] = target_id
            new_pos["sublocation_id"] = ""  # Reset sublocation
            return True, "", new_pos
        
        elif movement_type == "zone":
            zone = self.get_zone(target_id)
            if not zone:
                return False, f"Zona {target_id} non esiste", {}
            
            # Deve essere nella stessa regione
            if zone.get("region_id") != current.region_id:
                return False, f"Zona {target_id} non è in {current.region_id}", {}
            
            new_pos["zone_id"] = target_id
            # Imposta location di default (prima della lista)
            locations = zone.get("locations", [])
            new_pos["location_id"] = locations[0] if locations else ""
            new_pos["sublocation_id"] = ""
            return True, "", new_pos
        
        elif movement_type == "region":
            region = self.get_region(target_id)
            if not region:
                return False, f"Regione {target_id} non esiste", {}
            
            # TODO: Verificare che ci sia un confine raggiungibile
            new_pos["region_id"] = target_id
            # Reset tutto sotto
            new_pos["zone_id"] = ""
            new_pos["location_id"] = ""
            new_pos["sublocation_id"] = ""
            return True, "", new_pos
        
        return False, f"Tipo movimento non valido: {movement_type}", {}
    
    # ═══════════════════════════════════════════════════════════════
    # CONTEXT FOR GM - Genera il prompt con posizione assoluta
    # ═══════════════════════════════════════════════════════════════
    
    def get_context_for_gm(self, character_id: str) -> str:
        """
        Genera il contesto spaziale ASSOLUTO per il system prompt.
        Il GM non può negoziare questa posizione.
        """
        state_mgr = get_player_state_manager()
        state = state_mgr.get_state(character_id)
        pos = state.position
        
        lines = []
        lines.append("=" * 60)
        lines.append("📍 POSIZIONE ATTUALE (ASSOLUTA - NON NEGOZIABILE)")
        lines.append("=" * 60)
        
        # Gerarchia completa
        region = self.get_region(pos.region_id)
        zone = self.get_zone(pos.zone_id)
        location = self.get_location(pos.location_id)
        sublocation = self.get_sublocation(pos.sublocation_id, state) if pos.sublocation_id else None
        
        if region:
            lines.append(f"Regione: {region['name']} ({pos.region_id})")
        if zone:
            lines.append(f"Zona: {zone['name']} ({pos.zone_id})")
        if location:
            lines.append(f"Location: {location['name']} ({pos.location_id})")
        if sublocation:
            lines.append(f"Sublocation: {sublocation['name']} ({pos.sublocation_id})")
        
        lines.append("")
        lines.append(f"PATH: {pos.get_full_path()}")
        
        # Descrizione attuale
        current_place = sublocation or location
        if current_place:
            lines.append("")
            lines.append(f"DESCRIZIONE: {current_place.get('description', 'Nessuna descrizione')}")
            lines.append(f"TIPO: {current_place.get('type', 'unknown')}")
            tags = current_place.get('tags', [])
            if tags:
                lines.append(f"TAGS: {', '.join(tags)}")
        
        # NPC presenti
        if pos.sublocation_id:
            npcs = self.get_npcs_at_location(pos.sublocation_id, state)
            if npcs:
                lines.append("")
                lines.append("NPC PRESENTI:")
                for npc in npcs:
                    lines.append(f"  - {npc['name']} ({npc['title']}) [{npc['disposition']}]")
                    lines.append(f"    {npc['description']}")
        
        # Uscite disponibili
        if sublocation:
            exits = sublocation.get("exits", {})
            children = sublocation.get("children", [])
            if exits or children:
                lines.append("")
                lines.append("USCITE DISPONIBILI:")
                for exit_id, exit_label in exits.items():
                    lines.append(f"  → {exit_label} [{exit_id}]")
                for child_id in children:
                    child = self.get_sublocation(child_id, state)
                    if child:
                        lines.append(f"  ↓ {child['name']} [{child_id}]")
        elif location:
            sublocations = self.get_sublocations_for_location(pos.location_id, state)
            if sublocations:
                lines.append("")
                lines.append("LUOGHI ACCESSIBILI:")
                for subloc in sublocations:
                    lines.append(f"  → {subloc['name']} [{subloc['id']}]")
        
        # Prima visita?
        if state.is_first_visit():
            lines.append("")
            lines.append("⭐ PRIMA VISITA - Descrivi il luogo in dettaglio!")
        
        # Pool NPC della location (per riferimento)
        if location:
            lines.append("")
            lines.append("NPC POOL (possono apparire in questa location):")
            for npc_id in location.get("npc_pool", []):
                npc = self.get_npc(npc_id)
                if npc:
                    home = npc.get("home", "sconosciuto")
                    lines.append(f"  - {npc['name']}: {npc['title']} (home: {home})")
        
        lines.append("")
        lines.append("=" * 60)
        lines.append("Il giocatore È QUI. Se dice di essere altrove, è confuso.")
        lines.append("Per spostarlo, usa i tag di movimento appropriati.")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def get_location_info_for_api(self, character_id: str) -> Dict[str, Any]:
        """Ritorna info location per API frontend"""
        state_mgr = get_player_state_manager()
        state = state_mgr.get_state(character_id)
        pos = state.position
        
        region = self.get_region(pos.region_id)
        zone = self.get_zone(pos.zone_id)
        location = self.get_location(pos.location_id)
        sublocation = self.get_sublocation(pos.sublocation_id, state) if pos.sublocation_id else None
        
        current_place = sublocation or location or {}
        
        # Costruisci breadcrumb
        breadcrumb = []
        if region:
            breadcrumb.append({"id": pos.region_id, "name": region["name"], "type": "region"})
        if zone:
            breadcrumb.append({"id": pos.zone_id, "name": zone["name"], "type": "zone"})
        if location:
            breadcrumb.append({"id": pos.location_id, "name": location["name"], "type": "location"})
        if sublocation:
            breadcrumb.append({"id": pos.sublocation_id, "name": sublocation["name"], "type": "sublocation"})
        
        # Exits / Neighbors (per MiniMap)
        exits = []
        neighbors = []  # Formato compatibile con MiniMap
        
        if sublocation:
            # Uscite (verso parent o altre sublocation)
            for exit_id, exit_label in sublocation.get("exits", {}).items():
                exit_subloc = self.get_sublocation(exit_id, state)
                visited = state.get_visit_count(exit_id) > 0
                exits.append({"id": exit_id, "label": exit_label, "type": "exit"})
                neighbors.append({
                    "id": exit_id, 
                    "name": exit_subloc.get("name", exit_label) if exit_subloc else exit_label,
                    "type": "exit",
                    "visited": visited,
                    "locked": False
                })
            
            # Figli (entrare)
            for child_id in sublocation.get("children", []):
                child = self.get_sublocation(child_id, state)
                if child:
                    visited = state.get_visit_count(child_id) > 0
                    exits.append({"id": child_id, "label": child["name"], "type": "enter"})
                    neighbors.append({
                        "id": child_id,
                        "name": child["name"],
                        "type": "enter",
                        "visited": visited,
                        "locked": False
                    })
        
        elif location:
            # Sublocation accessibili dalla location
            for subloc in self.get_sublocations_for_location(pos.location_id, state):
                if subloc.get("parent_id") == pos.location_id:
                    subloc_id = subloc["id"]
                    visited = state.get_visit_count(subloc_id) > 0
                    exits.append({"id": subloc_id, "label": subloc["name"], "type": "enter"})
                    neighbors.append({
                        "id": subloc_id,
                        "name": subloc["name"],
                        "type": "enter",
                        "visited": visited,
                        "locked": False
                    })
        
        # NPCs
        npcs = []
        if pos.sublocation_id:
            for npc in self.get_npcs_at_location(pos.sublocation_id, state):
                npcs.append({
                    "id": npc["id"],
                    "name": npc["name"],
                    "title": npc.get("title", ""),
                    "disposition": npc.get("disposition", "neutral")
                })
        
        return {
            "has_location": True,
            "position": pos.to_dict(),
            "current": {
                "id": pos.get_current_id(),
                "name": current_place.get("name", "Sconosciuto"),
                "description": current_place.get("description", ""),
                "type": current_place.get("type", "unknown"),
                "tags": current_place.get("tags", [])
            },
            "breadcrumb": breadcrumb,
            "exits": exits,
            "neighbors": neighbors,  # Per compatibilità MiniMap
            "npcs": npcs,
            "is_first_visit": state.is_first_visit(),
            "visit_count": state.get_visit_count(pos.get_current_id())
        }
    
    def get_exploration_graph(self, character_id: str) -> Dict[str, Any]:
        """
        Ritorna il grafo completo dell'esplorazione per la MiniMap.
        Include tutti i nodi della location corrente + connessioni tra di essi.
        """
        state_mgr = get_player_state_manager()
        state = state_mgr.get_state(character_id)
        pos = state.position
        
        nodes = {}  # id -> node data
        edges = []
        
        current_id = pos.get_current_id()
        
        # 1. Aggiungi tutte le sublocation della location corrente (dal seed)
        location = self.get_location(pos.location_id)
        if location:
            for subloc_id in location.get("sublocations", []):
                subloc = self.get_sublocation(subloc_id, state)
                if subloc:
                    visited = state.get_visit_count(subloc_id) > 0
                    nodes[subloc_id] = {
                        "id": subloc_id,
                        "name": subloc.get("name", subloc_id),
                        "type": subloc.get("type", "room"),
                        "visited": visited,
                        "is_current": subloc_id == current_id,
                        "parent_id": subloc.get("parent_id", "")
                    }
                    
                    # Aggiungi anche i figli (es. cantina, stanze)
                    for child_id in subloc.get("children", []):
                        child_subloc = self.get_sublocation(child_id, state)
                        if child_subloc and child_id not in nodes:
                            child_visited = state.get_visit_count(child_id) > 0
                            nodes[child_id] = {
                                "id": child_id,
                                "name": child_subloc.get("name", child_id),
                                "type": child_subloc.get("type", "room"),
                                "visited": child_visited,
                                "is_current": child_id == current_id,
                                "parent_id": child_subloc.get("parent_id", "")
                            }
        
        # 2. Aggiungi sublocation procedurali scoperte
        for subloc_id, subloc_data in state.discovered_sublocations.items():
            if subloc_id not in nodes:
                visited = state.get_visit_count(subloc_id) > 0
                nodes[subloc_id] = {
                    "id": subloc_id,
                    "name": subloc_data.get("name", subloc_id),
                    "type": subloc_data.get("type", "room"),
                    "visited": visited,
                    "is_current": subloc_id == current_id,
                    "parent_id": subloc_data.get("parent_id", ""),
                    "procedural": True
                }
        
        # 3. Assicurati che il nodo corrente sia incluso
        if current_id and current_id not in nodes:
            subloc = self.get_sublocation(current_id, state)
            if subloc:
                nodes[current_id] = {
                    "id": current_id,
                    "name": subloc.get("name", current_id),
                    "type": subloc.get("type", "room"),
                    "visited": True,
                    "is_current": True,
                    "parent_id": subloc.get("parent_id", "")
                }
        
        # 4. Genera edges da tutte le exits
        seen_edges = set()
        for node_id in nodes:
            subloc = self.get_sublocation(node_id, state)
            if subloc:
                # Edges dalle exits
                for exit_id in subloc.get("exits", {}).keys():
                    if exit_id in nodes:
                        edge_key = tuple(sorted([node_id, exit_id]))
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            edges.append({
                                "from": node_id,
                                "to": exit_id,
                                "type": "connection"
                            })
                
                # Edges verso i figli
                for child_id in subloc.get("children", []):
                    if child_id in nodes:
                        edge_key = tuple(sorted([node_id, child_id]))
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            edges.append({
                                "from": node_id,
                                "to": child_id,
                                "type": "enter"
                            })
        
        return {
            "has_location": True,
            "current_id": current_id,
            "location_id": pos.location_id,
            "location_name": location.get("name", "") if location else "",
            "nodes": list(nodes.values()),
            "edges": edges,
            "breadcrumb": self._build_breadcrumb(pos)
        }
    
    def _build_breadcrumb(self, pos) -> List[Dict[str, str]]:
        """Helper per costruire breadcrumb"""
        breadcrumb = []
        region = self.get_region(pos.region_id)
        zone = self.get_zone(pos.zone_id)
        location = self.get_location(pos.location_id)
        
        if region:
            breadcrumb.append({"id": pos.region_id, "name": region["name"], "type": "region"})
        if zone:
            breadcrumb.append({"id": pos.zone_id, "name": zone["name"], "type": "zone"})
        if location:
            breadcrumb.append({"id": pos.location_id, "name": location["name"], "type": "location"})
        if pos.sublocation_id:
            subloc = self.get_sublocation(pos.sublocation_id, None)
            if subloc:
                breadcrumb.append({"id": pos.sublocation_id, "name": subloc["name"], "type": "sublocation"})
        return breadcrumb


def get_world_manager() -> WorldManager:
    """Singleton per WorldManager"""
    if WorldManager._instance is None:
        WorldManager._instance = WorldManager()
    return WorldManager._instance
