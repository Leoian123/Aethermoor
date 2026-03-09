"""
Configurazione AI e costanti globali.
"""

import os
from anthropic import Anthropic

# Modelli AI
MODEL_HAIKU = 'claude-haiku-4-5-20251001'      # Default: veloce, economico
MODEL_SONNET = 'claude-sonnet-4-5-20250929'     # Focus: dettagliato

# Client Anthropic (singleton)
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
