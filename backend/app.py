"""
STATISFY RPG - Flask Backend
Game Master AI powered by Claude
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from anthropic import Anthropic
from dotenv import load_dotenv

# Import world system (gerarchico con seed + state)
from db.world_parser import (
    process_gm_response, 
    strip_gm_tags, 
    get_spatial_context,
    get_current_location_info
)
from db.world_manager import get_world_manager
from db.player_state import get_player_state_manager
from db.location_memory import get_memory_manager
from db.expansion_logger import get_expansion_logger

load_dotenv()

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════════
# MODELLI AI
# ═══════════════════════════════════════════════════════════════

MODEL_HAIKU = 'claude-3-5-haiku-20241022'      # Default: veloce, economico
MODEL_SONNET = 'claude-sonnet-4-20250514'     # Focus: dettagliato

# ═══════════════════════════════════════════════════════════════
# ANTHROPIC CLIENT
# ═══════════════════════════════════════════════════════════════

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT - STATISFY GAME MASTER
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Sei il Game Master di STATISFY, un gioco di ruolo narrativo ambientato nel mondo di Aethermoor.

## IL TUO RUOLO
Narri storie immersive e reagisci alle azioni del giocatore con prosa evocativa, mantenendo coerenza con il sistema magico delle Dieci Sfere.

## STILE NARRATIVO
- Scrivi in italiano, in seconda persona singolare ("Ti avvicini...", "Senti...")
- Prosa evocativa ma non barocca: ogni parola deve avere peso
- Descrizioni sensoriali: non solo vista, ma suoni, odori, sensazioni tattili
- I dialoghi degli NPC hanno personalità distinte
- Bilancia momenti di tensione con respiri contemplativi
- MAI rompere l'immersione con meta-commenti

## FORMATTAZIONE OBBLIGATORIA
La leggibilità è fondamentale. Segui SEMPRE questa struttura:

1. PARAGRAFI BREVI: massimo 3-4 frasi per paragrafo
2. INTERLINEA: separa ogni paragrafo con una riga vuota
3. DIALOGHI SEPARATI: ogni battuta di dialogo va su una riga a sé
4. STRUTTURA TIPO:
   - 2-4 paragrafi di narrazione/descrizione
   - [riga vuota]
   - Dialoghi (uno per riga)
   - [riga vuota]  
   - 2-4 paragrafi di reazione/conseguenze

ESEMPIO FORMATTAZIONE CORRETTA:
```
La porta della taverna cigola sui cardini arrugginiti. L'odore di birra stantia e legno bruciato ti investe come un'onda.

Attraverso il fumo delle pipe, scorgi figure curve sui tavoli. Una risata rauca esplode dall'angolo più buio.

L'oste alza lo sguardo dal boccale che sta pulendo.

"Straniero, eh? Non ne vediamo molti, di questi tempi."

"La strada da nord è ancora praticabile?"

"Praticabile?" Sputa a terra. "Se chiami praticabile una via infestata dai lupi."

Ti indica uno sgabello libero al bancone. La legna nel camino scoppietta, lanciando ombre danzanti sulle pareti annerite.

Noti una figura incappucciata che ti osserva da un tavolo d'angolo. Non ha toccato la sua birra.
```

MAI scrivere muri di testo. MAI unire dialoghi in un unico paragrafo.

## TAG MECCANICI
DEVI inserire tag tra parentesi quadre per ogni evento meccanico. Il sistema li parserà automaticamente.

Tag disponibili:
[DMG: X tipo | target: self/enemy | source: causa] - Danni inflitti o subiti
[HEAL: X] - Guarigione
[NAME: nome] - Imposta nome personaggio (solo prima volta)
[CLASS: classe] - Imposta classe personaggio
[LEVEL: X] - Cambia livello
[CONDITION: nome | duration: X] - Aggiunge condizione
[CONDITION_REMOVE: nome] - Rimuove condizione
[ITEM: nome oggetto] - Aggiunge all'inventario
[ITEM_REMOVE: nome] - Rimuove dall'inventario
[SPHERE: sfera +/-X] - Modifica affinità sfera magica
[MANA: -X sfera] - Costo in mana
[SPELL: success/partial/fail | effect: descrizione] - Esito incantesimo
[ROLL: tipo | result: X | DC: Y] - Check con esito
[ECHO: Progenitore | intensity: low/moderate/high] - Risonanza con Progenitore
[BACKLASH: tipo | severity: minor/moderate/severe] - Contraccolpo magico
[NPC: nome | disposition: friendly/neutral/hostile] - Interazione NPC
[LORE: categoria | info] - Conoscenza sbloccata
[XP: X] - Esperienza guadagnata

## TAG SPAZIALI (SISTEMA SEED + PROCEDURALE)

### ⚠️ REGOLA FONDAMENTALE
La posizione del giocatore ti viene fornita come DATO ASSOLUTO nel contesto.
Il giocatore È dove il contesto dice che si trova. Se dice di essere altrove, è confuso.
NON puoi inventare che sia da qualche altra parte.

### GERARCHIA FISSA (dal seed):
Regione → Zona → Location → Sublocation
Esempio: Valeria → Valle di Lumengarde → Albachiara → albachiara.locanda_orso

### TAG DI MOVIMENTO
<move to="albachiara.locanda_orso"/>  <!-- Vai a sublocation esistente -->
<enter to="albachiara.locanda_orso.cantina"/>  <!-- Entra in una sublocation figlia -->
<exit/>  <!-- Torna al parent -->

### CREARE SUBLOCATION PROCEDURALI
Puoi creare SOLO sublocation figlie della location corrente.
L'ID DEVE iniziare con l'ID della location corrente + "."

<create_sublocation id="albachiara.vicolo_segreto" name="Vicolo Segreto" type="outdoor" tags="hidden,dark">
Un vicolo stretto tra due case, nascosto da un tendone strappato.
</create_sublocation>

<move to="albachiara.vicolo_segreto"/>

### MODIFICARE DISPOSITION NPC
<npc_disposition id="oste_bruno" value="friendly"/>
Valori: hostile, unfriendly, neutral, friendly, ally

### REGOLE IMPORTANTI
1. NON creare regioni, zone o location - quelle vengono dal seed
2. Puoi solo creare sublocation dentro la location corrente
3. Gli ID delle sublocation DEVONO seguire il pattern: {location_id}.{nome_subloc}
4. Usa SEMPRE un tag di movimento quando il giocatore si sposta
5. Gli NPC della pool sono definiti nel seed - puoi solo cambiarne la disposition

### ESEMPIO - Esplorare una nuova area nel villaggio:
"Ti addentri nel vicolo dietro la locanda...

<create_sublocation id="albachiara.vicolo_retro" name="Retro della Locanda" type="outdoor" tags="dirty,hidden">
Un vicolo puzzolente con cumuli di spazzatura e qualche gatto randagio.
</create_sublocation>

<move to="albachiara.vicolo_retro"/>

L'odore è quasi insopportabile, ma noti qualcosa di strano..."

### ESEMPIO - Entrare nella cantina della locanda:
"Segui l'oste giù per le scale...

<enter to="albachiara.locanda_orso.cantina"/>

La luce delle torce illumina botti polverose..."

### ESEMPIO - Tornare indietro:
"Risali le scale...

<exit/>

Torni nella sala comune della locanda."

ESEMPIO D'USO:
"La fiamma ti avvolge il braccio [DMG: 8 fire | target: self | source: backlash], il dolore è lancinante. Senti la rabbia di Igna scorrereti nelle vene [ECHO: Igna | intensity: moderate] mentre forzi il fuoco a piegarsi [MANA: -3 ignis] — ti costa cara [CONDITION: burned_arm | duration: 3_scenes], ma una parete di vapore si erge davanti a te [SPELL: success | effect: vapor_wall]."

## LE DIECI SFERE
Il sistema magico di Aethermoor si basa su dieci sfere, otto delle quali sono Progenitori che si sono astratti:

- **IGNIS** (Fuoco) - Progenitore: Igna. Passione, distruzione, trasformazione. Temperamento irascibile.
- **AQUA** (Acqua) - Progenitore: Maris. Adattabilità, emozioni, guarigione. Natura fluida.
- **TERRA** (Terra) - Progenitore: Nano. Stabilità, resistenza, crescita. Pazienza eterna.
- **VENTUS** (Aria) - Progenitore: Zephira. Libertà, comunicazione, velocità. Spirito inquieto.
- **MENS** (Mente) - Progenitore: Ethelion. Conoscenza, illusioni, telepatia. Curiosità infinita.
- **ANIMA** (Spirito) - Progenitore: Morwyn. Morti, spiriti, giustizia ultraterrena. Serenità malinconica.
- **VIS** (Forza) - Progenitore: Magnus. Energia pura, potenziamento, gravità. Precisione matematica.
- **VITA** (Vita) - Progenitore: Silvana. Guarigione, natura, crescita organica. Amore universale.
- **SPATIUM** (Spazio) - Non ha Progenitore. Teletrasporto, dimensioni, distorsione.
- **TEMPUS** (Tempo) - Non ha Progenitore. Rallentamento, accelerazione, visioni temporali.

## CONSEGUENZE NARRATIVE
- L'uso intenso di una sfera porta a ECHO del Progenitore: tratti della personalità emergono temporaneamente
- I backlash non sono solo meccanici: hanno conseguenze narrative (un backlash di Ignis potrebbe bruciare qualcosa di prezioso)
- Le combinazioni tra sfere compatibili sono potenti ma rischiose
- Le sfere incompatibili (es. Ignis/Aqua) creano tensione nel caster

## PRIMA SESSIONE
Quando il giocatore descrive il proprio personaggio per la prima volta:
1. Usa [NAME: ...] e [CLASS: ...] per registrare identità
2. Assegna 3 punti in sfere coerenti con la descrizione [SPHERE: ...]
3. Descrivi l'ambiente iniziale con dettagli sensoriali

## REGOLE D'ORO
1. MAI fare scelte per il giocatore
2. MAI rivelare meccaniche fuori dai tag
3. Le conseguenze sono reali: la morte è possibile
4. Il mondo reagisce alle azioni del giocatore
5. Gli NPC hanno motivazioni proprie
6. I tag sono OBBLIGATORI per ogni evento meccanico

Inizia la sessione reagendo al giocatore. Buon gioco."""


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def build_character_context(character: dict) -> str:
    """Costruisce il contesto personaggio per il prompt."""
    if not character or not character.get('name'):
        return ''
    
    spheres = character.get('spheres', {})
    active_spheres = [f"{k}: {v}" for k, v in spheres.items() if v and v > 0]
    
    hp = character.get('hp', {})
    conditions = character.get('conditions', [])
    inventory = character.get('inventory', [])
    
    # Aggiungi contesto spaziale se disponibile
    char_id = character.get('id', '')
    spatial_context = ""
    if char_id:
        try:
            spatial_context = get_spatial_context(char_id)
            if spatial_context:
                spatial_context = f"\n\n[POSIZIONE NEL MONDO]\n{spatial_context}"
        except Exception:
            pass
    
    return f"""

[STATO ATTUALE PERSONAGGIO]
Nome: {character.get('name', 'Non definito')}
Classe: {character.get('class', 'Non definita')}
Livello: {character.get('level', 1)}
HP: {hp.get('current', 100)}/{hp.get('max', 100)}
Sfere: {', '.join(active_spheres) if active_spheres else 'Nessuna'}
Condizioni: {', '.join(conditions) if conditions else 'Nessuna'}
Inventario: {', '.join(inventory) if inventory else 'Vuoto'}{spatial_context}"""


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Endpoint principale per la chat con il Game Master.
    Usa Haiku per risposte veloci ed economiche.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'Message required'}), 400
        
        history = data.get('history', [])
        character = data.get('character', {})
        character_id = character.get('id', '')
        location_id = data.get('location_id', '')
        
        # Costruisci system prompt con contesto personaggio
        system = SYSTEM_PROMPT + build_character_context(character)
        
        # Aggiungi recap della location se disponibile
        if character_id and location_id:
            memory_mgr = get_memory_manager()
            recap = memory_mgr.get_recap(character_id, location_id)
            if recap:
                system += f"\n\n{recap}"
        
        # Prepara messaggi per Claude
        messages = []
        for msg in history[-20:]:  # Ultimi 20 messaggi
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', '')
            })
        
        # Aggiungi messaggio corrente
        messages.append({
            'role': 'user',
            'content': message
        })
        
        # Chiamata a Claude HAIKU (veloce, economico)
        response = client.messages.create(
            model=MODEL_HAIKU,
            max_tokens=1024,
            system=system,
            messages=messages
        )
        
        # Estrai testo dalla risposta
        response_text = ''
        for block in response.content:
            if block.type == 'text':
                response_text += block.text
        
        # Processa i tag di location
        location_report = {}
        if character_id:
            try:
                location_report = process_gm_response(character_id, response_text)
            except Exception as e:
                app.logger.warning(f'Location processing error: {str(e)}')
        
        # Salva automaticamente nella memoria della location
        if character_id and location_id:
            try:
                memory_mgr = get_memory_manager()
                memory_mgr.add_message(character_id, location_id, 'user', message)
                memory_mgr.add_message(character_id, location_id, 'assistant', response_text)
                
                # Estrai eventi chiave dai tag (semplificato)
                key_event = extract_key_event(message, response_text)
                if key_event:
                    memory_mgr.add_event(character_id, location_id, key_event)
            except Exception as e:
                app.logger.warning(f'Memory save error: {str(e)}')
        
        # Ritorna risposta con info sulle location modificate
        return jsonify({
            'response': response_text,
            'location_updates': location_report,
            'model': 'haiku'
        })
    
    except Exception as e:
        app.logger.error(f'Chat error: {str(e)}')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@app.route('/api/chat/expand', methods=['POST'])
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
        context_type = data.get('context_type', 'general')  # description, dialogue, combat, lore
        user_prompt = data.get('user_prompt', '')
        character = data.get('character', {})
        character_id = character.get('id', '')
        location_id = data.get('location_id', '')
        history = data.get('history', [])
        
        if not original_message:
            return jsonify({'error': 'Original message required'}), 400
        
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

        # Costruisci contesto
        system = SYSTEM_PROMPT + build_character_context(character)
        
        # Prepara messaggi con history per contesto
        messages = []
        for msg in history[-10:]:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', '')
            })
        
        messages.append({
            'role': 'user',
            'content': expansion_prompt
        })
        
        # Chiamata a Claude SONNET (dettagliato)
        response = client.messages.create(
            model=MODEL_SONNET,
            max_tokens=2048,  # Più spazio per dettagli
            system=system,
            messages=messages
        )
        
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
            app.logger.warning(f'Expansion logging error: {str(e)}')
        
        return jsonify({
            'expanded': expanded_text,
            'model': 'sonnet',
            'context_type': context_type
        })
    
    except Exception as e:
        app.logger.error(f'Expand error: {str(e)}')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@app.route('/api/character/<char_id>/switch-location', methods=['POST'])
