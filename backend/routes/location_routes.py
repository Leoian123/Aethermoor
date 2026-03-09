"""
Blueprint: Location e Mappa (switch, map, exits, visited, neighborhood).
"""

from flask import Blueprint, request, jsonify, current_app

from auth import require_auth
from helpers import verify_ownership, award_xp_direct

from db.world_manager import get_world_manager, get_current_location_info
from db.player_state import get_player_state_manager
from db.location_memory import get_memory_manager

location_bp = Blueprint('location', __name__, url_prefix='/api/character')


@location_bp.route('/<char_id>/switch-location', methods=['POST'])
@require_auth
def switch_location(char_id):
    """Gestisce il cambio di location."""
    if not verify_ownership(char_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    try:
        data = request.get_json()
        from_location = data.get('from_location', '')
        to_location = data.get('to_location', '')
        current_messages = data.get('messages', [])

        if not to_location:
            return jsonify({'error': 'to_location required'}), 400

        memory_mgr = get_memory_manager()
        result = memory_mgr.switch_location(
            character_id=char_id,
            from_location=from_location,
            to_location=to_location,
            current_messages=current_messages
        )

        # XP esplorazione: prima visita a una location = 25 XP
        xp_result = None
        if result.get('visit_count') == 1:
            try:
                xp_result = award_xp_direct(char_id, 25, "exploration")
            except Exception as e:
                current_app.logger.error(f"Exploration XP error: {e}")

        if xp_result:
            result['xp_awarded'] = xp_result

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Switch location error: {str(e)}')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@location_bp.route('/<character_id>/map', methods=['GET'])
@require_auth
def get_character_map(character_id):
    """Ottieni la mappa/stato del personaggio nel mondo."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    world_mgr = get_world_manager()
    state_mgr = get_player_state_manager()
    state = state_mgr.get_state(character_id)

    return jsonify({
        'position': state.position.to_dict(),
        'discovered_sublocations': state.discovered_sublocations,
        'visit_history': state.visit_history,
        'npc_dispositions': state.npc_dispositions
    })


@location_bp.route('/<character_id>/location', methods=['GET'])
@require_auth
def get_character_location(character_id):
    """Ottieni informazioni sulla posizione corrente con gerarchia."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    location_info = get_current_location_info(character_id)
    if not location_info:
        return jsonify({
            'current_location': None,
            'has_location': False
        })
    # Aggiungi current_location come alias per compatibilità
    location_info['current_location'] = location_info.get('current')
    return jsonify(location_info)


@location_bp.route('/<character_id>/location/exits', methods=['GET'])
@require_auth
def get_location_exits(character_id):
    """Ottieni le uscite dalla posizione corrente."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    location_info = get_current_location_info(character_id)
    if not location_info:
        return jsonify({'exits': [], 'current': None})

    return jsonify({
        'exits': location_info.get('exits', []),
        'current': location_info.get('current', None)
    })


@location_bp.route('/<character_id>/location/visited', methods=['GET'])
@require_auth
def get_visited_locations(character_id):
    """Ottieni le location visitate dal personaggio."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    state_mgr = get_player_state_manager()
    state = state_mgr.get_state(character_id)

    visited = []
    for loc_id, timestamps in state.visit_history.items():
        visited.append({
            'id': loc_id,
            'visit_count': len(timestamps),
            'first_visit': timestamps[0] if timestamps else None,
            'last_visit': timestamps[-1] if timestamps else None
        })

    return jsonify({'visited': visited})


@location_bp.route('/<character_id>/location/neighborhood', methods=['GET'])
@require_auth
def get_neighborhood(character_id):
    """Ottieni il grafo completo dell'esplorazione per la mini-mappa."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    world_mgr = get_world_manager()
    graph_data = world_mgr.get_exploration_graph(character_id)

    if not graph_data.get('has_location'):
        return jsonify({
            'has_location': False,
            'current': None,
            'nodes': [],
            'edges': [],
            'breadcrumb': []
        })

    return jsonify(graph_data)


@location_bp.route('/<character_id>/location-preview/<location_id>', methods=['GET'])
@require_auth
def get_location_preview(character_id, location_id):
    """Info dettagliate su una location per il widget preview."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    world_mgr = get_world_manager()
    result = world_mgr.get_location_preview(character_id, location_id)

    if 'error' in result:
        return jsonify(result), 404

    return jsonify(result)


@location_bp.route('/<character_id>/world-graph', methods=['GET'])
@require_auth
def get_world_graph(character_id):
    """Ritorna il grafo del mondo a un dato livello di profondita' per la World Map."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    depth = request.args.get('depth', 0, type=int)
    parent_id = request.args.get('parent_id', None, type=str)

    # depth 0 non richiede parent_id
    if depth > 0 and not parent_id:
        return jsonify({'error': 'parent_id required for depth > 0'}), 400

    world_mgr = get_world_manager()
    result = world_mgr.get_world_graph(character_id, depth, parent_id)

    return jsonify(result)
