"""
STATISFY RPG - Auth Module
Password hashing (werkzeug.security), JWT tokens (PyJWT), auth decorator.
"""

import os
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret-change-me')
JWT_EXPIRY_HOURS = 72  # 3 giorni


def hash_password(password: str) -> str:
    """Hash password con scrypt (werkzeug default)."""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica password contro hash."""
    return check_password_hash(password_hash, password)


def create_token(user_id: str, username: str) -> str:
    """Genera JWT token con scadenza."""
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def decode_token(token: str) -> dict:
    """Decodifica e valida JWT. Lancia jwt.ExpiredSignatureError / jwt.InvalidTokenError."""
    return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])


def require_auth(f):
    """Decoratore: estrae Bearer token, setta g.user_id e g.username.
    Ritorna 401 JSON se token mancante, scaduto o invalido."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'auth_required', 'message': 'Token mancante'}), 401

        token = auth_header[7:]  # Strip "Bearer "
        try:
            payload = decode_token(token)
            g.user_id = payload['user_id']
            g.username = payload['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'token_expired', 'message': 'Sessione scaduta'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'invalid_token', 'message': 'Token non valido'}), 401

        return f(*args, **kwargs)
    return decorated
