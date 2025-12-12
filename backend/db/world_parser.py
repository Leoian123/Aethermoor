# world_parser.py - Parser tag movimento e creazione procedurale
"""
Gestisce i tag di movimento e creazione dal GM.
Il parser VALIDA ogni movimento contro il world_manager.
"""

import re
from typing import List, Dict, Any, Optional
from .player_state import get_player_state_manager
from .world_manager import get_world_manager


# ═══════════════════════════════════════════════════════════════
# REGEX PATTERNS - Tag di movimento e creazione
# ═══════════════════════════════════════════════════════════════

# Movimento a sublocation: <move to="albachiara.locanda_orso"/>
MOVE_PATTERN = re.compile(
    r'<move\s+to="([^"]+)"\s*/?>',
    re.IGNORECASE
)
MOVE_BRACKET = re.compile(
    r'\[MOVE\s+to="([^"]+)"\s*\]',
    re.IGNORECASE
)

# Entra in figlio: <enter to="albachiara.locanda_orso.cantina"/>
ENTER_PATTERN = re.compile(
    r'<enter\s+to="([^"]+)"\s*/?>',
    re.IGNORECASE
)
ENTER_BRACKET = re.compile(
    r'\[ENTER\s+to="([^"]+)"\s*\]',
    re.IGNORECASE
)

# Esci al parent: <exit/>
EXIT_PATTERN = re.compile(
    r'<exit\s*/?>',
    re.IGNORECASE
)
EXIT_BRACKET = re.compile(
    r'\[EXIT\s*\]',
    re.IGNORECASE
)

# Crea sublocation procedurale: <create_sublocation id="..." name="..." type="...">descrizione</create_sublocation>
CREATE_SUBLOC_PATTERN = re.compile(
    r'<create_sublocation\s+'
    r'id="([^"]+)"\s+'
    r'name="([^"]+)"'
    r'(?:\s+type="([^"]*)")?'
    r'(?:\s+tags="([^"]*)")?'
    r'\s*>'
    r'(.*?)'
    r'</create_sublocation>',
    re.DOTALL | re.IGNORECASE
)
CREATE_SUBLOC_BRACKET = re.compile(
    r'\[CREATE_SUBLOCATION\s+'
    r'id="([^"]+)"\s+'
    r'name="([^"]+)"'
    r'(?:\s+type="([^"]*)")?'
    r'(?:\s+tags="([^"]*)")?'
    r'\s*\]'
    r'([^\[]*)',
    re.IGNORECASE
)

# NPC disposition change: <npc_disposition id="oste_bruno" value="friendly"/>
NPC_DISPOSITION_PATTERN = re.compile(
    r'<npc_disposition\s+id="([^"]+)"\s+value="([^"]+)"\s*/?>',
    re.IGNORECASE
)
NPC_DISPOSITION_BRACKET = re.compile(
    r'\[NPC_DISPOSITION\s+id="([^"]+)"\s+value="([^"]+)"\s*\]',
    re.IGNORECASE
)

# Lista di tutti i pattern per strip
ALL_PATTERNS = [
    MOVE_PATTERN, MOVE_BRACKET,
    ENTER_PATTERN, ENTER_BRACKET,
    EXIT_PATTERN, EXIT_BRACKET,
    CREATE_SUBLOC_PATTERN, CREATE_SUBLOC_BRACKET,
    NPC_DISPOSITION_PATTERN, NPC_DISPOSITION_BRACKET,
]


# ═══════════════════════════════════════════════════════════════
# PARSING
# ═══════════════════════════════════════════════════════════════

def parse_gm_tags(text: str) -> List[Dict[str, Any]]:
    """
    Estrae tutti i tag di azione dal testo del GM.
    """
    actions = []
    found = set()
    
    # MOVE
    for pattern in [MOVE_PATTERN, MOVE_BRACKET]:
        for match in pattern.finditer(text):
            target = match.group(1)
            key = f"move:{target}"
            if key not in found:
                found.add(key)
                actions.append({"type": "move", "target": target})
    
    # ENTER
    for pattern in [ENTER_PATTERN, ENTER_BRACKET]:
        for match in pattern.finditer(text):
            target = match.group(1)
            key = f"enter:{target}"
            if key not in found:
                found.add(key)
                actions.append({"type": "enter", "target": target})
    
    # EXIT
    for pattern in [EXIT_PATTERN, EXIT_BRACKET]:
        if pattern.search(text) and "exit" not in found:
            found.add("exit")
            actions.append({"type": "exit"})
    
    # CREATE_SUBLOCATION
    for pattern in [CREATE_SUBLOC_PATTERN, CREATE_SUBLOC_BRACKET]:
        for match in pattern.finditer(text):
            subloc_id, name, subloc_type, tags_str, description = match.groups()
            key = f"create:{subloc_id}"
            if key not in found:
                found.add(key)
                tags = [t.strip() for t in (tags_str or "").split(",") if t.strip()]
                actions.append({
                    "type": "create_sublocation",
                    "id": subloc_id,
                    "name": name,
                    "subloc_type": subloc_type or "room",
                    "tags": tags,
                    "description": (description or "").strip()
                })
    
    # NPC_DISPOSITION
    for pattern in [NPC_DISPOSITION_PATTERN, NPC_DISPOSITION_BRACKET]:
        for match in pattern.finditer(text):
            npc_id, value = match.groups()
            key = f"disposition:{npc_id}"
            if key not in found:
                found.add(key)
                actions.append({
                    "type": "npc_disposition",
                    "npc_id": npc_id,
                    "value": value
                })
    
    return actions


