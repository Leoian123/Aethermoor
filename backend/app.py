"""
STATISFY RPG - Flask Backend
Game Master AI powered by Claude
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

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
[LOCATION: nome] - Spostamento
[NPC: nome | disposition: friendly/neutral/hostile] - Interazione NPC
[LORE: categoria | info] - Conoscenza sbloccata
[XP: X] - Esperienza guadagnata

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
    
    return f"""

[STATO ATTUALE PERSONAGGIO]
Nome: {character.get('name', 'Non definito')}
Classe: {character.get('class', 'Non definita')}
Livello: {character.get('level', 1)}
HP: {hp.get('current', 100)}/{hp.get('max', 100)}
Sfere: {', '.join(active_spheres) if active_spheres else 'Nessuna'}
Condizioni: {', '.join(conditions) if conditions else 'Nessuna'}
Inventario: {', '.join(inventory) if inventory else 'Vuoto'}"""


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint principale per la chat con il Game Master."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'Message required'}), 400
        
        history = data.get('history', [])
        character = data.get('character', {})
        
        # Costruisci system prompt con contesto personaggio
        system = SYSTEM_PROMPT + build_character_context(character)
        
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
        
        # Chiamata a Claude
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1024,
            system=system,
            messages=messages
        )
        
        # Estrai testo dalla risposta
        response_text = ''
        for block in response.content:
            if block.type == 'text':
                response_text += block.text
        
        return jsonify({'response': response_text})
    
    except Exception as e:
        app.logger.error(f'Chat error: {str(e)}')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'statisfy-rpg'
    })


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
