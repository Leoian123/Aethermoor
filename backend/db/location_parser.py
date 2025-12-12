# location_parser.py - Parser per i tag di location generati dall'AI
import re
from typing import List, Dict, Any, Optional
from .location_graph import LocationGraph, get_location_manager

# ═══════════════════════════════════════════════════════════════
# REGEX PATTERNS - FORMATO XML (preferito)
# ═══════════════════════════════════════════════════════════════

# Formato XML: <location_create id="..." name="..." tags="...">descrizione</location_create>
LOCATION_CREATE_XML = re.compile(
    r'<location_create\s+'
    r'id="([^"]+)"\s+'
    r'name="([^"]+)"'
    r'(?:\s+tags="([^"]*)")?'
    r'(?:\s+discovered="([^"]*)")?'
    r'\s*>'
    r'(.*?)'
    r'</location_create>',
    re.DOTALL | re.IGNORECASE
)

# Formato XML: <edge_create from="..." to="..." .../>
EDGE_CREATE_XML = re.compile(
    r'<edge_create\s+'
    r'from="([^"]+)"\s+'
    r'to="([^"]+)"'
    r'(?:\s+label="([^"]*)")?'
    r'(?:\s+bidirectional="([^"]*)")?'
    r'(?:\s+hidden="([^"]*)")?'
    r'(?:\s+locked="([^"]*)")?'
    r'(?:\s+condition="([^"]*)")?'
    r'\s*/?>',
    re.IGNORECASE
)

# Formato XML: <movement to="..."/>
MOVEMENT_XML = re.compile(
    r'<movement\s+to="([^"]+)"\s*/?>',
    re.IGNORECASE
)

# Formato XML: <edge_lock from="..." to="..."/>
EDGE_LOCK_XML = re.compile(r'<edge_lock\s+from="([^"]+)"\s+to="([^"]+)"\s*/?>', re.IGNORECASE)
EDGE_UNLOCK_XML = re.compile(r'<edge_unlock\s+from="([^"]+)"\s+to="([^"]+)"\s*/?>', re.IGNORECASE)
EDGE_REVEAL_XML = re.compile(r'<edge_reveal\s+from="([^"]+)"\s+to="([^"]+)"\s*/?>', re.IGNORECASE)
EDGE_HIDE_XML = re.compile(r'<edge_hide\s+from="([^"]+)"\s+to="([^"]+)"\s*/?>', re.IGNORECASE)

# Formato XML: <location_update id="..." add_tags="..." remove_tags="..."/>
LOCATION_UPDATE_XML = re.compile(
    r'<location_update\s+'
    r'id="([^"]+)"'
    r'(?:\s+add_tags="([^"]*)")?'
    r'(?:\s+remove_tags="([^"]*)")?'
    r'\s*/?>',
    re.IGNORECASE
)

# ═══════════════════════════════════════════════════════════════
# REGEX PATTERNS - FORMATO PARENTESI QUADRE (fallback per Haiku)
# ═══════════════════════════════════════════════════════════════

# [LOCATION_CREATE id="..." name="..." tags="..."] descrizione fino a fine riga o prossimo tag
LOCATION_CREATE_BRACKET = re.compile(
    r'\[LOCATION_CREATE\s+'
    r'id="([^"]+)"\s+'
    r'name="([^"]+)"'
    r'(?:\s+tags="([^"]*)")?'
    r'(?:\s+discovered="([^"]*)")?'
    r'\s*\]'
    r'([^\[]*)',
    re.IGNORECASE
)

# [EDGE_CREATE from="..." to="..." ...]
EDGE_CREATE_BRACKET = re.compile(
    r'\[EDGE_CREATE\s+'
    r'from="([^"]+)"\s+'
    r'to="([^"]+)"'
    r'(?:\s+label="([^"]*)")?'
    r'(?:\s+bidirectional="([^"]*)")?'
    r'(?:\s+hidden="([^"]*)")?'
    r'(?:\s+locked="([^"]*)")?'
    r'(?:\s+condition="([^"]*)")?'
    r'\s*\]',
    re.IGNORECASE
)

