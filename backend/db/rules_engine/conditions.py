"""
Sistema di tick e scadenza condizioni.

Ogni chiamata a process() del GM equivale a 1 tick.
Le condizioni con durata numerica vengono decrementate
e rimosse automaticamente quando raggiungono 0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from statisfy_tags import ConditionRemoveAction

if TYPE_CHECKING:
    from ..player_state import PlayerState


# Durate che non scadono mai
_NON_EXPIRING = frozenset({"permanent", "quest", "passive"})


class ConditionTicker:
    """
    Gestisce il decremento e la scadenza delle condizioni.

    Le condizioni in player_state.stats["conditions"] hanno formato:
        {"name": "burned", "duration": "3_scenes"}

    Al primo tick viene aggiunto 'ticks_remaining' calcolato
    da _parse_duration_to_ticks(). Successivamente viene solo
    decrementato.
    """

    def tick(
        self, player_state: "PlayerState"
    ) -> tuple[list[ConditionRemoveAction], list[str]]:
        """
        Decrementa tutte le condizioni di 1 tick.

        Modifica state.stats["conditions"] in-place.

        Returns:
            (azioni_rimozione, nomi_scaduti)
        """
        conditions = player_state.stats.get("conditions", [])
        if not conditions:
            return [], []

        expired_actions: list[ConditionRemoveAction] = []
        expired_names: list[str] = []
        remaining: list[dict] = []

        for cond in conditions:
            duration = cond.get("duration")
            name = cond.get("name", "unknown")

            # Condizioni permanenti: non scadono
            if duration in _NON_EXPIRING or duration is None:
                remaining.append(cond)
                continue

            # Inizializza ticks_remaining al primo incontro
            if "ticks_remaining" not in cond:
                cond["ticks_remaining"] = self._parse_duration_to_ticks(duration)

            # Decrementa
            cond["ticks_remaining"] -= 1

            if cond["ticks_remaining"] <= 0:
                expired_names.append(name)
                expired_actions.append(
                    ConditionRemoveAction(condition_name=name)
                )
            else:
                remaining.append(cond)

        # Aggiorna in-place
        player_state.stats["conditions"] = remaining

        return expired_actions, expired_names

    @staticmethod
    def _parse_duration_to_ticks(duration: str) -> int:
        """
        Converte stringa durata in numero di tick.

        Formati supportati:
            "3"            → 3
            "3_ticks"      → 3
            "3_scenes"     → 3  (1 scena = 1 tick)
            "3_rounds"     → 3
            "2_turns"      → 2
            "1_hour"       → 60
            "2_hours"      → 120
            "1_day"        → 1440

        Fallback: 1 tick se non parsabile.
        """
        if not duration:
            return 1

        cleaned = duration.strip().lower()

        # Numero puro
        try:
            return max(1, int(cleaned))
        except ValueError:
            pass

        # Formato "N_unita"
        parts = cleaned.split("_", 1)
        if len(parts) == 2:
            try:
                count = int(parts[0])
            except ValueError:
                return 1

            unit = parts[1]
            multipliers = {
                "tick": 1,
                "ticks": 1,
                "round": 1,
                "rounds": 1,
                "turn": 1,
                "turns": 1,
                "scene": 1,
                "scenes": 1,
                "hour": 60,
                "hours": 60,
                "day": 1440,
                "days": 1440,
            }
            return max(1, count * multipliers.get(unit, 1))

        return 1
