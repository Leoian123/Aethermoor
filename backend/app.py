"""
STATISFY RPG - Flask Backend
Game Master AI powered by Claude

App factory: registra i blueprint e gestisce gli errori.
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from errors import StatisfyError

load_dotenv()


def create_app():
    """Crea e configura l'app Flask."""
    app = Flask(__name__)
    CORS(app)

    # ── Error handler globale ──
    @app.errorhandler(StatisfyError)
    def handle_statisfy_error(error):
        app.logger.error(f"[{error.error_type}] {error.message}")
        return jsonify({
            'error': error.error_type,
            'message': error.message,
        }), error.status_code

    # ── Registra blueprint ──
    from routes.auth_routes import auth_bp
    from routes.chat_routes import chat_bp
    from routes.character_routes import character_bp
    from routes.location_routes import location_bp
    from routes.quest_routes import quest_bp
    from routes.inventory_routes import inventory_bp
    from routes.gamedata_routes import gamedata_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(character_bp)
    app.register_blueprint(location_bp)
    app.register_blueprint(quest_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(gamedata_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