def switch_location(char_id):
    """
    Gestisce il cambio di location.
    Salva la chat corrente, carica quella della nuova location.
    """
    try:
        data = request.get_json()
        from_location = data.get('from_location', '')
        to_location = data.get('to_location', '')
        current_messages = data.get('messages', [])
        
        if not to_location:
            return jsonify({'error': 'to_location required'}), 400
        
        memory_mgr = get_memory_manager()
        result = memory_mgr.switch_location(
            character_id=char_id,
            from_location=from_location,
            to_location=to_location,
            current_messages=current_messages
        )
        
        return jsonify(result)
    
    except Exception as e:
        app.logger.error(f'Switch location error: {str(e)}')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@app.route('/api/expansion-stats', methods=['GET'])
def expansion_stats():
    """Ottiene statistiche sulle espansioni (per il team)."""
    try:
        days = request.args.get('days', 7, type=int)
        logger = get_expansion_logger()
        stats = logger.get_stats(days=days)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def extract_key_event(user_message: str, gm_response: str) -> str:
    """
    Estrae un evento chiave dalla conversazione per il riassunto.
    Semplificato: cerca tag significativi.
    """
    import re
    
    # Pattern per tag significativi
    patterns = [
        (r'\[NPC:\s*([^\]]+)\]', lambda m: f"Incontrato {m.group(1).split('|')[0].strip()}"),
        (r'\[ITEM:\s*([^\]]+)\]', lambda m: f"Ottenuto {m.group(1)}"),
        (r'\[LORE:\s*([^\]]+)\]', lambda m: f"Scoperto {m.group(1).split('|')[0].strip()}"),
        (r'\[DMG:\s*(\d+)[^\]]*\|\s*target:\s*enemy', lambda m: f"Combattimento ({m.group(1)} danni inflitti)"),
        (r'\[SPELL:\s*success', lambda m: "Incantesimo riuscito"),
    ]
    
    for pattern, formatter in patterns:
        match = re.search(pattern, gm_response, re.IGNORECASE)
        if match:
            return formatter(match)
    
    # Se nessun tag trovato, niente evento
    return ""


