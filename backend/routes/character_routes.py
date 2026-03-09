"""
Blueprint: Character CRUD, slots, stats investment, skills.
"""

from flask import Blueprint, request, jsonify, g, current_app

from auth import require_auth
from helpers import verify_ownership
from db.mock_db import db

character_bp = Blueprint('character', __name__, url_prefix='/api')


@character_bp.route('/character/slot/<int:slot>', methods=['GET'])
@require_auth
def get_character_by_slot(slot):
    """Ottieni personaggio per slot (0-5), filtrato per utente."""
    char = db.get_character_by_slot_for_user(g.user_id, slot)
    if not char:
        return jsonify({'exists': False, 'slot': slot})

    full_char = db.get_character_full(char['id'])
    return jsonify({
        'exists': True,
        'character': full_char
    })


@character_bp.route('/character', methods=['POST'])
@require_auth
def create_character():
    """Crea un nuovo personaggio per l'utente autenticato."""
    data = request.json

    # Validazione
    required = ['slot', 'name', 'class_id']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Campo mancante: {field}'}), 400

    # Limite 6 personaggi per utente
    if db.count_characters_for_user(g.user_id) >= 6:
        return jsonify({'error': 'Limite di 6 personaggi raggiunto'}), 400

    # Verifica slot libero per QUESTO utente
    existing = db.get_character_by_slot_for_user(g.user_id, data['slot'])
    if existing:
        return jsonify({'error': 'Slot già occupato'}), 409

    # Verifica nome univoco (globale)
    name_check = db.get_where('characters', name=data['name'])
    if name_check:
        return jsonify({'error': 'Nome già in uso'}), 409

    # Valida stats (base 10 + 20 punti)
    str_stat = data.get('str', 10)
    dex_stat = data.get('dex', 10)
    vit_stat = data.get('vit', 10)
    int_stat = data.get('int', 10)

    total_points = (str_stat - 10) + (dex_stat - 10) + (vit_stat - 10) + (int_stat - 10)
    if total_points > 20:
        return jsonify({'error': 'Troppi punti assegnati (max 20 extra)'}), 400
    if any(s < 5 for s in [str_stat, dex_stat, vit_stat, int_stat]):
        return jsonify({'error': 'Stats minimo 5'}), 400

    try:
        character = db.create_character(
            user_id=g.user_id,
            slot=data['slot'],
            name=data['name'],
            class_id=data['class_id'],
            str_stat=str_stat,
            dex_stat=dex_stat,
            vit_stat=vit_stat,
            int_stat=int_stat
        )

        # Ritorna personaggio completo
        full_char = db.get_character_full(character['id'])
        return jsonify({
            'success': True,
            'character': full_char
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f'Create character error: {str(e)}')
        return jsonify({'error': 'Errore interno'}), 500


@character_bp.route('/character/<character_id>', methods=['GET'])
@require_auth
def get_character(character_id):
    """Ottieni personaggio per ID con tutti i dettagli."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    char = db.get_character_full(character_id)
    return jsonify(char)


@character_bp.route('/character/<character_id>', methods=['PUT'])
@require_auth
def update_character(character_id):
    """Aggiorna personaggio (HP, mana, XP, etc.)."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json

    allowed = ['hp_current', 'mana_current', 'xp', 'level']
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({'error': 'Nessun campo valido da aggiornare'}), 400

    updated = db.update('characters', character_id, updates)
    if not updated:
        return jsonify({'error': 'Personaggio non trovato'}), 404

    return jsonify(updated)


@character_bp.route('/character/<character_id>', methods=['DELETE'])
@require_auth
def delete_character(character_id):
    """Elimina personaggio e tutte le sue relazioni."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    success = db.delete_character(character_id)
    if not success:
        return jsonify({'error': 'Personaggio non trovato'}), 404
    return jsonify({'success': True})


@character_bp.route('/character/<character_id>/invest-stats', methods=['POST'])
@require_auth
def invest_stats(character_id):
    """Investe punti liberi da level-up nelle stats base."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    from stats import STAT_KEYS, empty_stat_bonuses, compute_invest_points_available

    data = request.json
    if not data:
        return jsonify({'error': 'Nessun dato fornito'}), 400

    char = db.get_by_id('characters', character_id)
    if not char:
        return jsonify({'error': 'Personaggio non trovato'}), 404

    bonuses = char.get('stat_bonuses', empty_stat_bonuses())
    available = compute_invest_points_available(char.get('level', 1), bonuses)

    # Valida: solo stat keys validi, tutti positivi
    points_to_spend = {}
    total_spending = 0
    for key in STAT_KEYS:
        val = data.get(key, 0)
        if not isinstance(val, int) or val < 0:
            return jsonify({'error': f'Valore non valido per {key}'}), 400
        if val > 0:
            points_to_spend[key] = val
            total_spending += val

    if total_spending == 0:
        return jsonify({'error': 'Nessun punto da investire'}), 400

    if total_spending > available:
        return jsonify({
            'error': f'Punti insufficienti: {total_spending} richiesti, {available} disponibili'
        }), 400

    # Applica investimento
    for key, val in points_to_spend.items():
        bonuses['invested'][key] = bonuses['invested'].get(key, 0) + val

    db.update_character_fields(character_id, {'stat_bonuses': bonuses})

    # Ritorna personaggio aggiornato con derivate ricalcolate
    full_char = db.get_character_full(character_id)
    return jsonify({
        'success': True,
        'character': full_char,
        'points_spent': total_spending,
        'points_remaining': available - total_spending
    })


@character_bp.route('/character/<character_id>/skill', methods=['POST'])
@require_auth
def add_skill_to_character(character_id):
    """Aggiunge una skill al personaggio."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    skill_id = data.get('skill_id')
    mastery = data.get('mastery', 1)

    if not skill_id:
        return jsonify({'error': 'skill_id richiesto'}), 400

    result = db.add_character_skill(character_id, skill_id, mastery)
    return jsonify(result)


@character_bp.route('/character/<character_id>/skill/<skill_tag>', methods=['PATCH'])
@require_auth
def update_skill_mastery(character_id, skill_tag):
    """Aggiorna mastery di una skill."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    delta = data.get('delta', 1)

    result = db.update_skill_mastery(character_id, skill_tag, delta)
    if not result:
        return jsonify({'error': 'Skill non trovata o non posseduta'}), 404

    return jsonify(result)


@character_bp.route('/slots', methods=['GET'])
@require_auth
def get_all_slots():
    """Ottieni stato di tutti gli slot per l'utente autenticato."""
    user_chars = db.get_all_slots_for_user(g.user_id)

    # Mappa slot -> personaggio
    slot_map = {}
    for char in user_chars:
        slot_map[char['slot']] = char

    slots = []
    for i in range(6):
        char = slot_map.get(i)
        if char:
            char_class = db.get_by_id('classes', char['class_id'])
            slots.append({
                'slot': i,
                'exists': True,
                'id': char['id'],
                'name': char['name'],
                'class_name': char_class['name'] if char_class else 'Unknown',
                'level': char['level']
            })
        else:
            slots.append({
                'slot': i,
                'exists': False
            })
    return jsonify(slots)
