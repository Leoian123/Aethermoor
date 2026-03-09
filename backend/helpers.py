"""
Helper functions condivise tra i blueprint.

Estratte da app.py per Single Responsibility.
"""

import re
from flask import current_app, g

from db.mock_db import db
from db.world_manager import get_spatial_context
from db.player_state import get_player_state_manager
from system_prompt import SYSTEM_PROMPT_CORE, SPHERE_LORE, FIRST_SESSION


# ═══════════════════════════════════════════════════════════════════════════════
# SANITIZZAZIONE INPUT
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern per tag meccanici: [TAG: valore | param: valore]
_TAG_PATTERN = re.compile(r'\[[A-Z_]+\s*:[^\]]*\]')

# Pattern per tag spaziali XML: <move .../>, <exit/>, <create_sublocation ...>...</create_sublocation>
_XML_TAG_PATTERN = re.compile(
    r'<\/?\s*(?:move|enter|exit|create_sublocation|npc_disposition)\b[^>]*>',
    re.IGNORECASE,
)

# Context type validi per l'endpoint expand
VALID_CONTEXT_TYPES = frozenset({
    'general', 'combat', 'dialogue', 'exploration', 'magic', 'lore',
})


def sanitize_user_message(message: str) -> str:
    """Rimuove tag meccanici e spaziali dal messaggio utente.

    Difesa in profondità: impedisce al giocatore di iniettare tag
    che potrebbero influenzare il GM o essere echeggiati nella risposta.
    """
    sanitized = _TAG_PATTERN.sub('', message)
    sanitized = _XML_TAG_PATTERN.sub('', sanitized)
    # Pulisci spazi multipli residui
    sanitized = re.sub(r'  +', ' ', sanitized)
    return sanitized.strip()


def sanitize_history(history: list) -> list:
    """Valida e sanitizza la chat history proveniente dal client.

    - Solo role 'user' e 'assistant' ammessi
    - Tag meccanici/spaziali strippati dai messaggi 'user'
    - Messaggi vuoti scartati
    """
    sanitized = []
    for msg in history:
        role = msg.get('role', '')
        content = msg.get('content', '')

        if role not in ('user', 'assistant'):
            continue

        if role == 'user':
            content = sanitize_user_message(content)

        if content.strip():
            sanitized.append({'role': role, 'content': content})

    return sanitized


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSIZIONE SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

def build_system_prompt(
    character: dict,
    character_id: str = '',
    location_id: str = '',
) -> str:
    """Compone il system prompt iniettando solo i moduli necessari.

    Moduli condizionali:
    - SPHERE_LORE: se il personaggio è un magic user o ha punti sfera
    - FIRST_SESSION: se il personaggio è nuovo (lv.1, 0 XP)
    - Character context: stats, posizione, quest
    - Location recap: memoria delle visite precedenti
    """
    parts = [SYSTEM_PROMPT_CORE]

    # Sfere: solo per chi usa magia
    if _needs_sphere_lore(character):
        parts.append(SPHERE_LORE)

    # Prima sessione: solo per personaggi nuovi
    if _is_first_session(character):
        parts.append(FIRST_SESSION)

    # Contesto personaggio (stats, posizione, quest)
    char_context = build_character_context(character)
    if char_context:
        parts.append(char_context)

    # Recap location (memoria visite precedenti)
    if character_id and location_id:
        try:
            from db.location_memory import get_memory_manager
            memory_mgr = get_memory_manager()
            recap = memory_mgr.get_recap(character_id, location_id)
            if recap:
                parts.append(f"\n\n{recap}")
        except Exception:
            pass

    return '\n'.join(parts)


def _needs_sphere_lore(character: dict) -> bool:
    """Determina se includere il lore delle sfere."""
    if not character:
        return False

    # Classi magiche
    class_info = character.get('class', {})
    class_name = (
        class_info.get('name', '')
        if isinstance(class_info, dict)
        else str(class_info)
    )
    if class_name.lower() in ('mage', 'mago', 'priest', 'sacerdote'):
        return True

    # Ha punti in qualche sfera
    spheres = character.get('spheres', {})
    return any(v and v > 0 for v in spheres.values())