def extract_tags_from_text(text: str) -> list:
    """Estrae tutti i tag [...] da un testo."""
    import re
    return re.findall(r'\[([A-Z_]+):[^\]]+\]', text)


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'statisfy-rpg'
    })


# ═══════════════════════════════════════════════════════════════
# WORLD API - Mappa gerarchica
# ═══════════════════════════════════════════════════════════════

@app.route('/api/character/<character_id>/map', methods=['GET'])
def get_character_map(character_id):
    """Ottieni la mappa/stato del personaggio nel mondo."""
    world_mgr = get_world_manager()
    state_mgr = get_player_state_manager()
    state = state_mgr.get_state(character_id)
    
    return jsonify({
        'position': state.position.to_dict(),
        'discovered_sublocations': state.discovered_sublocations,
        'visit_history': state.visit_history,
        'npc_dispositions': state.npc_dispositions
    })


@app.route('/api/character/<character_id>/location', methods=['GET'])
def get_character_location(character_id):
    """Ottieni informazioni sulla posizione corrente con gerarchia."""
    location_info = get_current_location_info(character_id)
    if not location_info:
        return jsonify({
            'current_location': None,
            'has_location': False
        })
    # Aggiungi current_location come alias per compatibilità
    location_info['current_location'] = location_info.get('current')
    return jsonify(location_info)


