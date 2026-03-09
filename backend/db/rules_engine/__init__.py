"""
Rules Engine - Meccaniche di gioco deterministiche per Statisfy RPG.

Si inserisce tra il parser statisfy-tags e gli applicators.
Risolve tag di intento, valida meccaniche, rileva morte,
gestisce scadenza condizioni.
"""

from .engine import RulesEngine, ResolvedResult
from .formula import FormulaEvaluator, FormulaError
from .death import DeathHandler, DeathEvent

__all__ = [
    "RulesEngine",
    "ResolvedResult",
    "FormulaEvaluator",
    "FormulaError",
    "DeathHandler",
    "DeathEvent",
]
