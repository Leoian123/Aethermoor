/**
 * STATISFY RPG - Tag Parser
 * Parsing e applicazione dei tag meccanici [TAG: value]
 */

// NOTA: Lo stato del personaggio è ora gestito dal backend.
// Le funzioni di mutazione (applyTags) non sono più necessarie.

// Regex per estrarre i tag [TAG: value]
const TAG_REGEX = /\[([A-Z_]+):\s*([^\]]+)\]/g;

// Regex per i tag del mondo (per rimuoverli dalla visualizzazione)
const LOCATION_TAG_PATTERNS = [
  // Nuovo sistema seed-based
  /<move\s+to="[^"]+"\s*\/?>/gi,
  /<enter\s+to="[^"]+"\s*\/?>/gi,
  /<exit\s*\/?>/gi,
  /<create_sublocation[^>]*>[\s\S]*?<\/create_sublocation>/gi,
  /<npc_disposition[^>]*\/?>/gi,
  // Formato parentesi quadre (fallback Haiku)
  /\[MOVE\s+to="[^"]+"\s*\]/gi,
  /\[ENTER\s+to="[^"]+"\s*\]/gi,
  /\[EXIT\s*\]/gi,
  /\[CREATE_SUBLOCATION[^\]]*\][^\[]*/gi,
  /\[NPC_DISPOSITION[^\]]*\]/gi,
  // Vecchi pattern per backward compatibility
  /<node_create[^>]*>[\s\S]*?<\/node_create>/gi,
  /<location_create[^>]*>[\s\S]*?<\/location_create>/gi,
  /<edge_create[^>]*\/?>/gi,
  /<movement[^>]*\/?>/gi,
  /\[NODE_CREATE[^\]]*\][^\[]*/gi,
  /\[LOCATION_CREATE[^\]]*\][^\[]*/gi,
  /\[EDGE_CREATE[^\]]*\]/gi,
  /\[MOVEMENT[^\]]*\]/gi,
  // Tag UI-only (non narrativi, non vanno mostrati)
  /\[SHOP:\s*[^\]]+\]/gi,
];

/**
 * Parsa i sotto-campi di un tag
 * Es: "24 | target: enemy | source: sword" → { value: "24", target: "enemy", source: "sword" }
 * @param {string} value - Valore grezzo del tag
 * @returns {Object} Campi parsati
 */
export function parseTagFields(value) {
  const fields = {};
  const parts = value.split('|').map(p => p.trim());
  
  parts.forEach((part, index) => {
    if (index === 0) {
      // Primo valore è sempre il valore principale
      fields.value = part;
    } else if (part.includes(':')) {
      // Altri sono chiave: valore
      const colonIndex = part.indexOf(':');
      const key = part.slice(0, colonIndex).trim().toLowerCase();
      const val = part.slice(colonIndex + 1).trim();
      fields[key] = val;
    }
  });
  
  return fields;
}

/**
 * Estrae tutti i tag da un testo
 * @param {string} text - Testo con tag
 * @returns {Array} Lista di tag { type, value, raw }
 */
export function parseTags(text) {
  const tags = [];
  let match;
  
  // Reset regex
  TAG_REGEX.lastIndex = 0;
  
  while ((match = TAG_REGEX.exec(text)) !== null) {
    tags.push({
      type: match[1],
      value: match[2].trim(),
      raw: match[0]
    });
  }
  
  return tags;
}

/**
 * Applica i tag allo stato del gioco
 * @param {Array} tags - Lista di tag parsati
 */