# [MOVEMENT to="..."]
MOVEMENT_BRACKET = re.compile(
    r'\[MOVEMENT\s+to="([^"]+)"\s*\]',
    re.IGNORECASE
)

# [EDGE_LOCK from="..." to="..."]
EDGE_LOCK_BRACKET = re.compile(r'\[EDGE_LOCK\s+from="([^"]+)"\s+to="([^"]+)"\s*\]', re.IGNORECASE)
EDGE_UNLOCK_BRACKET = re.compile(r'\[EDGE_UNLOCK\s+from="([^"]+)"\s+to="([^"]+)"\s*\]', re.IGNORECASE)
EDGE_REVEAL_BRACKET = re.compile(r'\[EDGE_REVEAL\s+from="([^"]+)"\s+to="([^"]+)"\s*\]', re.IGNORECASE)
EDGE_HIDE_BRACKET = re.compile(r'\[EDGE_HIDE\s+from="([^"]+)"\s+to="([^"]+)"\s*\]', re.IGNORECASE)

# [LOCATION_UPDATE id="..." add_tags="..." remove_tags="..."]
LOCATION_UPDATE_BRACKET = re.compile(
    r'\[LOCATION_UPDATE\s+'
    r'id="([^"]+)"'
    r'(?:\s+add_tags="([^"]*)")?'
    r'(?:\s+remove_tags="([^"]*)")?'
    r'\s*\]',
    re.IGNORECASE
)

# ═══════════════════════════════════════════════════════════════
# PARSING FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def parse_bool(value: str) -> bool:
    """Converte stringa in booleano"""
    if not value:
        return False
    return value.lower() in ('true', '1', 'yes', 'sì', 'si')


