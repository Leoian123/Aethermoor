# world_graph.py - Grafo gerarchico del mondo (regioni → location → stanze)
import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════

@dataclass
class WorldNode:
    """
    Nodo gerarchico del mondo.
    Può essere: region, location, room
    """
    id: str
    name: str
    node_type: str  # "region", "location", "room"
    description: str = ""
    tags: Set[str] = field(default_factory=set)
    
    # Gerarchia
    parent_id: Optional[str] = None
    depth: int = 0  # 0=region, 1=location, 2=room, etc.
    
    # Coordinate hex (solo per regioni, depth=0)
    hex_q: Optional[int] = None
    hex_r: Optional[int] = None
    
    # Stato
    visited: bool = False
    discovered: bool = True
    
    # Contenuti
    npcs: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    
    # Metadata
    first_visited: Optional[str] = None
    last_visited: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type,
            "description": self.description,
            "tags": list(self.tags),
            "parent_id": self.parent_id,
            "depth": self.depth,
            "hex_q": self.hex_q,
            "hex_r": self.hex_r,
            "visited": self.visited,
            "discovered": self.discovered,
            "npcs": self.npcs,
            "items": self.items,
            "first_visited": self.first_visited,
            "last_visited": self.last_visited
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorldNode':
        return cls(
            id=data["id"],
            name=data["name"],
            node_type=data.get("node_type", "location"),
            description=data.get("description", ""),
            tags=set(data.get("tags", [])),
            parent_id=data.get("parent_id"),
            depth=data.get("depth", 0),
            hex_q=data.get("hex_q"),
            hex_r=data.get("hex_r"),
            visited=data.get("visited", False),
            discovered=data.get("discovered", True),
            npcs=data.get("npcs", []),
            items=data.get("items", []),
            first_visited=data.get("first_visited"),
            last_visited=data.get("last_visited")
        )


@dataclass
class WorldEdge:
    """
    Connessione tra nodi (stesso livello o cross-level per passaggi segreti)
    """
    from_id: str
    to_id: str
    label: str = ""  # "porta", "scale", "sentiero", "passaggio segreto"
    edge_type: str = "normal"  # "normal", "secret", "locked", "one_way"
    bidirectional: bool = True
    hidden: bool = False
    locked: bool = False
    condition: str = ""  # Condizione per sbloccare
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "label": self.label,
            "edge_type": self.edge_type,
            "bidirectional": self.bidirectional,
            "hidden": self.hidden,
            "locked": self.locked,
            "condition": self.condition
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorldEdge':
        return cls(
            from_id=data["from_id"],
            to_id=data["to_id"],
            label=data.get("label", ""),
            edge_type=data.get("edge_type", "normal"),
            bidirectional=data.get("bidirectional", True),
            hidden=data.get("hidden", False),
            locked=data.get("locked", False),
            condition=data.get("condition", "")
        )


# ═══════════════════════════════════════════════════════════════
# WORLD GRAPH
# ═══════════════════════════════════════════════════════════════

