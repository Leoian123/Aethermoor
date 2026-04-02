/**
 * STATISFY RPG - Game State Manager
 *
 * DEPRECATED: Lo stato del personaggio è ora gestito dal backend (MockDB).
 * Il frontend riceve lo stato aggiornato nella response di /api/chat.
 * Questo file è mantenuto solo per compatibilità con import esistenti.
 */

// Stato di default per un nuovo personaggio
const DEFAULT_CHARACTER = {
  name: null,
  class: null,
  level: 1,
  hp: { current: 100, max: 100 },
  mana: { current: 50, max: 50 },
  stats: {
    str: 10,
    dex: 10,
    vit: 10,
    int: 10
  },
  spheres: {
    ignis: 0,
    aqua: 0,
    terra: 0,
    ventus: 0,
    mens: 0,
    anima: 0,
    vis: 0,
    vita: 0,
    spatium: 0,
    tempus: 0
  },
  conditions: [],
  inventory: [],
  equipment: {
    weapon: null,
    armor: null,
    accessory: null
  }
};

// Stato globale del gioco
export const gameState = {
  character: { ...DEFAULT_CHARACTER },
  history: [],
  currentSlot: null
};

/**
 * Carica lo stato da localStorage
 * @param {number} slot - Slot del personaggio (0-5)
 */
export function loadGameState(slot = 0) {
  const key = `statisfy_slot_${slot}`;
  const saved = localStorage.getItem(key);
  
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      Object.assign(gameState.character, DEFAULT_CHARACTER, parsed.character);
      gameState.history = parsed.history || [];
      gameState.currentSlot = slot;
      return true;
    } catch (e) {
      console.warn('Errore caricamento stato:', e);
      return false;
    }
  }
  return false;
}

/**
 * Salva lo stato in localStorage
 */
export function saveGameState() {
  if (gameState.currentSlot === null) return;
  
  const key = `statisfy_slot_${gameState.currentSlot}`;
  const data = {
    character: gameState.character,
    history: gameState.history,
    lastSaved: new Date().toISOString()
  };
  
  localStorage.setItem(key, JSON.stringify(data));
}

/**
 * Resetta lo stato a default
 */
export function resetGameState() {
  gameState.character = { ...DEFAULT_CHARACTER };
  gameState.history = [];
}

/**
 * Ottiene tutti gli slot salvati
 * @returns {Array} Lista degli slot con info base
 */
export function getSavedSlots() {
  const slots = [];
  
  for (let i = 0; i < 6; i++) {
    const key = `statisfy_slot_${i}`;
    const saved = localStorage.getItem(key);
    
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        slots.push({
          slot: i,
          name: parsed.character?.name || 'Sconosciuto',
          class: parsed.character?.class || 'Nessuna',
          level: parsed.character?.level || 1,
          lastSaved: parsed.lastSaved || null,
          exists: true
        });
      } catch (e) {
        slots.push({ slot: i, exists: false });
      }
    } else {
      slots.push({ slot: i, exists: false });
    }
  }
  
  return slots;
}

/**
 * Elimina uno slot salvato
 * @param {number} slot - Slot da eliminare
 */
export function deleteSlot(slot) {
  const key = `statisfy_slot_${slot}`;
  localStorage.removeItem(key);
}

/**
 * Modifica HP del personaggio
 * @param {number} delta - Variazione (positivo = heal, negativo = danno)
 */
export function modifyHP(delta) {
  const hp = gameState.character.hp;
  hp.current = Math.max(0, Math.min(hp.max, hp.current + delta));
}

/**
 * Modifica Mana del personaggio
 * @param {number} delta - Variazione
 */
export function modifyMana(delta) {
  const mana = gameState.character.mana;
  mana.current = Math.max(0, Math.min(mana.max, mana.current + delta));
}

/**
 * Aggiunge una condizione
 * @param {string} condition - Nome condizione
 */
export function addCondition(condition) {
  if (!gameState.character.conditions.includes(condition)) {
    gameState.character.conditions.push(condition);
  }
}

/**
 * Rimuove una condizione
 * @param {string} condition - Nome condizione
 */
export function removeCondition(condition) {
  gameState.character.conditions = gameState.character.conditions
    .filter(c => c.toLowerCase() !== condition.toLowerCase());
}

/**
 * Aggiunge un item all'inventario
 * @param {string} item - Nome item
 */
export function addItem(item) {
  if (!gameState.character.inventory.includes(item)) {
    gameState.character.inventory.push(item);
  }
}

/**
 * Rimuove un item dall'inventario
 * @param {string} item - Nome item
 */
export function removeItem(item) {
  gameState.character.inventory = gameState.character.inventory
    .filter(i => i.toLowerCase() !== item.toLowerCase());
}

/**
 * Modifica valore di una sfera
 * @param {string} sphere - Nome sfera
 * @param {number} delta - Variazione
 */
export function modifySphere(sphere, delta) {
  const sphereKey = sphere.toLowerCase();
  if (gameState.character.spheres.hasOwnProperty(sphereKey)) {
    gameState.character.spheres[sphereKey] += delta;
  }
}

// Auto-save ogni 5 secondi quando in gioco
let autoSaveInterval = null;

export function startAutoSave() {
  if (autoSaveInterval) return;
  autoSaveInterval = setInterval(saveGameState, 5000);
}

export function stopAutoSave() {
  if (autoSaveInterval) {
    clearInterval(autoSaveInterval);
    autoSaveInterval = null;
  }
}