@app.route('/api/character/<character_id>/location/exits', methods=['GET'])
def get_location_exits(character_id):
    """Ottieni le uscite dalla posizione corrente."""
    location_info = get_current_location_info(character_id)
    if not location_info:
        return jsonify({'exits': [], 'current': None})
    
    return jsonify({
        'exits': location_info.get('exits', []),
        'current': location_info.get('current', None)
    })


@app.route('/api/character/<character_id>/location/visited', methods=['GET'])
def get_visited_locations(character_id):
    """Ottieni le location visitate dal personaggio."""
    state_mgr = get_player_state_manager()
    state = state_mgr.get_state(character_id)
    
    visited = []
    for loc_id, timestamps in state.visit_history.items():
        visited.append({
            'id': loc_id,
            'visit_count': len(timestamps),
            'first_visit': timestamps[0] if timestamps else None,
            'last_visit': timestamps[-1] if timestamps else None
        })
    
    return jsonify({'visited': visited})


@app.route('/api/character/<character_id>/location/neighborhood', methods=['GET'])
def get_neighborhood(character_id):
    """
    Ottieni il grafo completo dell'esplorazione per la mini-mappa.
    Include: tutti i nodi visitati, edges, posizione corrente.
    """
    world_mgr = get_world_manager()
    graph_data = world_mgr.get_exploration_graph(character_id)
    
    if not graph_data.get('has_location'):
        return jsonify({
            'has_location': False,
            'current': None,
            'nodes': [],
            'edges': [],
            'breadcrumb': []
        })
    
    return jsonify(graph_data)