class WorldGraph:
    """
    Grafo gerarchico del mondo con supporto per:
    - Regioni (hex grid)
    - Location (dentro regioni)
    - Stanze (dentro location)
    - Connessioni orizzontali e verticali
    """
    
    def __init__(self):
        self.nodes: Dict[str, WorldNode] = {}
        self.edges: List[WorldEdge] = []
        self.current_node_id: Optional[str] = None
    
    # ═══════════════════════════════════════
    # NODE OPERATIONS
    # ═══════════════════════════════════════
    
    def create_node(
        self,
        id: str,
        name: str,
        node_type: str = "location",
        description: str = "",
        tags: List[str] = None,
        parent_id: Optional[str] = None,
        hex_q: Optional[int] = None,
        hex_r: Optional[int] = None
    ) -> WorldNode:
        """Crea un nuovo nodo nel grafo"""
        
        # Calcola depth basato sul parent
        depth = 0
        if parent_id and parent_id in self.nodes:
            depth = self.nodes[parent_id].depth + 1
        
        # Auto-detect node_type se non specificato
        if node_type == "location":
            if depth == 0:
                node_type = "region"
            elif depth >= 2:
                node_type = "room"
        
        node = WorldNode(
            id=id,
            name=name,
            node_type=node_type,
            description=description,
            tags=set(tags or []),
            parent_id=parent_id,
            depth=depth,
            hex_q=hex_q,
            hex_r=hex_r
        )
        
        self.nodes[id] = node
        
        # Se ha un parent, crea automaticamente edge bidirezionale
        if parent_id and parent_id in self.nodes:
            self.create_edge(parent_id, id, label="accesso", bidirectional=True)
        
        return node
    
    def get_node(self, node_id: str) -> Optional[WorldNode]:
        return self.nodes.get(node_id)
    
    def get_children(self, node_id: str) -> List[WorldNode]:
        """Ottieni tutti i figli diretti di un nodo"""
        return [n for n in self.nodes.values() if n.parent_id == node_id]
    
    def get_siblings(self, node_id: str) -> List[WorldNode]:
        """Ottieni tutti i fratelli (stesso parent)"""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [n for n in self.nodes.values() 
                if n.parent_id == node.parent_id and n.id != node_id]
    
    def get_ancestors(self, node_id: str) -> List[WorldNode]:
        """Ottieni tutti gli antenati (parent, grandparent, etc.)"""
        ancestors = []
        current = self.nodes.get(node_id)
        while current and current.parent_id:
            parent = self.nodes.get(current.parent_id)
            if parent:
                ancestors.append(parent)
                current = parent
            else:
                break
        return ancestors
    
    def get_region(self, node_id: str) -> Optional[WorldNode]:
        """Ottieni la regione (depth=0) che contiene questo nodo"""
        node = self.nodes.get(node_id)
        if not node:
            return None
        if node.depth == 0:
            return node
        ancestors = self.get_ancestors(node_id)
        for a in ancestors:
            if a.depth == 0:
                return a
        return None
    
    def get_breadcrumb(self, node_id: str) -> List[WorldNode]:
        """Ottieni il percorso dalla root al nodo (per breadcrumb UI)"""
        ancestors = self.get_ancestors(node_id)
        ancestors.reverse()
        node = self.nodes.get(node_id)
        if node:
            ancestors.append(node)
        return ancestors
    
    # ═══════════════════════════════════════
    # EDGE OPERATIONS
    # ═══════════════════════════════════════
    
    def create_edge(
        self,
        from_id: str,
        to_id: str,
        label: str = "",
        edge_type: str = "normal",
        bidirectional: bool = True,
        hidden: bool = False,
        locked: bool = False,
        condition: str = ""
    ) -> Optional[WorldEdge]:
        """Crea una connessione tra due nodi"""
        
        if from_id not in self.nodes or to_id not in self.nodes:
            return None
        
        # Evita duplicati
        for e in self.edges:
            if e.from_id == from_id and e.to_id == to_id:
                return e
        
        edge = WorldEdge(
            from_id=from_id,
            to_id=to_id,
            label=label,
            edge_type=edge_type,
            bidirectional=bidirectional,
            hidden=hidden,
            locked=locked,
            condition=condition
        )
        
        self.edges.append(edge)
        return edge
    
    def get_connections(self, node_id: str, include_hidden: bool = False) -> List[Dict[str, Any]]:
        """Ottieni tutte le connessioni da un nodo"""
        connections = []
        
        for edge in self.edges:
            target_id = None
            
            if edge.from_id == node_id:
                target_id = edge.to_id
            elif edge.bidirectional and edge.to_id == node_id:
                target_id = edge.from_id
            
            if target_id and (include_hidden or not edge.hidden):
                target = self.nodes.get(target_id)
                if target and target.discovered:
                    connections.append({
                        "node": target,
                        "edge": edge,
                        "accessible": not edge.locked
                    })
        
        return connections
    
    def lock_edge(self, from_id: str, to_id: str):
        for e in self.edges:
            if (e.from_id == from_id and e.to_id == to_id) or \
               (e.bidirectional and e.from_id == to_id and e.to_id == from_id):
                e.locked = True
    
    def unlock_edge(self, from_id: str, to_id: str):
        for e in self.edges:
            if (e.from_id == from_id and e.to_id == to_id) or \
               (e.bidirectional and e.from_id == to_id and e.to_id == from_id):
                e.locked = False
    
    def reveal_edge(self, from_id: str, to_id: str):
        for e in self.edges:
            if (e.from_id == from_id and e.to_id == to_id) or \
               (e.bidirectional and e.from_id == to_id and e.to_id == from_id):
                e.hidden = False
    
    # ═══════════════════════════════════════
    # NAVIGATION
    # ═══════════════════════════════════════
    
    def move_to(self, node_id: str, force: bool = False) -> bool:
        """
        Muove il giocatore a un nodo.
        Verifica che ci sia una connessione valida (a meno che force=True).
        """
        if node_id not in self.nodes:
            return False
        
        target = self.nodes[node_id]
        
        # Se force, muovi direttamente
        if force:
            self._enter_node(node_id)
            return True
        
        # Verifica connessione
        if self.current_node_id:
            connections = self.get_connections(self.current_node_id)
            valid = any(c["node"].id == node_id and c["accessible"] for c in connections)
            if not valid:
                return False
        
        self._enter_node(node_id)
        return True
    
    def _enter_node(self, node_id: str):
        """Entra in un nodo (aggiorna stato)"""
        node = self.nodes[node_id]
        node.visited = True
        node.discovered = True
        now = datetime.now().isoformat()
        if not node.first_visited:
            node.first_visited = now
        node.last_visited = now
        self.current_node_id = node_id
    
    def enter_child(self, child_id: str) -> bool:
        """Entra in un figlio del nodo corrente (zoom in)"""
        if not self.current_node_id:
            return False
        children = self.get_children(self.current_node_id)
        if any(c.id == child_id for c in children):
            return self.move_to(child_id, force=True)
        return False
    
    def exit_to_parent(self) -> bool:
        """Torna al parent (zoom out)"""
        if not self.current_node_id:
            return False
        current = self.nodes[self.current_node_id]
        if current.parent_id:
            return self.move_to(current.parent_id, force=True)
        return False
    
    def get_current_node(self) -> Optional[WorldNode]:
        if self.current_node_id:
            return self.nodes.get(self.current_node_id)
        return None
    
    # ═══════════════════════════════════════
    # CONTEXT FOR GM
    # ═══════════════════════════════════════
    
    def get_context_for_gm(self) -> str:
        """Genera contesto spaziale per il system prompt del GM"""
        lines = []
        
        current = self.get_current_node()
        if not current:
            lines.append("POSIZIONE: Il personaggio non ha ancora una posizione definita.")
            lines.append("Usa i tag per creare la location iniziale.")
            return "\n".join(lines)
        
        # Breadcrumb
        breadcrumb = self.get_breadcrumb(current.id)
        path = " > ".join([n.name for n in breadcrumb])
        lines.append(f"POSIZIONE ATTUALE: {path}")
        lines.append(f"- Tipo: {current.node_type}")
        lines.append(f"- Descrizione: {current.description}")
        if current.tags:
            lines.append(f"- Tags: {', '.join(current.tags)}")
        
        # Figli (luoghi esplorabili dentro)
        children = self.get_children(current.id)
        if children:
            lines.append(f"\nLUOGHI ALL'INTERNO ({len(children)}):")
            for child in children:
                status = "✓" if child.visited else "○"
                lines.append(f"  {status} {child.name} [{child.node_type}]")
        
        # Connessioni orizzontali (fratelli raggiungibili)
        connections = self.get_connections(current.id)
        if connections:
            lines.append(f"\nCONNESSIONI ({len(connections)}):")
            for conn in connections:
                node = conn["node"]
                edge = conn["edge"]
                lock = "🔒" if edge.locked else ""
                label = f" ({edge.label})" if edge.label else ""
                lines.append(f"  → {node.name}{label} {lock}")
        
        # Parent (per uscire)
        if current.parent_id:
            parent = self.nodes.get(current.parent_id)
            if parent:
                lines.append(f"\nUSCITA: Torna a {parent.name}")
        
        return "\n".join(lines)
    
    # ═══════════════════════════════════════
    # SERIALIZATION
    # ═══════════════════════════════════════
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "current_node_id": self.current_node_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorldGraph':
        graph = cls()
        for node_data in data.get("nodes", {}).values():
            graph.nodes[node_data["id"]] = WorldNode.from_dict(node_data)
        for edge_data in data.get("edges", []):
            graph.edges.append(WorldEdge.from_dict(edge_data))
        graph.current_node_id = data.get("current_node_id")
        return graph
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WorldGraph':
        return cls.from_dict(json.loads(json_str))