def parse_location_tags(text: str) -> List[Dict[str, Any]]:
    """
    Estrae tutti i tag di location da un testo.
    Supporta sia formato XML che parentesi quadre (fallback per Haiku).
    Ritorna lista di azioni da eseguire.
    """
    actions = []
    
    # ═══════════════════════════════════════
    # 1. Location Create (XML + Bracket)
    # ═══════════════════════════════════════
    for match in LOCATION_CREATE_XML.finditer(text):
        loc_id, name, tags_str, discovered, description = match.groups()
        tags = [t.strip() for t in (tags_str or "").split(",") if t.strip()]
        actions.append({
            "type": "location_create",
            "id": loc_id,
            "name": name,
            "tags": tags,
            "description": description.strip() if description else "",
            "discovered": parse_bool(discovered) if discovered else True
        })
    
    for match in LOCATION_CREATE_BRACKET.finditer(text):
        loc_id, name, tags_str, discovered, description = match.groups()
        # Evita duplicati se già trovato in XML
        if any(a["type"] == "location_create" and a["id"] == loc_id for a in actions):
            continue
        tags = [t.strip() for t in (tags_str or "").split(",") if t.strip()]
        actions.append({
            "type": "location_create",
            "id": loc_id,
            "name": name,
            "tags": tags,
            "description": description.strip() if description else "",
            "discovered": parse_bool(discovered) if discovered else True
        })
    
    # ═══════════════════════════════════════
    # 2. Edge Create (XML + Bracket)
    # ═══════════════════════════════════════
    for match in EDGE_CREATE_XML.finditer(text):
        from_id, to_id, label, bidir, hidden, locked, condition = match.groups()
        actions.append({
            "type": "edge_create",
            "from_id": from_id,
            "to_id": to_id,
            "label": label or "",
            "bidirectional": parse_bool(bidir) if bidir else True,
            "hidden": parse_bool(hidden),
            "locked": parse_bool(locked),
            "condition": condition or ""
        })
    
    for match in EDGE_CREATE_BRACKET.finditer(text):
        from_id, to_id, label, bidir, hidden, locked, condition = match.groups()
        # Evita duplicati
        if any(a["type"] == "edge_create" and a["from_id"] == from_id and a["to_id"] == to_id for a in actions):
            continue
        actions.append({
            "type": "edge_create",
            "from_id": from_id,
            "to_id": to_id,
            "label": label or "",
            "bidirectional": parse_bool(bidir) if bidir else True,
            "hidden": parse_bool(hidden),
            "locked": parse_bool(locked),
            "condition": condition or ""
        })
    
    # ═══════════════════════════════════════
    # 3. Movement (XML + Bracket)
    # ═══════════════════════════════════════
    for match in MOVEMENT_XML.finditer(text):
        to_id = match.group(1)
        actions.append({"type": "movement", "to_id": to_id})
    
    for match in MOVEMENT_BRACKET.finditer(text):
        to_id = match.group(1)
        if any(a["type"] == "movement" and a["to_id"] == to_id for a in actions):
            continue
        actions.append({"type": "movement", "to_id": to_id})
    
    # ═══════════════════════════════════════
    # 4. Edge modifications (XML + Bracket)
    # ═══════════════════════════════════════
    for pattern, action_type in [
        (EDGE_LOCK_XML, "edge_lock"),
        (EDGE_LOCK_BRACKET, "edge_lock"),
        (EDGE_UNLOCK_XML, "edge_unlock"),
        (EDGE_UNLOCK_BRACKET, "edge_unlock"),
        (EDGE_REVEAL_XML, "edge_reveal"),
        (EDGE_REVEAL_BRACKET, "edge_reveal"),
        (EDGE_HIDE_XML, "edge_hide"),
        (EDGE_HIDE_BRACKET, "edge_hide"),
    ]:
        for match in pattern.finditer(text):
            action = {"type": action_type, "from_id": match.group(1), "to_id": match.group(2)}
            # Evita duplicati
            if action not in actions:
                actions.append(action)
    
    # ═══════════════════════════════════════
    # 5. Location Update (XML + Bracket)
    # ═══════════════════════════════════════
    for pattern in [LOCATION_UPDATE_XML, LOCATION_UPDATE_BRACKET]:
        for match in pattern.finditer(text):
            loc_id, add_tags_str, remove_tags_str = match.groups()
            # Evita duplicati
            if any(a["type"] == "location_update" and a["id"] == loc_id for a in actions):
                continue
            add_tags = [t.strip() for t in (add_tags_str or "").split(",") if t.strip()]
            remove_tags = [t.strip() for t in (remove_tags_str or "").split(",") if t.strip()]
            if add_tags or remove_tags:
                actions.append({
                    "type": "location_update",
                    "id": loc_id,
                    "add_tags": add_tags,
                    "remove_tags": remove_tags
                })
    
    return actions