# ═══════════════════════════════════════════════════════════════
# DATABASE API - Characters & Game Data
# ═══════════════════════════════════════════════════════════════

from db.mock_db import db


@app.route('/api/classes', methods=['GET'])
def get_classes():
    """Ottieni tutte le classi disponibili."""
    classes = db.get_all_classes()
    return jsonify(classes)


@app.route('/api/skills', methods=['GET'])
def get_skills():
    """Ottieni skills. Query params: category, roots_only."""
    category = request.args.get('category')
    roots_only = request.args.get('roots_only', 'false').lower() == 'true'
    
    if roots_only:
        skills = db.get_root_skills()
    elif category:
        skills = db.get_skills_by_category(category)
    else:
        skills = db.get_all('skills')
    
    return jsonify(skills)


@app.route('/api/skills/<skill_id>/tree', methods=['GET'])
def get_skill_tree(skill_id):
    """Ottieni albero skill da una root."""
    tree = db.get_skill_tree(skill_id)
    return jsonify(tree)


@app.route('/api/character/slot/<int:slot>', methods=['GET'])
def get_character_by_slot(slot):
    """Ottieni personaggio per slot (0-5)."""
    char = db.get_character_by_slot(slot)
    if not char:
        return jsonify({'exists': False, 'slot': slot})
    
    # Ottieni dati completi con relazioni
    full_char = db.get_character_full(char['id'])
    return jsonify({
        'exists': True,
        'character': full_char
    })