# ═══════════════════════════════════════════════════════════════
# WORLD MANAGER (singleton per gestione file)
# ═══════════════════════════════════════════════════════════════

class WorldManager:
    """Gestisce il salvataggio/caricamento dei grafi mondo per personaggio"""
    
    _instance = None
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), 'data', 'worlds')
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._graphs: Dict[str, WorldGraph] = {}
    
    def _get_path(self, character_id: str) -> str:
        return os.path.join(self.data_dir, f"{character_id}_world.json")
    
    def get_graph(self, character_id: str) -> WorldGraph:
        """Ottieni o crea il grafo mondo per un personaggio"""
        if character_id not in self._graphs:
            path = self._get_path(character_id)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self._graphs[character_id] = WorldGraph.from_json(f.read())
            else:
                self._graphs[character_id] = WorldGraph()
        return self._graphs[character_id]
    
    def save_graph(self, character_id: str):
        """Salva il grafo su file"""
        if character_id in self._graphs:
            path = self._get_path(character_id)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._graphs[character_id].to_json())
    
    def delete_graph(self, character_id: str):
        """Elimina il grafo di un personaggio"""
        if character_id in self._graphs:
            del self._graphs[character_id]
        path = self._get_path(character_id)
        if os.path.exists(path):
            os.remove(path)


def get_world_manager() -> WorldManager:
    """Singleton per il WorldManager"""
    if WorldManager._instance is None:
        WorldManager._instance = WorldManager()
    return WorldManager._instance
