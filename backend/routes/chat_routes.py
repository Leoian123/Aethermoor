"""
Blueprint: Chat con il Game Master AI (chat, expand).
"""

import anthropic
from flask import Blueprint, request, jsonify, current_app

from auth import require_auth
from config import client, MODEL_HAIKU, MODEL_SONNET
from helpers import (
    verify_ownership,
    build_system_prompt,
    sanitize_user_message,
    sanitize_history,
    extract_key_event,
    extract_tags_from_text,
    VALID_CONTEXT_TYPES,
)
from errors import StatisfyError, AIServiceError

from db.applicators import process_gm_response, strip_gm_tags
from db.mock_db import db
from db.location_memory import get_memory_manager  # usato per salvataggio memoria
from db.expansion_logger import get_expansion_logger

chat_bp = Blueprint('chat', __name__, url_prefix='/api')


@chat_bp.route('/chat', methods=['POST'])
@require_auth
def chat():
    """
    Endpoint principale per la chat con il Game Master.
    Usa Haiku per risposte veloci ed economiche.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        raw_message = data.get('message', '').strip()
        if not raw_message:
            return jsonify({'error': 'Message required'}), 400

        # Sanitizza input: rimuovi tag meccanici/spaziali dal messaggio
        message = sanitize_user_message(raw_message)
        if not message:
            return jsonify({'error': 'Message required'}), 400

        character = data.get('character', {})
        character_id = character.get('id', '')
        location_id = data.get('location_id', '')

        # Verifica ownership
        if character_id and not verify_ownership(character_id):
            return jsonify({'error': 'Personaggio non trovato'}), 404

        # Sanitizza history: valida role, rimuovi tag dai messaggi user
        history = sanitize_history(data.get('history', []))

        # Costruisci system prompt modulare (core + sfere? + prima sessione? + contesto + recap)
        system = build_system_prompt(character, character_id, location_id)

        # Prepara messaggi per Claude
        messages = []
        for msg in history[-20:]:  # Ultimi 20 messaggi
            messages.append({
                'role': msg['role'],
                'content': msg['content'],
            })

        # Aggiungi messaggio corrente
        messages.append({
            'role': 'user',
            'content': message
        })

        # Chiamata a Claude HAIKU (veloce, economico)
        try:
            response = client.messages.create(
                model=MODEL_HAIKU,
                max_tokens=1024,
                system=system,
                messages=messages
            )
        except anthropic.AuthenticationError:
            raise AIServiceError("API key non valida o scaduta")
        except anthropic.RateLimitError:
            raise AIServiceError("Troppe richieste al Game Master, riprova tra poco")
        except anthropic.APIConnectionError:
            raise AIServiceError("Il Game Master non è raggiungibile")
        except anthropic.APIStatusError as e:
            raise AIServiceError(f"Servizio AI temporaneamente non disponibile ({e.status_code})")

        # Estrai testo dalla risposta
        response_text = ''
        for block in response.content:
            if block.type == 'text':
                response_text += block.text

        # Processa i tag di location
        location_report = {}
        if character_id:
            try:
                current_app.logger.debug(f"Processing tags for character: {character_id}")
                current_app.logger.debug(f"Response text (first 200 chars): {response_text[:200]}")
                location_report = process_gm_response(character_id, response_text)
                current_app.logger.debug(f"Report: {location_report}")
            except Exception as e:
                current_app.logger.error(f"Location processing error: {str(e)}", exc_info=True)

        # Salva automaticamente nella memoria della location
        if character_id and location_id:
            try:
                memory_mgr = get_memory_manager()
                memory_mgr.add_message(character_id, location_id, 'user', message)
                memory_mgr.add_message(character_id, location_id, 'assistant', response_text)

                # Estrai eventi chiave dai tag
                key_event = extract_key_event(message, response_text)
                if key_event:
                    memory_mgr.add_event(character_id, location_id, key_event)
            except Exception as e:
                current_app.logger.warning(f'Memory save error: {str(e)}')

        # Ri-fetch personaggio aggiornato dal DB (source of truth)
        updated_character = None
        if character_id:
            try:
                updated_character = db.get_character_full(character_id)
            except Exception as e:
                current_app.logger.error(f"Failed to fetch updated character: {e}")

        # Ritorna risposta con stato aggiornato
        return jsonify({
            'response': response_text,
            'location_updates': location_report,
            'model': 'haiku',
            'character': updated_character
        })

    except StatisfyError:
        raise
    except Exception as e:
        current_app.logger.error(f'Chat error: {str(e)}', exc_info=True)
        return jsonify({
            'error': 'internal_error',
            'message': 'Errore interno del server'
        }), 500


@chat_bp.route('/chat/expand', methods=['POST'])
@require_auth
def expand_message():
    """
    Espande un messaggio con Sonnet per maggiore dettaglio.
    Usato quando il giocatore vuole approfondire una scena.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        original_message = data.get('original_message', '').strip()
        user_prompt = data.get('user_prompt', '')
        character = data.get('character', {})
        character_id = character.get('id', '')
        location_id = data.get('location_id', '')

        # Whitelist context_type
        context_type = data.get('context_type', 'general')
        if context_type not in VALID_CONTEXT_TYPES:
            context_type = 'general'

        # Verifica ownership
        if character_id and not verify_ownership(character_id):
            return jsonify({'error': 'Personaggio non trovato'}), 404

        if not original_message:
            return jsonify({'error': 'Original message required'}), 400

        # Sanitizza history
        history = sanitize_history(data.get('history', []))

        # Costruisci prompt per espansione
        expansion_prompt = f"""Espandi e arricchisci questa scena con maggiore dettaglio narrativo.
Mantieni lo stesso tono e gli stessi eventi, ma aggiungi:
- Descrizioni sensoriali più ricche
- Dettagli ambientali
- Sfumature emotive dei personaggi
- Atmosfera più immersiva

IMPORTANTE: Mantieni la stessa struttura di formattazione (paragrafi separati, dialoghi su righe singole).
Non aggiungere nuovi eventi o cambiare la trama.

Tipo di focus richiesto: {context_type}

SCENA ORIGINALE:
{original_message}

SCENA ESPANSA:"""

        # Costruisci system prompt modulare
        system = build_system_prompt(character, character_id, location_id)

        # Prepara messaggi con history per contesto
        messages = []
        for msg in history[-10:]:
            messages.append({
                'role': msg['role'],
                'content': msg['content'],
            })

        messages.append({
            'role': 'user',
            'content': expansion_prompt
        })

        # Chiamata a Claude SONNET (dettagliato)
        try:
            response = client.messages.create(
                model=MODEL_SONNET,
                max_tokens=2048,
                system=system,
                messages=messages
            )
        except anthropic.AuthenticationError:
            raise AIServiceError("API key non valida o scaduta")
        except anthropic.RateLimitError:
            raise AIServiceError("Troppe richieste al Game Master, riprova tra poco")
        except anthropic.APIConnectionError:
            raise AIServiceError("Il Game Master non è raggiungibile")
        except anthropic.APIStatusError as e:
            raise AIServiceError(f"Servizio AI temporaneamente non disponibile ({e.status_code})")

        # Estrai testo
        expanded_text = ''
        for block in response.content:
            if block.type == 'text':
                expanded_text += block.text

        # Logga l'espansione per analytics
        try:
            logger = get_expansion_logger()
            logger.log_expansion(
                character_id=character_id,
                location_id=location_id,
                original_message=original_message,
                expanded_message=expanded_text,
                context_type=context_type,
                user_prompt=user_prompt,
                tags_found=extract_tags_from_text(original_message)
            )
        except Exception as e:
            current_app.logger.warning(f'Expansion logging error: {str(e)}')

        return jsonify({
            'expanded': expanded_text,
            'model': 'sonnet',
            'context_type': context_type
        })

    except StatisfyError:
        raise
    except Exception as e:
        current_app.logger.error(f'Expand error: {str(e)}', exc_info=True)
        return jsonify({
            'error': 'internal_error',
            'message': 'Errore interno del server'
        }), 500
