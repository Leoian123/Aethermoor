"""
Valutatore sicuro di formule per skill di gioco.

Usa ast.parse per valutare espressioni aritmetiche
senza mai chiamare eval(). Supporta solo operazioni
matematiche e variabili dal contesto.

Esempio:
    evaluator = FormulaEvaluator()
    result = evaluator.evaluate("20 + (mastery * 8)", {"mastery": 3})
    # result == 44.0
"""

from __future__ import annotations

import ast
import operator
from typing import Any


class FormulaError(Exception):
    """Errore nella valutazione di una formula skill."""
    pass


class FormulaEvaluator:
    """
    Valuta formule aritmetiche da skills.json in modo sicuro.

    Operazioni permesse: +, -, *, /, //, %, **
    Nodi permessi: numeri, variabili (dal context), operazioni binarie/unarie
    Funzioni permesse: min, max, abs, round, int
    """

    _BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    _UNARY_OPS = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    _SAFE_FUNCS = {
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "int": int,
    }

    def evaluate(self, formula: str, context: dict[str, int | float]) -> float:
        """
        Valuta una formula con variabili dal contesto.

        Args:
            formula: es. "20 + (mastery * 8)"
            context: es. {"mastery": 3, "level": 5, "int": 25}

        Returns:
            Valore calcolato come float

        Raises:
            FormulaError: se la formula contiene operazioni non permesse
        """
        if not formula or not formula.strip():
            raise FormulaError("Formula vuota")

        try:
            tree = ast.parse(formula.strip(), mode="eval")
            return float(self._eval_node(tree.body, context))
        except FormulaError:
            raise
        except (SyntaxError, TypeError) as e:
            raise FormulaError(f"Sintassi invalida '{formula}': {e}")
        except KeyError as e:
            raise FormulaError(f"Variabile sconosciuta in '{formula}': {e}")
        except ZeroDivisionError:
            raise FormulaError(f"Divisione per zero in '{formula}'")

    def _eval_node(self, node: ast.AST, ctx: dict[str, Any]) -> float:
        """Valuta ricorsivamente un nodo AST."""
        match node:
            # Costante numerica: 20, 3.14
            case ast.Constant(value=v) if isinstance(v, (int, float)):
                return float(v)

            # Variabile: mastery, level, str, int
            case ast.Name(id=name):
                if name not in ctx:
                    raise FormulaError(f"Variabile sconosciuta: '{name}'")
                val = ctx[name]
                if not isinstance(val, (int, float)):
                    raise FormulaError(
                        f"Variabile '{name}' non numerica: {type(val).__name__}"
                    )
                return float(val)

            # Operazione binaria: a + b, a * b, ...
            case ast.BinOp(left=left, op=op, right=right):
                op_func = self._BIN_OPS.get(type(op))
                if op_func is None:
                    raise FormulaError(
                        f"Operatore non supportato: {type(op).__name__}"
                    )
                return op_func(
                    self._eval_node(left, ctx),
                    self._eval_node(right, ctx),
                )

            # Operazione unaria: -x, +x
            case ast.UnaryOp(op=op, operand=operand):
                op_func = self._UNARY_OPS.get(type(op))
                if op_func is None:
                    raise FormulaError(
                        f"Operatore unario non supportato: {type(op).__name__}"
                    )
                return op_func(self._eval_node(operand, ctx))

            # Chiamata funzione: min(a, b), max(a, b), round(x)
            case ast.Call(func=ast.Name(id=func_name), args=args):
                safe_func = self._SAFE_FUNCS.get(func_name)
                if safe_func is None:
                    raise FormulaError(f"Funzione non permessa: '{func_name}'")
                evaluated_args = [self._eval_node(arg, ctx) for arg in args]
                return float(safe_func(*evaluated_args))

            case _:
                raise FormulaError(
                    f"Nodo AST non supportato: {type(node).__name__}"
                )