def _is_first_session(character: dict) -> bool:
    """Determina se è la prima sessione del personaggio."""
    if not character:
        return False
    return character.get('level', 1) == 1 and character.get('xp', 0) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# OWNERSHIP
# ═══════════════════════════════════════════════════════════════════════════════

def verify_ownership(character_id: str):
    """Verifica che il personaggio appartenga all'utente autenticato.
    Ritorna il character dict o None (per evitare info leak)."""
    char = db.get_by_id('characters', character_id)
    if not char or char.get('user_id') != g.user_id:
        return None
    return char


# ═══════════════════════════════════════════════════════════════════════════════
# CONTESTO PERSONAGGIO
# ═══════════════════════════════════════════════════════════════════════════════

def build_character_context(character: dict) -> str:
    """Costruisce il contesto personaggio per il prompt.

    Legge lo stato canonico da MockDB (source of truth).
    Include stats totali e le 14 derivate.
    """
    if not character or not character.get('name'):
        return ''

    # Leggi stato canonico da DB
    char_id = character.get('id', '')
    if char_id:
        db_char = db.get_character_full(char_id)
        if db_char:
            character = db_char

    spheres = character.get('spheres', {})
    active_spheres = [f"{k}: {v}" for k, v in spheres.items() if v and v > 0]

    hp_current = character.get('hp_current', 100)
    hp_max = character.get('hp_max', 100)
    mana_current = character.get('mana_current', 50)
    mana_max = character.get('mana_max', 50)

    conditions = character.get('conditions', [])
    condition_names = [c.get('name', c) if isinstance(c, dict) else c for c in conditions]

    # Inventario: supporta sia oggetti dict che stringhe
    raw_inventory = character.get('inventory', [])
    inventory_names = [
        item.get('item_name', item) if isinstance(item, dict) else item
        for item in raw_inventory
    ]

    # Stats totali e derivate
    total = character.get('total_stats', {})
    d = character.get('derived', {})

    # Contesto spaziale
    spatial_context = ""
    if char_id:
        try:
            spatial_context = get_spatial_context(char_id)
            if spatial_context:
                spatial_context = f"\n\n[POSIZIONE NEL MONDO]\n{spatial_context}"
        except Exception:
            pass

    class_name = character.get('class', {}).get('name', 'Non definita') if isinstance(character.get('class'), dict) else character.get('class', 'Non definita')

    # ── Quest context ──
    quest_context = ""
    if char_id:
        try:
            active_quests = db.get_character_active_quests(char_id)
            if active_quests:
                lines = ["\n\n--- QUEST ATTIVE ---"]
                for aq in active_quests:
                    q = aq.get('quest', {})
                    lines.append(f"- {q.get('name', '?')} [{q.get('rarity', '?')}]")
                    for obj in aq.get('objectives_progress', []):
                        lines.append(f"  * {obj['description']}: {obj.get('current', 0)}/{obj.get('target', 1)}")
                quest_context += "\n".join(lines)

            recent_quests = db.get_character_quest_history(char_id, limit=5)
            if recent_quests:
                lines = ["\n\n--- QUEST RECENTI ---"]
                for rq in recent_quests:
                    q = rq.get('quest', {})
                    status_label = "Completata" if rq['status'] == 'completed' else "Fallita"
                    rewards = rq.get('rewards_received', {})
                    reward_parts = []
                    if rewards.get('corone'):
                        reward_parts.append(f"{rewards['corone']} corone")
                    if rewards.get('xp'):
                        reward_parts.append(f"{rewards['xp']} XP")
                    if rewards.get('items'):
                        reward_parts.append(f"items: {', '.join(rewards['items'])}")
                    reward_str = f" | Ricompense: {', '.join(reward_parts)}" if reward_parts else ""
                    lines.append(f"- {q.get('name', '?')} [{status_label}]{reward_str}")
                quest_context += "\n".join(lines)
        except Exception:
            pass

    corone = character.get('corone', 0)

    return f"""

[STATO ATTUALE PERSONAGGIO]
Nome: {character.get('name', 'Non definito')}
Classe: {class_name} | Livello: {character.get('level', 1)}
HP: {hp_current}/{hp_max} | Mana: {mana_current}/{mana_max} | Corone: {corone}
STR: {total.get('str', '?')} | DEX: {total.get('dex', '?')} | VIT: {total.get('vit', '?')} | INT: {total.get('int', '?')}
Danno Fisico: x{d.get('phys_dmg_mult', 1)} | Danno Magico: x{d.get('magic_dmg_mult', 1)}
Evasione: {d.get('evasion', 0)}% | Precisione: {d.get('precision', 60)}%
Attacchi/Turno: {d.get('attacks_per_turn', 1)} | Velocita': {d.get('move_speed', 100)}%
Carico max: {d.get('carry_max', 50)}kg
Regen HP: {d.get('hp_regen', 0)}/min | Res. Veleni: {d.get('poison_resist', 0)}% | Res. Elementi: {d.get('element_resist', 0)}%
Bonus EXP: {d.get('xp_bonus', 0)}% | Bonus Craft: {d.get('craft_bonus', 0)}%
Sfere: {', '.join(active_spheres) if active_spheres else 'Nessuna'}
Condizioni: {', '.join(condition_names) if condition_names else 'Nessuna'}
Inventario: {', '.join(inventory_names) if inventory_names else 'Vuoto'}{spatial_context}{quest_context}"""


