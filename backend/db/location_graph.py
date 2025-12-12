# location_graph.py - Sistema di mappe a grafo generabili dall'AI
from typing import Dict, List, Optional, Set, Tuple
from collections import deque
import json
import os

class LocationNode:
    """Rappresenta una location nel mondo di gioco"""
    def __init__(self, id: str, name: str, description: str = "", tags: List[str] = None):
        self.id = id
        self.name = name
        self.description = description
        self.tags = set(tags) if tags else set()
        self.npcs: List[str] = []  # NPC presenti
        self.items: List[str] = []  # Item nella location
        self.visited: bool = False
        self.discovered: bool = False  # Il giocatore sa che esiste?
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "npcs": self.npcs,
            "items": self.items,
            "visited": self.visited,
            "discovered": self.discovered
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LocationNode':
        node = cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            tags=data.get("tags", [])
        )
        node.npcs = data.get("npcs", [])
        node.items = data.get("items", [])
        node.visited = data.get("visited", False)
        node.discovered = data.get("discovered", False)
        return node


class LocationEdge:
    """Rappresenta una connessione tra due location"""
    def __init__(self, from_id: str, to_id: str, label: str = "",
                 bidirectional: bool = True, hidden: bool = False, 
                 locked: bool = False, condition: str = ""):
        self.from_id = from_id
        self.to_id = to_id
        self.label = label  # "Porta Nord", "Scala", "Passaggio Segreto"
        self.bidirectional = bidirectional
        self.hidden = hidden  # Non visibile finché non scoperto
        self.locked = locked  # Bloccato (serve chiave/azione)
        self.condition = condition  # es. "has_item:iron_key" o "skill:lockpick>=10"
    
    def to_dict(self) -> dict:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "label": self.label,
            "bidirectional": self.bidirectional,
            "hidden": self.hidden,
            "locked": self.locked,
            "condition": self.condition
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LocationEdge':
        return cls(
            from_id=data["from_id"],
            to_id=data["to_id"],
            label=data.get("label", ""),
            bidirectional=data.get("bidirectional", True),
            hidden=data.get("hidden", False),
            locked=data.get("locked", False),
            condition=data.get("condition", "")
        )


