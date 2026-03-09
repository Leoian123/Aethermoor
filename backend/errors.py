"""
STATISFY RPG - Eccezioni custom

Gerarchia di errori strutturata per l'applicazione.
Ogni errore ha un status_code HTTP e un error_type per il frontend.
"""


class StatisfyError(Exception):
    """Base per tutti gli errori dell'app."""
    status_code = 500
    error_type = "internal_error"

    def __init__(self, message: str = "Errore interno del server"):
        self.message = message
        super().__init__(self.message)


class ValidationError(StatisfyError):
    """Dati di input non validi (400)."""
    status_code = 400
    error_type = "validation_error"

    def __init__(self, message: str = "Dati non validi"):
        super().__init__(message)


class NotFoundError(StatisfyError):
    """Risorsa non trovata (404)."""
    status_code = 404
    error_type = "not_found"

    def __init__(self, message: str = "Risorsa non trovata"):
        super().__init__(message)


class AIServiceError(StatisfyError):
    """Errore nel servizio AI — Claude non raggiungibile (503)."""
    status_code = 503
    error_type = "ai_service_error"

    def __init__(self, message: str = "Il Game Master non è raggiungibile"):
        super().__init__(message)


class ConflictError(StatisfyError):
    """Conflitto di stato — es. slot già occupato (409)."""
    status_code = 409
    error_type = "conflict"

    def __init__(self, message: str = "Conflitto di stato"):
        super().__init__(message)


class AuthError(StatisfyError):
    """Errore di autenticazione (401)."""
    status_code = 401
    error_type = "auth_error"

    def __init__(self, message: str = "Autenticazione richiesta"):
        super().__init__(message)
