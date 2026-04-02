/**
 * STATISFY RPG - API Client
 * Comunicazione con il backend Flask
 */

import { getToken, clearAuth } from './auth.js';

const API_BASE = import.meta.env.PUBLIC_API_URL || 'http://localhost:5000';

// ── API Call Counter (debug) ──
let _apiCallTotal = 0;
const _apiCallCounts = {};

/**
 * Helper per chiamate API (con auth automatico)
 */
async function apiCall(endpoint, options = {}) {
  // Debug: traccia chiamate API
  _apiCallTotal++;
  const method = options.method || 'GET';
  const key = `${method} ${endpoint.split('?')[0]}`;
  _apiCallCounts[key] = (_apiCallCounts[key] || 0) + 1;
  console.debug(`[API #${_apiCallTotal}] ${key} (x${_apiCallCounts[key]})`);

  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  };

  // Attach Bearer token se presente
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers,
    ...options
  });

  // 401 globale: token scaduto/invalido → logout
  if (response.status === 401) {
    const body = await response.json().catch(() => ({}));
    if (body.error === 'token_expired' || body.error === 'invalid_token') {
      clearAuth();
      window.location.href = '/login';
      return;
    }
    // auth_error (credenziali sbagliate) — lascia propagare come errore
    const err = new Error(body.message || 'Non autorizzato');
    err.status = 401;
    err.errorType = body.error || 'auth_error';
    err.serverMessage = body.message || null;
    throw err;
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const err = new Error(body.message || `HTTP ${response.status}`);
    err.status = response.status;
    err.errorType = body.error || 'unknown';
    err.serverMessage = body.message || null;
    throw err;
  }

  return response.json();
}

// ═══════════════════════════════════════
// AUTH
// ═══════════════════════════════════════

/**
 * Registra nuovo utente
 */
export async function registerUser(username, password) {
  return apiCall('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
}

/**
 * Login utente
 */
export async function loginUser(username, password) {
  return apiCall('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
}

/**
 * Verifica token e ottieni dati utente
 */
export async function getCurrentUser() {
  return apiCall('/api/auth/me');
}

// ═══════════════════════════════════════
// CHAT
// ═══════════════════════════════════════

/**
 * Invia un messaggio al Game Master (usa Haiku)
 */
export async function sendChatMessage(message, history = [], character = {}, locationId = '') {
  return apiCall('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ 
      message, 
      history, 
      character,
      location_id: locationId
    })
  });
}

/**
 * Espande un messaggio con Sonnet per maggiore dettaglio
 */
export async function expandMessage(originalMessage, contextType, character = {}, locationId = '', history = [], userPrompt = '') {
  return apiCall('/api/chat/expand', {
    method: 'POST',
    body: JSON.stringify({
      original_message: originalMessage,
      context_type: contextType,
      character,
      location_id: locationId,
      history,
      user_prompt: userPrompt
    })
  });
}

/**
 * Cambia location - salva chat corrente, carica nuova
 */
export async function switchLocation(characterId, fromLocation, toLocation, currentMessages = []) {
  return apiCall(`/api/character/${characterId}/switch-location`, {
    method: 'POST',
    body: JSON.stringify({
      from_location: fromLocation,
      to_location: toLocation,
      messages: currentMessages
    })
  });
}

// ═══════════════════════════════════════
// SLOTS & CHARACTERS
// ═══════════════════════════════════════

/**
 * Ottieni stato di tutti gli slot
 */
export async function getAllSlots() {
  return apiCall('/api/slots');
}

/**
 * Ottieni personaggio per slot
 */
export async function getCharacterBySlot(slot) {
  return apiCall(`/api/character/slot/${slot}`);
}

/**
 * Crea nuovo personaggio
 */