def award_xp_direct(character_id: str, amount: int, reason: str = "generic") -> dict:
    """Assegna XP direttamente, senza passare per tag GM.

    Utile per: esplorazione, quest, eventi programmatici.
    Usa la stessa logica di apply_xp() (bonus INT, level-up, replenish).
    """
    from statisfy_tags.actions import XPAction
    from db.applicators.mechanical import MechanicalApplicator

    state_manager = get_player_state_manager()
    state = state_manager.load(character_id)
    applicator = MechanicalApplicator(
        state_manager=state_manager,
        character_id=character_id,
    )

    result = applicator.apply_xp(XPAction(amount=amount))
    applicator.save()

    # Sync a MockDB (xp e level)
    changes = {"xp": state.stats.get("xp", 0), "level": state.level}
    db.update_character_fields(character_id, changes)

    result["reason"] = reason
    current_app.logger.info(
        f"XP awarded: {amount} to {character_id} ({reason}) "
        f"→ effective={result['gained_effective']}, "
        f"level={result['old_level']}→{result['new_level']}"
    )

    return result


def extract_key_event(user_message: str, gm_response: str) -> str:
    """Estrae un evento chiave dalla conversazione per il riassunto.
    Semplificato: cerca tag significativi."""
    patterns = [
        (r'\[NPC:\s*([^\]]+)\]', lambda m: f"Incontrato {m.group(1).split('|')[0].strip()}"),
        (r'\[ITEM:\s*([^\]]+)\]', lambda m: f"Ottenuto {m.group(1)}"),
        (r'\[LORE:\s*([^\]]+)\]', lambda m: f"Scoperto {m.group(1).split('|')[0].strip()}"),
        (r'\[DMG:\s*(\d+)[^\]]*\|\s*target:\s*enemy', lambda m: f"Combattimento ({m.group(1)} danni inflitti)"),
        (r'\[SPELL:\s*success', lambda m: "Incantesimo riuscito"),
    ]

    for pattern, formatter in patterns:
        match = re.search(pattern, gm_response, re.IGNORECASE)
        if match:
            return formatter(match)

    return ""


def extract_tags_from_text(text: str) -> list:
    """Estrae tutti i tag [...] da un testo."""
    return re.findall(r'\[([A-Z_]+):[^\]]+\]', text)