@app.route('/api/character', methods=['POST'])
def create_character():
    """Crea un nuovo personaggio."""
    data = request.json
    
    # Validazione
    required = ['slot', 'name', 'class_id']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Campo mancante: {field}'}), 400
    
    # Verifica slot libero
    existing = db.get_character_by_slot(data['slot'])
    if existing:
        return jsonify({'error': 'Slot già occupato'}), 409
    
    # Verifica nome univoco
    name_check = db.get_where('characters', name=data['name'])
    if name_check:
        return jsonify({'error': 'Nome già in uso'}), 409
    
    # Valida stats (base 10 + 20 punti)
    str_stat = data.get('str', 10)
    dex_stat = data.get('dex', 10)
    vit_stat = data.get('vit', 10)
    int_stat = data.get('int', 10)
    
    total_points = (str_stat - 10) + (dex_stat - 10) + (vit_stat - 10) + (int_stat - 10)
    if total_points > 20:
        return jsonify({'error': 'Troppi punti assegnati (max 20 extra)'}), 400
    if any(s < 5 for s in [str_stat, dex_stat, vit_stat, int_stat]):
        return jsonify({'error': 'Stats minimo 5'}), 400
    
    try:
        character = db.create_character(
            slot=data['slot'],
            name=data['name'],
            class_id=data['class_id'],
            str_stat=str_stat,
            dex_stat=dex_stat,
            vit_stat=vit_stat,
            int_stat=int_stat
        )
        
        # Ritorna personaggio completo
        full_char = db.get_character_full(character['id'])
        return jsonify({
            'success': True,
            'character': full_char
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f'Create character error: {str(e)}')
        return jsonify({'error': 'Errore interno'}), 500


@app.route('/api/character/<character_id>', methods=['GET'])
def get_character(character_id):
    """Ottieni personaggio per ID con tutti i dettagli."""
    char = db.get_character_full(character_id)
    if not char:
        return jsonify({'error': 'Personaggio non trovato'}), 404
    return jsonify(char)


@app.route('/api/character/<character_id>', methods=['PUT'])
def update_character(character_id):
    """Aggiorna personaggio (HP, mana, XP, etc.)."""
    data = request.json
    
    # Filtra solo campi modificabili
    allowed = ['hp_current', 'mana_current', 'xp', 'level']
    updates = {k: v for k, v in data.items() if k in allowed}
    
    if not updates:
        return jsonify({'error': 'Nessun campo valido da aggiornare'}), 400
    
    updated = db.update('characters', character_id, updates)
    if not updated:
        return jsonify({'error': 'Personaggio non trovato'}), 404
    
    return jsonify(updated)


@app.route('/api/character/<character_id>', methods=['DELETE'])
def delete_character(character_id):
    """Elimina personaggio e tutte le sue relazioni."""
    success = db.delete_character(character_id)
    if not success:
        return jsonify({'error': 'Personaggio non trovato'}), 404
    return jsonify({'success': True})


@app.route('/api/character/<character_id>/skill', methods=['POST'])
def add_skill_to_character(character_id):
    """Aggiunge una skill al personaggio."""
    data = request.json
    skill_id = data.get('skill_id')
    mastery = data.get('mastery', 1)
    
    if not skill_id:
        return jsonify({'error': 'skill_id richiesto'}), 400
    
    result = db.add_character_skill(character_id, skill_id, mastery)
    return jsonify(result)


@app.route('/api/character/<character_id>/skill/<skill_tag>', methods=['PATCH'])
def update_skill_mastery(character_id, skill_tag):
    """Aggiorna mastery di una skill."""
    data = request.json
    delta = data.get('delta', 1)
    
    result = db.update_skill_mastery(character_id, skill_tag, delta)
    if not result:
        return jsonify({'error': 'Skill non trovata o non posseduta'}), 404
    
    return jsonify(result)


@app.route('/api/character/<character_id>/inventory', methods=['POST'])
def add_inventory_item(character_id):
    """Aggiunge item all'inventario."""
    data = request.json
    item_name = data.get('item_name')
    quantity = data.get('quantity', 1)
    
    if not item_name:
        return jsonify({'error': 'item_name richiesto'}), 400
    
    result = db.add_to_inventory(character_id, item_name, quantity)
    return jsonify(result)


@app.route('/api/character/<character_id>/inventory/<item_name>', methods=['DELETE'])
def remove_inventory_item(character_id, item_name):
    """Rimuove item dall'inventario."""
    quantity = request.args.get('quantity', 1, type=int)
    
    success = db.remove_from_inventory(character_id, item_name, quantity)
    if not success:
        return jsonify({'error': 'Item non trovato'}), 404
    
    return jsonify({'success': True})


@app.route('/api/character/<character_id>/equip', methods=['POST'])
def equip_item(character_id):
    """Equipaggia un item dall'inventario in uno slot specifico."""
    data = request.json
    item_name = data.get('item_name')
    slot = data.get('slot')
    
    if not item_name or not slot:
        return jsonify({'error': 'item_name e slot richiesti'}), 400
    
    result = db.equip_from_inventory(character_id, item_name, slot)
    if not result:
        return jsonify({'error': 'Slot non compatibile con questo item'}), 400
    
    return jsonify({'success': True, 'equipped': result})


@app.route('/api/character/<character_id>/unequip', methods=['POST'])
def unequip_item(character_id):
    """Rimuove un item equipaggiato e lo mette in inventario."""
    data = request.json
    slot = data.get('slot')
    
    if not slot:
        return jsonify({'error': 'slot richiesto'}), 400
    
    result = db.unequip_to_inventory(character_id, slot)
    if not result:
        return jsonify({'error': 'Nessun item in questo slot'}), 404
    
    return jsonify({'success': True})


@app.route('/api/character/<character_id>/move-equipment', methods=['POST'])
def move_equipment(character_id):
    """Sposta un item da uno slot a un altro."""
    data = request.json
    from_slot = data.get('from_slot')
    to_slot = data.get('to_slot')
    
    if not from_slot or not to_slot:
        return jsonify({'error': 'from_slot e to_slot richiesti'}), 400
    
    result = db.move_equipment(character_id, from_slot, to_slot)
    if not result:
        return jsonify({'error': 'Impossibile spostare: slot non compatibile o vuoto'}), 400
    
    return jsonify({'success': True, 'moved': result})


@app.route('/api/slots', methods=['GET'])
def get_all_slots():
    """Ottieni stato di tutti gli slot (per dashboard)."""
    slots = []
    for i in range(6):
        char = db.get_character_by_slot(i)
        if char:
            char_class = db.get_by_id('classes', char['class_id'])
            slots.append({
                'slot': i,
                'exists': True,
                'id': char['id'],
                'name': char['name'],
                'class_name': char_class['name'] if char_class else 'Unknown',
                'level': char['level']
            })
        else:
            slots.append({
                'slot': i,
                'exists': False
            })
    return jsonify(slots)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
