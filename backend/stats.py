"""
STATISFY RPG - Modulo Calcolo Stats
Formule universali per stats derivate e composizione stats a 7 sorgenti.

@STAT = Iniziale + Creazione + Investiti + LevelUp + Equipment + Training + Titoli
"""

STAT_KEYS = ['str', 'dex', 'vit', 'int']
BONUS_SOURCES = ['invested', 'level_up', 'training', 'titles']


def empty_stat_bonuses() -> dict:
    """Ritorna struttura bonus vuota per inizializzazione personaggio."""
    return {source: {k: 0 for k in STAT_KEYS} for source in BONUS_SOURCES}


def compute_equipment_bonuses(equipped_items: list) -> dict:
    """Somma stats_bonus di tutti gli item effettivamente equipaggiati.

    Ignora item con equipped_slot == 'inventory' (non equipaggiati).
    """
    bonuses = {k: 0 for k in STAT_KEYS}
    for item in equipped_items:
        if item.get('equipped_slot', 'inventory') == 'inventory':
            continue
        for stat, val in item.get('stats_bonus', {}).items():
            if stat in bonuses:
                bonuses[stat] += val
    return bonuses


def compute_total_stats(base_stats: dict, stat_bonuses: dict,
                        equipment_bonuses: dict) -> dict:
    """Somma tutte le 7 sorgenti per ottenere le stats totali.

    base_stats contiene gia' Iniziale(10) + Creazione.
    stat_bonuses contiene invested, level_up, training, titles.
    equipment_bonuses contiene i bonus dagli item equipaggiati.
    """
    totals = {}
    for key in STAT_KEYS:
        total = base_stats.get(key, 10)
        for source in BONUS_SOURCES:
            total += stat_bonuses.get(source, {}).get(key, 0)
        total += equipment_bonuses.get(key, 0)
        totals[key] = total
    return totals


def compute_derived_stats(total_stats: dict) -> dict:
    """Calcola le 14 stats derivate dai totali.

    Formule universali (uguali per tutte le classi):

    STR:
        Molt. Danno Fisico = 1 + (STR / 100)
        Capacita' Carico   = 50 + (STR * 0.5) kg

    DEX:
        Attacchi per Turno  = 1 + (DEX * 0.005)
        Precisione          = 60 + (DEX / 10) %
        Evasione            = DEX / 20 %
        Velocita' Movimento = 100 + (DEX / 5) %

    VIT:
        Punti Vita (HP)     = 100 + (VIT * 15)
        Regen HP            = VIT / 10 HP/min
        Res. Veleni         = VIT / 5 %
        Res. Elementi       = VIT / 10 %

    INT:
        Punti Mana (MP)     = 50 + (INT * 10)
        Molt. Danno Magico  = 1 + (INT / 50)
        Bonus EXP           = INT / 20 %
        Bonus Crafting      = INT / 15 %
    """
    s = total_stats.get('str', 10)
    d = total_stats.get('dex', 10)
    v = total_stats.get('vit', 10)
    i = total_stats.get('int', 10)

    return {
        # STR
        'phys_dmg_mult': round(1 + s / 100, 2),
        'carry_max': round(50 + s * 0.5, 1),
        # DEX
        'attacks_per_turn': round(1 + d * 0.005, 3),
        'precision': round(60 + d / 10, 1),
        'evasion': round(d / 20, 1),
        'move_speed': round(100 + d / 5, 1),
        # VIT
        'hp_max': int(100 + v * 15),
        'hp_regen': round(v / 10, 1),
        'poison_resist': round(v / 5, 1),
        'element_resist': round(v / 10, 1),
        # INT
        'mana_max': int(50 + i * 10),
        'magic_dmg_mult': round(1 + i / 50, 2),
        'xp_bonus': round(i / 20, 1),
        'craft_bonus': round(i / 15, 1),
    }


def compute_invest_points_available(level: int, stat_bonuses: dict) -> int:
    """Calcola i punti liberi disponibili per l'investimento.

    Ogni level-up (dal livello 2 in poi) concede 10 punti liberi.
    I punti gia' investiti vengono sottratti.
    """
    total_earned = (level - 1) * 10
    invested = stat_bonuses.get('invested', {})
    total_spent = sum(invested.get(k, 0) for k in STAT_KEYS)
    return max(0, total_earned - total_spent)


def apply_condition_modifiers(derived: dict, conditions: list) -> dict:
    """Applica modificatori delle condizioni alle stats derivate.

    Condizioni gestite:
        - death_malus: -10% a tutte le stats derivate
        - death_recovery_bonus: +50% su xp_bonus

    Args:
        derived: stats derivate calcolate da compute_derived_stats()
        conditions: lista condizioni attive [{name, duration, ...}]

    Returns:
        Copia delle stats derivate con modificatori applicati
    """
    if not conditions:
        return derived

    modified = dict(derived)
    condition_names = {c.get("name") for c in conditions if isinstance(c, dict)}

    # Death malus: -10% tutte le stats
    if "death_malus" in condition_names:
        for key in modified:
            val = modified[key]
            if isinstance(val, (int, float)):
                modified[key] = round(val * 0.9, 2)

    # Death recovery bonus: +50% EXP bonus
    if "death_recovery_bonus" in condition_names:
        if "xp_bonus" in modified:
            modified["xp_bonus"] = round(modified["xp_bonus"] * 1.5, 1)

    return modified
