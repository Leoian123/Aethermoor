"""
Blueprint: Quest e Journal (quests, notes, journal CRUD).
"""

from flask import Blueprint, request, jsonify

from auth import require_auth
from helpers import verify_ownership
from db.mock_db import db

quest_bp = Blueprint('quest', __name__, url_prefix='/api/character')


@quest_bp.route('/<character_id>/quests', methods=['GET'])
@require_auth
def get_character_quests(character_id):
    """Ottieni quest attive e storico per il journal."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    active = db.get_character_active_quests(character_id)
    history = db.get_character_quest_history(character_id, limit=20)

    return jsonify({
        'active': active,
        'history': history,
    })


@quest_bp.route('/<character_id>/quests/<quest_id>/notes', methods=['PATCH'])
@require_auth
def update_quest_notes(character_id, quest_id):
    """Aggiorna le note del giocatore su una quest."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    data = request.get_json()
    if not data or 'notes' not in data:
        return jsonify({'error': 'Campo notes richiesto'}), 400

    # Verifica che la quest appartenga al personaggio
    cq = db.get_by_id('character_quests', quest_id)
    if not cq or cq.get('character_id') != character_id:
        return jsonify({'error': 'Quest non trovata'}), 404

    updated = db.update('character_quests', quest_id, {
        'player_notes': data['notes']
    })

    return jsonify({'success': True, 'quest_id': quest_id})


@quest_bp.route('/<character_id>/journal-notes', methods=['GET'])
@require_auth
def get_journal_notes(character_id):
    """Ottieni le note generali del diario."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    notes = db.get_journal_notes(character_id)
    return jsonify({'notes': notes})


@quest_bp.route('/<character_id>/journal-notes', methods=['POST'])
@require_auth
def save_journal_note(character_id):
    """Salva una nota del diario (crea o aggiorna)."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Campo content richiesto'}), 400

    note = db.save_journal_note(
        character_id,
        data['content'],
        note_id=data.get('id')
    )

    return jsonify({'success': True, 'note': note})


@quest_bp.route('/<character_id>/journal-notes/<note_id>', methods=['DELETE'])
@require_auth
def delete_journal_note(character_id, note_id):
    """Elimina una nota del diario."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    success = db.delete_journal_note(character_id, note_id)
    if not success:
        return jsonify({'error': 'Nota non trovata'}), 404

    return jsonify({'success': True})