def apply_gm_actions(character_id: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Applica le azioni estratte dal GM.
    Ogni azione viene VALIDATA prima di essere applicata.
    """
    state_mgr = get_player_state_manager()
    world_mgr = get_world_manager()
    state = state_mgr.get_state(character_id)
    
    report = {
        "movements": [],
        "created": [],
        "disposition_changes": [],
        "errors": []
    }
    
    for action in actions:
        try:
            action_type = action["type"]
            
            if action_type in ("move", "enter"):
                target = action["target"]
                valid, error, new_pos = world_mgr.validate_movement(state, target)
                
                if valid:
                    state_mgr.move_player(
                        character_id,
                        sublocation_id=new_pos.get("sublocation_id", "")
                    )
                    report["movements"].append({
                        "to": target,
                        "success": True
                    })
                else:
                    report["errors"].append(f"Movimento a {target} fallito: {error}")
            
            elif action_type == "exit":
                current_subloc = state.position.sublocation_id
                if not current_subloc:
                    report["errors"].append("Non sei in una sublocation, non puoi uscire")
                    continue
                
                # Trova il parent
                subloc = world_mgr.get_sublocation(current_subloc, state)
                if subloc:
                    parent_id = subloc.get("parent_id", "")
                    if parent_id == state.position.location_id:
                        # Esci alla location
                        state_mgr.move_player(character_id, sublocation_id="")
                    else:
                        # Esci al parent sublocation
                        state_mgr.move_player(character_id, sublocation_id=parent_id)
                    report["movements"].append({
                        "to": parent_id or state.position.location_id,
                        "success": True,
                        "action": "exit"
                    })
            
            elif action_type == "create_sublocation":
                subloc_id = action["id"]
                
                # Valida che sia figlia della location corrente
                if not subloc_id.startswith(state.position.location_id + "."):
                    report["errors"].append(
                        f"Sublocation {subloc_id} deve iniziare con {state.position.location_id}."
                    )
                    continue
                
                # Determina il parent
                parts = subloc_id.split(".")
                if len(parts) == 2:
                    parent_id = state.position.location_id
                else:
                    parent_id = ".".join(parts[:-1])
                
                # Crea la sublocation procedurale
                subloc_data = {
                    "id": subloc_id,
                    "parent_id": parent_id,
                    "name": action["name"],
                    "description": action.get("description", ""),
                    "type": action.get("subloc_type", "room"),
                    "tags": action.get("tags", []),
                    "exits": {parent_id: f"torna a {parent_id.split('.')[-1]}"},
                    "npcs_here": [],
                    "children": [],
                    "_procedural": True
                }
                
                state.add_procedural_sublocation(subloc_id, subloc_data)
                
                # Aggiungi come figlio al parent se è una sublocation
                if parent_id != state.position.location_id:
                    parent_subloc = world_mgr.get_sublocation(parent_id, state)
                    if parent_subloc and parent_subloc.get("_procedural"):
                        if "children" not in parent_subloc:
                            parent_subloc["children"] = []
                        if subloc_id not in parent_subloc["children"]:
                            parent_subloc["children"].append(subloc_id)
                
                state_mgr.save_state(character_id)
                report["created"].append({
                    "id": subloc_id,
                    "name": action["name"],
                    "parent": parent_id
                })
            
            elif action_type == "npc_disposition":
                npc_id = action["npc_id"]
                value = action["value"]
                state.set_npc_disposition(npc_id, value)
                state_mgr.save_state(character_id)
                report["disposition_changes"].append({
                    "npc_id": npc_id,
                    "new_value": value
                })
        
        except Exception as e:
            report["errors"].append(f"Errore in {action_type}: {str(e)}")
    
    return report


def process_gm_response(character_id: str, gm_response: str) -> Dict[str, Any]:
    """
    Processa la risposta del GM: estrae e applica i tag.
    """
    actions = parse_gm_tags(gm_response)
    if actions:
        report = apply_gm_actions(character_id, actions)
    else:
        report = {"movements": [], "created": [], "disposition_changes": [], "errors": []}
    
    # Aggiungi alias per compatibilità frontend
    report["locations_created"] = report.get("created", [])
    report["modifications"] = report.get("disposition_changes", [])
    
    return report


def strip_gm_tags(text: str) -> str:
    """Rimuove tutti i tag GM dal testo per visualizzazione"""
    for pattern in ALL_PATTERNS:
        text = pattern.sub('', text)
    
    # Pulisci spazi multipli
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def get_spatial_context(character_id: str) -> str:
    """Genera contesto spaziale per il GM"""
    world_mgr = get_world_manager()
    return world_mgr.get_context_for_gm(character_id)


def get_current_location_info(character_id: str) -> Optional[Dict[str, Any]]:
    """Ottiene info sulla posizione corrente per API"""
    world_mgr = get_world_manager()
    return world_mgr.get_location_info_for_api(character_id)