def apply_location_actions(character_id: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Applica le azioni di location al grafo del personaggio.
    Ritorna un report delle modifiche.
    """
    manager = get_location_manager()
    graph = manager.get_graph(character_id)
    
    report = {
        "locations_created": [],
        "edges_created": [],
        "movements": [],
        "modifications": [],
        "errors": []
    }
    
    for action in actions:
        try:
            action_type = action["type"]
            
            if action_type == "location_create":
                node = graph.create_location(
                    id=action["id"],
                    name=action["name"],
                    description=action.get("description", ""),
                    tags=action.get("tags", [])
                )
                if action.get("discovered"):
                    node.discovered = True
                report["locations_created"].append(action["id"])
            
            elif action_type == "edge_create":
                edge = graph.create_edge(
                    from_id=action["from_id"],
                    to_id=action["to_id"],
                    label=action.get("label", ""),
                    bidirectional=action.get("bidirectional", True),
                    hidden=action.get("hidden", False),
                    locked=action.get("locked", False),
                    condition=action.get("condition", "")
                )
                if edge:
                    report["edges_created"].append(f"{action['from_id']} -> {action['to_id']}")
                else:
                    report["errors"].append(f"Edge non creato: location non esistente")
            
            elif action_type == "movement":
                success = graph.move_to(action["to_id"])
                if success:
                    report["movements"].append(action["to_id"])
                else:
                    report["errors"].append(f"Movimento fallito: {action['to_id']}")
            
            elif action_type == "edge_lock":
                graph.lock_edge(action["from_id"], action["to_id"])
                report["modifications"].append(f"Locked: {action['from_id']} -> {action['to_id']}")
            
            elif action_type == "edge_unlock":
                graph.unlock_edge(action["from_id"], action["to_id"])
                report["modifications"].append(f"Unlocked: {action['from_id']} -> {action['to_id']}")
            
            elif action_type == "edge_reveal":
                graph.reveal_edge(action["from_id"], action["to_id"])
                report["modifications"].append(f"Revealed: {action['from_id']} -> {action['to_id']}")
            
            elif action_type == "edge_hide":
                graph.hide_edge(action["from_id"], action["to_id"])
                report["modifications"].append(f"Hidden: {action['from_id']} -> {action['to_id']}")
            
            elif action_type == "location_update":
                node = graph.update_location(
                    id=action["id"],
                    add_tags=action.get("add_tags"),
                    remove_tags=action.get("remove_tags")
                )
                if node:
                    report["modifications"].append(f"Updated: {action['id']}")
        
        except Exception as e:
            report["errors"].append(f"Errore in {action_type}: {str(e)}")
    
    # Salva il grafo
    manager.save_graph(character_id)
    
    return report


def process_gm_response(character_id: str, gm_response: str) -> Dict[str, Any]:
    """
    Processa la risposta del GM ed estrae/applica i tag di location.
    Ritorna il report delle modifiche.
    """
    actions = parse_location_tags(gm_response)
    if actions:
        return apply_location_actions(character_id, actions)
    return {"locations_created": [], "edges_created": [], "movements": [], "modifications": [], "errors": []}


def strip_location_tags(text: str) -> str:
    """Rimuove i tag di location dal testo per la visualizzazione"""
    # Rimuovi tutti i tag XML di location
    text = LOCATION_CREATE_XML.sub('', text)
    text = EDGE_CREATE_XML.sub('', text)
    text = MOVEMENT_XML.sub('', text)
    text = EDGE_LOCK_XML.sub('', text)
    text = EDGE_UNLOCK_XML.sub('', text)
    text = EDGE_REVEAL_XML.sub('', text)
    text = EDGE_HIDE_XML.sub('', text)
    text = LOCATION_UPDATE_XML.sub('', text)
    
    # Rimuovi tutti i tag formato parentesi quadre
    text = LOCATION_CREATE_BRACKET.sub('', text)
    text = EDGE_CREATE_BRACKET.sub('', text)
    text = MOVEMENT_BRACKET.sub('', text)
    text = EDGE_LOCK_BRACKET.sub('', text)
    text = EDGE_UNLOCK_BRACKET.sub('', text)
    text = EDGE_REVEAL_BRACKET.sub('', text)
    text = EDGE_HIDE_BRACKET.sub('', text)
    text = LOCATION_UPDATE_BRACKET.sub('', text)
    
    # Pulisci linee vuote multiple
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════
# HELPER per generare context per il GM
# ═══════════════════════════════════════════════════════════════

def get_spatial_context(character_id: str) -> str:
    """
    Genera il contesto spaziale per il system prompt del GM.
    """
    manager = get_location_manager()
    graph = manager.get_graph(character_id)
    return graph.get_context_for_gm()


def get_current_location_info(character_id: str) -> Optional[Dict[str, Any]]:
    """
    Ottiene informazioni sulla location corrente.
    """
    manager = get_location_manager()
    graph = manager.get_graph(character_id)
    
    current = graph.get_current_location()
    if not current:
        return None
    
    exits = graph.get_visible_exits()
    
    return {
        "id": current.id,
        "name": current.name,
        "description": current.description,
        "tags": list(current.tags),
        "exits": exits,
        "npcs": current.npcs,
        "items": current.items
    }
