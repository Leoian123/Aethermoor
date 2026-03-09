"""
Blueprint: Autenticazione (register, login, me).
"""

from flask import Blueprint, request, jsonify, g

from auth import hash_password, verify_password, create_token, require_auth
from db.mock_db import db

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Registra un nuovo utente."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'validation_error', 'message': 'Nessun dato fornito'}), 400

    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    if not username or len(username) < 3 or len(username) > 20:
        return jsonify({'error': 'validation_error', 'message': 'Username deve essere 3-20 caratteri'}), 400
    if not password or len(password) < 6:
        return jsonify({'error': 'validation_error', 'message': 'Password deve essere almeno 6 caratteri'}), 400

    existing = db.get_user_by_username(username)
    if existing:
        return jsonify({'error': 'conflict', 'message': 'Username già in uso'}), 409

    password_hash = hash_password(password)
    user = db.create_user(username, password_hash)
    token = create_token(user['id'], user['username'])

    return jsonify({
        'token': token,
        'user': {'id': user['id'], 'username': user['username']}
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login utente esistente."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'validation_error', 'message': 'Nessun dato fornito'}), 400

    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'validation_error', 'message': 'Username e password richiesti'}), 400

    user = db.get_user_by_username(username)
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({'error': 'auth_error', 'message': 'Credenziali non valide'}), 401

    token = create_token(user['id'], user['username'])

    return jsonify({
        'token': token,
        'user': {'id': user['id'], 'username': user['username']}
    })


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """Verifica token e ritorna dati utente."""
    return jsonify({
        'user': {'id': g.user_id, 'username': g.username}
    })
