"""
Blueprint: Game Data statico e Admin (classes, skills, health, stats).
"""

from flask import Blueprint, request, jsonify

from db.mock_db import db
from db.expansion_logger import get_expansion_logger

gamedata_bp = Blueprint('gamedata', __name__, url_prefix='/api')


@gamedata_bp.route('/classes', methods=['GET'])
def get_classes():
    """Ottieni tutte le classi disponibili."""
    classes = db.get_all_classes()
    return jsonify(classes)


@gamedata_bp.route('/skills', methods=['GET'])
def get_skills():
    """Ottieni skills. Query params: category, roots_only."""
    category = request.args.get('category')
    roots_only = request.args.get('roots_only', 'false').lower() == 'true'

    if roots_only:
        skills = db.get_root_skills()
    elif category:
        skills = db.get_skills_by_category(category)
    else:
        skills = db.get_all('skills')

    return jsonify(skills)


@gamedata_bp.route('/skills/<skill_id>/tree', methods=['GET'])
def get_skill_tree(skill_id):
    """Ottieni albero skill da una root."""
    tree = db.get_skill_tree(skill_id)
    return jsonify(tree)


@gamedata_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'statisfy-rpg'
    })


@gamedata_bp.route('/expansion-stats', methods=['GET'])
def expansion_stats():
    """Ottiene statistiche sulle espansioni (per il team)."""
    try:
        days = request.args.get('days', 7, type=int)
        logger = get_expansion_logger()
        stats = logger.get_stats(days=days)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