export async function createCharacter(data) {
  return apiCall('/api/character', {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

/**
 * Elimina personaggio
 */
export async function deleteCharacter(characterId) {
  return apiCall(`/api/character/${characterId}`, {
    method: 'DELETE'
  });
}

/**
 * Aggiorna personaggio (HP, mana, etc.)
 */
export async function updateCharacter(characterId, data) {
  return apiCall(`/api/character/${characterId}`, {
    method: 'PUT',
    body: JSON.stringify(data)
  });
}

// ═══════════════════════════════════════
// CLASSES & SKILLS
// ═══════════════════════════════════════

/**
 * Ottieni tutte le classi
 */
export async function getClasses() {
  return apiCall('/api/classes');
}

/**
 * Ottieni skills
 */
export async function getSkills(options = {}) {
  const params = new URLSearchParams();
  if (options.category) params.append('category', options.category);
  if (options.rootsOnly) params.append('roots_only', 'true');
  
  const query = params.toString();
  return apiCall(`/api/skills${query ? `?${query}` : ''}`);
}

/**
 * Ottieni albero skill
 */
export async function getSkillTree(skillId) {
  return apiCall(`/api/skills/${skillId}/tree`);
}

// ═══════════════════════════════════════
// INVENTORY & EQUIPMENT
// ═══════════════════════════════════════

/**
 * Aggiungi item all'inventario
 */
export async function addToInventory(characterId, itemName, quantity = 1) {
  return apiCall(`/api/character/${characterId}/inventory`, {
    method: 'POST',
    body: JSON.stringify({ item_name: itemName, quantity })
  });
}

/**
 * Rimuovi item dall'inventario
 */
export async function removeFromInventory(characterId, itemName, quantity = 1) {
  return apiCall(`/api/character/${characterId}/inventory/${encodeURIComponent(itemName)}?quantity=${quantity}`, {
    method: 'DELETE'
  });
}

/**
 * Investe punti liberi da level-up nelle stats
 */
export async function investStats(characterId, statPoints) {
  return apiCall(`/api/character/${characterId}/invest-stats`, {
    method: 'POST',
    body: JSON.stringify(statPoints)
  });
}

/**
 * Equipaggia un item dall'inventario
 */
export async function equipItem(characterId, itemName, slot) {
  return apiCall(`/api/character/${characterId}/equip`, {
    method: 'POST',
    body: JSON.stringify({ item_name: itemName, slot: slot })
  });
}

/**
 * Rimuovi un item equipaggiato (torna in inventario)
 */
export async function unequipItem(characterId, slot) {
  return apiCall(`/api/character/${characterId}/unequip`, {
    method: 'POST',
    body: JSON.stringify({ slot: slot })
  });
}

/**
 * Sposta un item da uno slot equipaggiato a un altro
 */
export async function moveEquipment(characterId, fromSlot, toSlot) {
  return apiCall(`/api/character/${characterId}/move-equipment`, {
    method: 'POST',
    body: JSON.stringify({ from_slot: fromSlot, to_slot: toSlot })
  });
}

/**
 * Usa un consumabile dall'inventario
 */
export async function useItem(characterId, itemName) {
  return apiCall(`/api/character/${characterId}/use-item`, {
    method: 'POST',
    body: JSON.stringify({ item_name: itemName })
  });
}

/**
 * Ottieni inventario negozio NPC
 */
export async function getShop(characterId, npcId) {
  return apiCall(`/api/character/${characterId}/shop/${encodeURIComponent(npcId)}`);
}

/**
 * Compra item dal negozio NPC
 */
export async function buyFromShop(characterId, npcId, equipmentId) {
  return apiCall(`/api/character/${characterId}/shop/${encodeURIComponent(npcId)}/buy`, {
    method: 'POST',
    body: JSON.stringify({ equipment_id: equipmentId })
  });
}

/**
 * Vendi item al negozio NPC
 */
export async function sellToShop(characterId, npcId, itemName) {
  return apiCall(`/api/character/${characterId}/shop/${encodeURIComponent(npcId)}/sell`, {
    method: 'POST',
    body: JSON.stringify({ item_name: itemName })
  });
}

/**
 * Ottieni vendor con shop nella location corrente (zero AI calls)
 */
export async function getNearbyVendors(characterId) {
  return apiCall(`/api/character/${characterId}/nearby-vendors`);
}

// ═══════════════════════════════════════
// HEALTH
// ═══════════════════════════════════════

/**
 * Verifica lo stato del backend
 */
export async function checkHealth() {
  try {
    await apiCall('/api/health');
    return true;
  } catch (e) {
    return false;
  }
}

// ═══════════════════════════════════════
// LOCATION / MAP
// ═══════════════════════════════════════

/**
 * Ottieni la mappa completa del personaggio
 */
export async function getCharacterMap(characterId) {
  return apiCall(`/api/character/${characterId}/map`);
}

/**
 * Ottieni informazioni sulla location corrente
 */
export async function getCurrentLocation(characterId) {
  return apiCall(`/api/character/${characterId}/location`);
}

/**
 * Ottieni le uscite visibili dalla location corrente
 */
export async function getLocationExits(characterId) {
  return apiCall(`/api/character/${characterId}/location/exits`);
}

/**
 * Ottieni le location visitate dal personaggio
 */
export async function getVisitedLocations(characterId) {
  return apiCall(`/api/character/${characterId}/location/visited`);
}

/**
 * Ottieni neighborhood per mini-mappa (location corrente + vicini)
 */
export async function getNeighborhood(characterId) {
  return apiCall(`/api/character/${characterId}/location/neighborhood`);
}

/**
 * Ottieni il grafo del mondo a un dato livello di profondita' per la World Map
 * @param {string} characterId
 * @param {number} depth - 0=regioni, 1=zone, 2=location, 3=sublocation, 4+=nested
 * @param {string|null} parentId - Richiesto per depth > 0
 */
export async function getWorldGraph(characterId, depth = 0, parentId = null) {
  let endpoint = `/api/character/${characterId}/world-graph?depth=${depth}`;
  if (parentId) {
    endpoint += `&parent_id=${encodeURIComponent(parentId)}`;
  }
  return apiCall(endpoint);
}

/**
 * Ottieni preview dettagliato di una location per il widget mappa
 */
export async function getLocationPreview(characterId, locationId) {
  return apiCall(`/api/character/${characterId}/location-preview/${encodeURIComponent(locationId)}`);
}

/**
 * Trova il percorso tra due location
 */
export async function findPath(characterId, fromId, toId) {
  return apiCall(`/api/character/${characterId}/location/path?from=${encodeURIComponent(fromId)}&to=${encodeURIComponent(toId)}`);
}

// ═══════════════════════════════════════
// QUEST & JOURNAL
// ═══════════════════════════════════════

/**
 * Ottieni quest attive e storico del personaggio
 */
export async function getCharacterQuests(characterId) {
  return apiCall(`/api/character/${characterId}/quests`);
}

/**
 * Aggiorna le note del giocatore su una quest
 */
export async function updateQuestNotes(characterId, questId, notes) {
  return apiCall(`/api/character/${characterId}/quests/${questId}/notes`, {
    method: 'PATCH',
    body: JSON.stringify({ notes })
  });
}

/**
 * Ottieni le note generali del diario
 */
export async function getJournalNotes(characterId) {
  return apiCall(`/api/character/${characterId}/journal-notes`);
}

/**
 * Salva una nota del diario (crea o aggiorna)
 */
export async function saveJournalNote(characterId, content, noteId = null) {
  return apiCall(`/api/character/${characterId}/journal-notes`, {
    method: 'POST',
    body: JSON.stringify({ content, id: noteId })
  });
}

/**
 * Elimina una nota del diario
 */
export async function deleteJournalNote(characterId, noteId) {
  return apiCall(`/api/character/${characterId}/journal-notes/${noteId}`, {
    method: 'DELETE'
  });
}
