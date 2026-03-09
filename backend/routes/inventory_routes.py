"""
Blueprint: Inventario e Equipment (add/remove, equip/unequip, move).
"""

from flask import Blueprint, request, jsonify

from auth import require_auth
from helpers import verify_ownership
from db.mock_db import db
from db.repos.equipment_repo import VALID_SLOTS
from db.player_state import get_player_state_manager
from db.world_manager import get_world_manager

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/character')


@inventory_bp.route('/<character_id>/inventory', methods=['POST'])
@require_auth
def add_inventory_item(character_id):
    """Aggiunge item all'inventario."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    item_name = data.get('item_name')
    quantity = data.get('quantity', 1)

    if not item_name:
        return jsonify({'error': 'item_name richiesto'}), 400

    result = db.add_to_inventory(character_id, item_name, quantity)
    return jsonify(result)


@inventory_bp.route('/<character_id>/inventory/<item_name>', methods=['DELETE'])
@require_auth
def remove_inventory_item(character_id, item_name):
    """Rimuove item dall'inventario."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    quantity = request.args.get('quantity', 1, type=int)

    success = db.remove_from_inventory(character_id, item_name, quantity)
    if not success:
        return jsonify({'error': 'Item non trovato'}), 404

    return jsonify({'success': True})


@inventory_bp.route('/<character_id>/equip', methods=['POST'])
@require_auth
def equip_item(character_id):
    """Equipaggia un item dall'inventario in uno slot specifico."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    item_name = data.get('item_name')
    slot = data.get('slot')

    if not item_name or not slot:
        return jsonify({'error': 'item_name e slot richiesti'}), 400

    if slot not in VALID_SLOTS:
        return jsonify({'error': f'Slot non valido: {slot}'}), 400

    result = db.equip_from_inventory(character_id, item_name, slot)
    if not result:
        return jsonify({'error': 'Slot non compatibile con questo item'}), 400

    return jsonify({'success': True, 'equipped': result})


@inventory_bp.route('/<character_id>/unequip', methods=['POST'])
@require_auth
def unequip_item(character_id):
    """Rimuove un item equipaggiato e lo mette in inventario."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    slot = data.get('slot')

    if not slot:
        return jsonify({'error': 'slot richiesto'}), 400

    if slot not in VALID_SLOTS:
        return jsonify({'error': f'Slot non valido: {slot}'}), 400

    result = db.unequip_to_inventory(character_id, slot)
    if not result:
        return jsonify({'error': 'Nessun item in questo slot'}), 404

    return jsonify({'success': True})


@inventory_bp.route('/<character_id>/move-equipment', methods=['POST'])
@require_auth
def move_equipment(character_id):
    """Sposta un item da uno slot a un altro."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    from_slot = data.get('from_slot')
    to_slot = data.get('to_slot')

    if not from_slot or not to_slot:
        return jsonify({'error': 'from_slot e to_slot richiesti'}), 400

    if from_slot not in VALID_SLOTS or to_slot not in VALID_SLOTS:
        return jsonify({'error': 'Slot non valido'}), 400

    result = db.move_equipment(character_id, from_slot, to_slot)
    if not result:
        return jsonify({'error': 'Impossibile spostare: slot non compatibile o vuoto'}), 400

    return jsonify({'success': True, 'moved': result})


@inventory_bp.route('/<character_id>/use-item', methods=['POST'])
@require_auth
def use_item(character_id):
    """Usa un consumabile dall'inventario."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    item_name = data.get('item_name')

    if not item_name:
        return jsonify({'error': 'item_name richiesto'}), 400

    result = db.use_consumable(character_id, item_name)
    if not result:
        return jsonify({'error': 'Item non utilizzabile o non trovato'}), 400

    return jsonify({'success': True, 'result': result})


# ═══════════════════════════════════════
# SHOP / VENDOR
# ═══════════════════════════════════════

@inventory_bp.route('/<character_id>/shop/<npc_id>', methods=['GET'])
@require_auth
def get_shop(character_id, npc_id):
    """Ottieni inventario del negozio NPC."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    shop = db.get_shop_inventory(npc_id)
    if not shop:
        return jsonify({'error': 'NPC non ha un negozio'}), 404

    return jsonify(shop)


@inventory_bp.route('/<character_id>/shop/<npc_id>/buy', methods=['POST'])
@require_auth
def buy_from_shop(character_id, npc_id):
    """Compra un item dal negozio NPC."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    equipment_id = data.get('equipment_id')

    if not equipment_id:
        return jsonify({'error': 'equipment_id richiesto'}), 400

    result = db.buy_from_shop(character_id, npc_id, equipment_id)
    if not result:
        return jsonify({'error': 'Acquisto non riuscito'}), 400

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)


@inventory_bp.route('/<character_id>/shop/<npc_id>/sell', methods=['POST'])
@require_auth
def sell_to_shop(character_id, npc_id):
    """Vendi un item al negozio NPC."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404
    data = request.json
    item_name = data.get('item_name')

    if not item_name:
        return jsonify({'error': 'item_name richiesto'}), 400

    result = db.sell_to_shop(character_id, npc_id, item_name)
    if not result:
        return jsonify({'error': 'Vendita non riuscita'}), 400

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)


# ═══════════════════════════════════════
# NEARBY VENDORS (zero AI calls)
# ═══════════════════════════════════════

@inventory_bp.route('/<character_id>/nearby-vendors', methods=['GET'])
@require_auth
def nearby_vendors(character_id):
    """Restituisce i vendor con shop nella location corrente del giocatore.
    Puro data lookup — nessuna chiamata AI."""
    if not verify_ownership(character_id):
        return jsonify({'error': 'Personaggio non trovato'}), 404

    # Leggi posizione del personaggio
    state_mgr = get_player_state_manager()
    state = state_mgr.load_state(character_id)
    location_id = state.position.location_id

    if not location_id:
        return jsonify({'vendors': [], 'location_id': ''})

    # Ottieni NPC della location e filtra quelli con shop
    world_mgr = get_world_manager()
    npcs = world_mgr.get_npc_pool_for_location(location_id)

    vendors = []
    for npc in npcs:
        shop = npc.get('shop_inventory')
        if shop:
            vendors.append({
                'npc_id': npc.get('id', ''),
                'name': npc.get('name', ''),
                'title': npc.get('title', ''),
                'role': npc.get('role', 'merchant'),
                'item_count': len(shop),
            })

    return jsonify({'vendors': vendors, 'location_id': location_id})