export function applyTags(tags) {
  tags.forEach(tag => {
    const fields = parseTagFields(tag.value);
    const target = (fields.target || 'self').toLowerCase();
    
    switch (tag.type) {
      case 'DMG': {
        const amount = parseInt(fields.value) || 0;
        
        if (target === 'self') {
          modifyHP(-amount);
          console.log(`[DMG] Player subisce ${amount} danni`);
        } else {
          // Enemy o NPC specifico - non modifica scheda player
          console.log(`[DMG] ${target} subisce ${amount} danni`);
        }
        break;
      }
      
      case 'HEAL': {
        const amount = parseInt(fields.value) || 0;
        
        if (target === 'self') {
          modifyHP(amount);
          console.log(`[HEAL] Player recupera ${amount} HP`);
        } else {
          console.log(`[HEAL] ${target} recupera ${amount} HP`);
        }
        break;
      }
      
      case 'MANA': {
        const amount = parseInt(fields.value) || 0;
        modifyMana(amount); // Sempre sul player
        console.log(`[MANA] Player ${amount > 0 ? 'recupera' : 'consuma'} ${Math.abs(amount)} mana`);
        break;
      }
      
      case 'CONDITION': {
        const condName = fields.value;
        
        if (target === 'self') {
          addCondition(condName);
          console.log(`[CONDITION] Player ottiene: ${condName}`);
        } else {
          console.log(`[CONDITION] ${target} ottiene: ${condName}`);
        }
        break;
      }
      
      case 'CONDITION_REMOVE': {
        const condName = fields.value;
        
        if (target === 'self') {
          removeCondition(condName);
          console.log(`[CONDITION_REMOVE] Player perde: ${condName}`);
        } else {
          console.log(`[CONDITION_REMOVE] ${target} perde: ${condName}`);
        }
        break;
      }
      
      case 'NAME': {
        // Solo se non già impostato (protezione)
        if (!gameState.character.name) {
          gameState.character.name = fields.value;
          console.log(`[NAME] Impostato: ${fields.value}`);
        } else {
          console.log(`[NAME] Ignorato - nome già impostato: ${gameState.character.name}`);
        }
        break;
      }
      
      case 'CLASS': {
        // Solo se non già impostato (protezione)
        if (!gameState.character.class) {
          gameState.character.class = fields.value;
          console.log(`[CLASS] Impostata: ${fields.value}`);
        } else {
          console.log(`[CLASS] Ignorato - classe già impostata: ${gameState.character.class}`);
        }
        break;
      }
      
      case 'LEVEL': {
        const newLevel = parseInt(fields.value);
        if (newLevel && newLevel > gameState.character.level) {
          gameState.character.level = newLevel;
          console.log(`[LEVEL] Nuovo livello: ${newLevel}`);
        }
        break;
      }
      
      case 'ITEM': {
        addItem(fields.value);
        console.log(`[ITEM] Aggiunto: ${fields.value}`);
        break;
      }
      
      case 'ITEM_REMOVE': {
        removeItem(fields.value);
        console.log(`[ITEM_REMOVE] Rimosso: ${fields.value}`);
        break;
      }
      
      case 'SPHERE': {
        // Formato: "ignis +2" o "mens -1"
        const sphereMatch = fields.value.match(/(\w+)\s*([+-]?\d+)/i);
        if (sphereMatch) {
          const sphere = sphereMatch[1];
          const delta = parseInt(sphereMatch[2]);
          modifySphere(sphere, delta);
          console.log(`[SPHERE] ${sphere} ${delta > 0 ? '+' : ''}${delta}`);
        }
        break;
      }
      
      case 'XP': {
        const xp = parseInt(fields.value) || 0;
        // TODO: implementare sistema XP
        console.log(`[XP] Guadagnati: ${xp}`);
        break;
      }
      
      case 'ECHO': {
        const progenitor = fields.value;
        const intensity = fields.intensity || 'low';
        console.log(`[ECHO] Risonanza con ${progenitor} (${intensity})`);
        break;
      }
      
      case 'BACKLASH': {
        const type = fields.value;
        const severity = fields.severity || 'minor';
        console.log(`[BACKLASH] ${type} (${severity})`);
        break;
      }
      
      case 'SPELL': {
        const result = fields.value;
        const effect = fields.effect || '';
        console.log(`[SPELL] ${result}: ${effect}`);
        break;
      }
      
      case 'ROLL': {
        const type = fields.value;
        const result = fields.result || '?';
        const dc = fields.dc || '?';
        console.log(`[ROLL] ${type}: ${result} vs DC ${dc}`);
        break;
      }
      
      case 'LOCATION': {
        // TODO: world state
        console.log(`[LOCATION] ${fields.value}`);
        break;
      }
      
      case 'NPC': {
        const npcName = fields.value;
        const disposition = fields.disposition || 'neutral';
        console.log(`[NPC] ${npcName} (${disposition})`);
        break;
      }
      
      case 'LORE': {
        const category = fields.value;
        const info = fields.info || '';
        console.log(`[LORE] ${category}: ${info}`);
        break;
      }

      case 'SHOP': {
        const npcId = fields.value;
        console.log(`[SHOP] Apertura negozio: ${npcId}`);
        window.dispatchEvent(new CustomEvent('open-shop', { detail: { npcId } }));
        break;
      }

      case 'CORONE': {
        const amount = parseInt(fields.value) || 0;
        console.log(`[CORONE] ${amount > 0 ? '+' : ''}${amount} corone`);
        break;
      }

      default:
        console.log(`[${tag.type}] Non gestito:`, tag.value);
    }
  });
}

/**
 * Formatta il testo evidenziando i tag per la visualizzazione
 * @param {string} text - Testo con tag
 * @returns {string} HTML con tag evidenziati
 */
export function formatTagsForDisplay(text) {
  return text.replace(TAG_REGEX, '<span class="tag">$&</span>');
}

/**
 * Rimuove i tag di location dal testo (non vanno mostrati al giocatore)
 * @param {string} text - Testo con tag XML
 * @returns {string} Testo pulito
 */
export function stripLocationTags(text) {
  let result = text;
  for (const pattern of LOCATION_TAG_PATTERNS) {
    result = result.replace(pattern, '');
  }
  // Pulisci linee vuote multiple
  result = result.replace(/\n\s*\n\s*\n/g, '\n\n');
  return result.trim();
}

/**
 * Prepara il testo per la visualizzazione:
 * - Rimuove tag location XML
 * - Evidenzia tag meccanici [TAG: value]
 * @param {string} text - Testo grezzo dal GM
 * @returns {string} HTML pronto per la visualizzazione
 */
export function prepareTextForDisplay(text) {
  const withoutLocation = stripLocationTags(text);
  return formatTagsForDisplay(withoutLocation);
}
