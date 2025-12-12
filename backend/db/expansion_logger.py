# expansion_logger.py - Log delle espansioni con Sonnet
"""
Traccia quando i giocatori usano il pulsante "Focus" per espandere con Sonnet.
Utile per analytics su cosa interessa ai giocatori.
"""

import os
import json
from datetime import datetime
from typing import Optional
import logging

# Setup logger
logger = logging.getLogger('expansion_logger')
logger.setLevel(logging.INFO)


class ExpansionLogger:
    """Logger per le espansioni Sonnet"""
    
    def __init__(self, log_dir: str = "db/data/logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "expansions.jsonl")
    
    def log_expansion(
        self,
        character_id: str,
        location_id: str,
        original_message: str,
        expanded_message: str,
        context_type: str,  # "description", "dialogue", "combat", "lore", etc.
        user_prompt: Optional[str] = None,
        tags_found: Optional[list] = None
    ):
        """
        Logga un'espansione.
        
        Args:
            character_id: ID del personaggio
            location_id: ID della location corrente
            original_message: Messaggio originale (Haiku)
            expanded_message: Messaggio espanso (Sonnet)
            context_type: Tipo di contesto (per categorizzazione)
            user_prompt: Prompt originale dell'utente
            tags_found: Tag meccanici trovati nel messaggio
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'character_id': character_id,
            'location_id': location_id,
            'context_type': context_type,
            'user_prompt': user_prompt,
            'original_length': len(original_message),
            'expanded_length': len(expanded_message),
            'expansion_ratio': len(expanded_message) / len(original_message) if original_message else 0,
            'tags_found': tags_found or [],
            # Non salviamo il testo completo per privacy, solo metadati
            'original_preview': original_message[:100] + '...' if len(original_message) > 100 else original_message,
        }
        
        # Append to JSONL file
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        logger.info(f"Expansion logged: {character_id} @ {location_id} - {context_type}")
    
    def get_stats(self, days: int = 7) -> dict:
        """
        Ottiene statistiche sulle espansioni.
        
        Returns:
            Dict con statistiche aggregate
        """
        if not os.path.exists(self.log_file):
            return {'total': 0, 'by_context': {}, 'by_location': {}}
        
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        stats = {
            'total': 0,
            'by_context': {},
            'by_location': {},
            'avg_expansion_ratio': 0,
            'period_days': days
        }
        
        ratios = []
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry_time = datetime.fromisoformat(entry['timestamp'])
                    
                    if entry_time >= cutoff:
                        stats['total'] += 1
                        
                        ctx = entry.get('context_type', 'unknown')
                        stats['by_context'][ctx] = stats['by_context'].get(ctx, 0) + 1
                        
                        loc = entry.get('location_id', 'unknown')
                        stats['by_location'][loc] = stats['by_location'].get(loc, 0) + 1
                        
                        if entry.get('expansion_ratio'):
                            ratios.append(entry['expansion_ratio'])
                            
                except json.JSONDecodeError:
                    continue
        
        if ratios:
            stats['avg_expansion_ratio'] = sum(ratios) / len(ratios)
        
        # Top 5 per categoria
        stats['top_contexts'] = sorted(
            stats['by_context'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        stats['top_locations'] = sorted(
            stats['by_location'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return stats


# Singleton
_expansion_logger: Optional[ExpansionLogger] = None

def get_expansion_logger() -> ExpansionLogger:
    global _expansion_logger
    if _expansion_logger is None:
        _expansion_logger = ExpansionLogger()
    return _expansion_logger