class LocationGraph:
    """
    Grafo delle location del mondo di gioco.
    Supporta creazione dinamica da parte dell'AI.
    """
    
    def __init__(self, character_id: str):
        self.character_id = character_id
        self.nodes: Dict[str, LocationNode] = {}
        self.edges: List[LocationEdge] = []
        self.current_location: Optional[str] = None
        
        # Indici per lookup O(1)
        self._adjacency: Dict[str, List[Tuple[str, LocationEdge]]] = {}
        self._edge_index: Dict[Tuple[str, str], LocationEdge] = {}
    
    # ═══════════════════════════════════════
    # CREAZIONE DINAMICA (chiamata dal GM)
    # ═══════════════════════════════════════
    
    def create_location(self, id: str, name: str, description: str = "", 
                        tags: List[str] = None) -> LocationNode:
        """Crea una nuova location (chiamata quando l'AI genera <location_create>)"""
        if id in self.nodes:
            # Aggiorna location esistente
            node = self.nodes[id]
            node.name = name
            if description:
                node.description = description
            if tags:
                node.tags = set(tags)
            return node
        
        node = LocationNode(id, name, description, tags)
        self.nodes[id] = node
        self._adjacency[id] = []
        
        # Se è la prima location, imposta come corrente
        if self.current_location is None:
            self.current_location = id
            node.visited = True
            node.discovered = True
        
        return node
    
    def create_edge(self, from_id: str, to_id: str, label: str = "",
                    bidirectional: bool = True, hidden: bool = False,
                    locked: bool = False, condition: str = "") -> Optional[LocationEdge]:
        """Crea una connessione tra location"""
        # Verifica che le location esistano
        if from_id not in self.nodes or to_id not in self.nodes:
            return None
        
        # Evita duplicati
        if (from_id, to_id) in self._edge_index:
            # Aggiorna edge esistente
            edge = self._edge_index[(from_id, to_id)]
            edge.label = label or edge.label
            edge.hidden = hidden
            edge.locked = locked
            edge.condition = condition or edge.condition
            return edge
        
        edge = LocationEdge(from_id, to_id, label, bidirectional, hidden, locked, condition)
        self.edges.append(edge)
        
        # Aggiorna indici
        self._adjacency[from_id].append((to_id, edge))
        self._edge_index[(from_id, to_id)] = edge
        
        if bidirectional:
            self._adjacency[to_id].append((from_id, edge))
            self._edge_index[(to_id, from_id)] = edge
        
        return edge
    
    def update_location(self, id: str, add_tags: List[str] = None, 
                        remove_tags: List[str] = None) -> Optional[LocationNode]:
        """Aggiorna i tag di una location"""
        if id not in self.nodes:
            return None
        
        node = self.nodes[id]
        if add_tags:
            node.tags.update(add_tags)
        if remove_tags:
            node.tags -= set(remove_tags)
        return node
    
    # ═══════════════════════════════════════
    # GESTIONE EDGES
    # ═══════════════════════════════════════
    
    def lock_edge(self, from_id: str, to_id: str) -> bool:
        """Blocca un passaggio"""
        edge = self._edge_index.get((from_id, to_id))
        if edge:
            edge.locked = True
            return True
        return False
    
    def unlock_edge(self, from_id: str, to_id: str) -> bool:
        """Sblocca un passaggio"""
        edge = self._edge_index.get((from_id, to_id))
        if edge:
            edge.locked = False
            return True
        return False
    
    def hide_edge(self, from_id: str, to_id: str) -> bool:
        """Nasconde un passaggio"""
        edge = self._edge_index.get((from_id, to_id))
        if edge:
            edge.hidden = True
            return True
        return False
    
    def reveal_edge(self, from_id: str, to_id: str) -> bool:
        """Rivela un passaggio segreto"""
        edge = self._edge_index.get((from_id, to_id))
        if edge:
            edge.hidden = False
            return True
        return False
    
    # ═══════════════════════════════════════
    # NAVIGAZIONE
    # ═══════════════════════════════════════
    
    def move_to(self, location_id: str) -> bool:
        """Sposta il personaggio in una location"""
        if location_id not in self.nodes:
            return False
        
        # Verifica che ci sia un percorso valido
        if self.current_location and not self.can_reach(self.current_location, location_id):
            return False
        
        self.current_location = location_id
        node = self.nodes[location_id]
        node.visited = True
        node.discovered = True
        return True
    
    def can_reach(self, from_id: str, to_id: str) -> bool:
        """Verifica se è possibile raggiungere una location (passaggio non bloccato/nascosto)"""
        edge = self._edge_index.get((from_id, to_id))
        if not edge:
            return False
        return not edge.locked and not edge.hidden
    
    def get_neighbors(self, location_id: str, include_hidden: bool = False,
                      include_locked: bool = True) -> List[Tuple[str, LocationEdge]]:
        """Ottieni le location raggiungibili da una posizione"""
        if location_id not in self._adjacency:
            return []
        
        result = []
        for neighbor_id, edge in self._adjacency[location_id]:
            if edge.hidden and not include_hidden:
                continue
            if not include_locked and edge.locked:
                continue
            result.append((neighbor_id, edge))
        return result
    
    def get_visible_exits(self, location_id: str = None) -> List[dict]:
        """Ottieni le uscite visibili dalla location corrente (per il GM)"""
        loc_id = location_id or self.current_location
        if not loc_id:
            return []
        
        exits = []
        for neighbor_id, edge in self.get_neighbors(loc_id, include_hidden=False):
            neighbor = self.nodes.get(neighbor_id)
            if neighbor:
                exits.append({
                    "id": neighbor_id,
                    "name": neighbor.name,
                    "label": edge.label,
                    "locked": edge.locked,
                    "visited": neighbor.visited
                })
        return exits
    
    # ═══════════════════════════════════════
    # PATHFINDING
    # ═══════════════════════════════════════
    
    def find_path_bfs(self, start_id: str, goal_id: str, 
                      ignore_locked: bool = False) -> List[str]:
        """Trova il percorso più breve tra due location usando BFS"""
        if start_id not in self.nodes or goal_id not in self.nodes:
            return []
        
        if start_id == goal_id:
            return [start_id]
        
        visited = {start_id}
        queue = deque([(start_id, [start_id])])
        
        while queue:
            current, path = queue.popleft()
            
            for neighbor_id, edge in self._adjacency.get(current, []):
                if neighbor_id in visited:
                    continue
                if edge.hidden:
                    continue
                if edge.locked and not ignore_locked:
                    continue
                
                new_path = path + [neighbor_id]
                if neighbor_id == goal_id:
                    return new_path
                
                visited.add(neighbor_id)
                queue.append((neighbor_id, new_path))
        
        return []  # Nessun percorso trovato
    
    # ═══════════════════════════════════════
    # QUERY
    # ═══════════════════════════════════════
    
    def get_current_location(self) -> Optional[LocationNode]:
        """Ottieni la location corrente"""
        if self.current_location:
            return self.nodes.get(self.current_location)
        return None
    
    def get_location(self, location_id: str) -> Optional[LocationNode]:
        """Ottieni una location per ID"""
        return self.nodes.get(location_id)
    
    def get_edge(self, from_id: str, to_id: str) -> Optional[LocationEdge]:
        """Ottieni un edge specifico"""
        return self._edge_index.get((from_id, to_id))
    
    def get_locations_by_tag(self, tag: str) -> List[LocationNode]:
        """Trova tutte le location con un certo tag"""
        return [node for node in self.nodes.values() if tag in node.tags]
    
    def get_visited_locations(self) -> List[LocationNode]:
        """Ottieni le location già visitate"""
        return [node for node in self.nodes.values() if node.visited]
    
    def get_discovered_locations(self) -> List[LocationNode]:
        """Ottieni le location scoperte (anche se non visitate)"""
        return [node for node in self.nodes.values() if node.discovered]
    
    # ═══════════════════════════════════════
    # CONTEXT PER GM
    # ═══════════════════════════════════════
    
    def get_context_for_gm(self) -> str:
        """Genera un riassunto della situazione spaziale per il system prompt del GM"""
        if not self.current_location:
            return "Il personaggio non si trova in nessuna location definita."
        
        current = self.nodes[self.current_location]
        exits = self.get_visible_exits()
        
        lines = [
            f"LOCATION CORRENTE: {current.name} (ID: {current.id})",
            f"Descrizione: {current.description}" if current.description else "",
            f"Tags: {', '.join(current.tags)}" if current.tags else "",
            "",
            "USCITE VISIBILI:"
        ]
        
        if exits:
            for exit in exits:
                status = "🔒" if exit["locked"] else ("✓" if exit["visited"] else "?")
                lines.append(f"  - {exit['label'] or 'Passaggio'} → {exit['name']} {status}")
        else:
            lines.append("  Nessuna uscita visibile.")
        
        # Location visitate
        visited = self.get_visited_locations()
        if len(visited) > 1:
            lines.append("")
            lines.append(f"LOCATION VISITATE ({len(visited)}):")
            for loc in visited[:10]:  # Max 10 per brevità
                if loc.id != self.current_location:
                    lines.append(f"  - {loc.name}")
        
        return "\n".join(filter(None, lines))
    
    # ═══════════════════════════════════════
    # SERIALIZZAZIONE
    # ═══════════════════════════════════════
    
    def to_dict(self) -> dict:
        """Serializza il grafo in un dizionario"""
        return {
            "character_id": self.character_id,
            "current_location": self.current_location,
            "nodes": {id: node.to_dict() for id, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LocationGraph':
        """Deserializza un grafo da dizionario"""
        graph = cls(data["character_id"])
        graph.current_location = data.get("current_location")
        
        # Carica nodi
        for id, node_data in data.get("nodes", {}).items():
            node = LocationNode.from_dict(node_data)
            graph.nodes[id] = node
            graph._adjacency[id] = []
        
        # Carica edges e ricostruisci indici
        for edge_data in data.get("edges", []):
            edge = LocationEdge.from_dict(edge_data)
            graph.edges.append(edge)
            
            graph._adjacency[edge.from_id].append((edge.to_id, edge))
            graph._edge_index[(edge.from_id, edge.to_id)] = edge
            
            if edge.bidirectional:
                graph._adjacency[edge.to_id].append((edge.from_id, edge))
                graph._edge_index[(edge.to_id, edge.from_id)] = edge
        
        return graph
    
    def save(self, filepath: str):
        """Salva il grafo su file JSON"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> Optional['LocationGraph']:
        """Carica un grafo da file JSON"""
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


# ═══════════════════════════════════════════════════════════════
# MANAGER: gestisce i grafi di tutti i personaggi
# ═══════════════════════════════════════════════════════════════

class LocationGraphManager:
    """Gestisce i grafi delle location per tutti i personaggi"""
    
    def __init__(self, data_dir: str = "db/data/maps"):
        self.data_dir = data_dir
        self.graphs: Dict[str, LocationGraph] = {}
    
    def get_graph(self, character_id: str) -> LocationGraph:
        """Ottieni il grafo di un personaggio (crea se non esiste)"""
        if character_id not in self.graphs:
            # Prova a caricare da file
            filepath = os.path.join(self.data_dir, f"{character_id}_map.json")
            graph = LocationGraph.load(filepath)
            if graph:
                self.graphs[character_id] = graph
            else:
                self.graphs[character_id] = LocationGraph(character_id)
        return self.graphs[character_id]
    
    def save_graph(self, character_id: str):
        """Salva il grafo di un personaggio"""
        if character_id in self.graphs:
            filepath = os.path.join(self.data_dir, f"{character_id}_map.json")
            self.graphs[character_id].save(filepath)
    
    def save_all(self):
        """Salva tutti i grafi"""
        for char_id in self.graphs:
            self.save_graph(char_id)
    
    def delete_graph(self, character_id: str):
        """Elimina il grafo di un personaggio"""
        if character_id in self.graphs:
            del self.graphs[character_id]
        filepath = os.path.join(self.data_dir, f"{character_id}_map.json")
        if os.path.exists(filepath):
            os.remove(filepath)


# Singleton per accesso globale
_manager: Optional[LocationGraphManager] = None

def get_location_manager() -> LocationGraphManager:
    global _manager
    if _manager is None:
        _manager = LocationGraphManager()
    return _manager
