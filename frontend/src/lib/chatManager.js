/**
 * STATISFY RPG - Chat Manager
 * Gestione completa della chat di gioco: messaggi, persistenza, focus/expand, location change.
 */

import { sendChatMessage, expandMessage, switchLocation } from './api.js';
import { parseTags, formatTagsForDisplay, stripLocationTags } from './tagParser.js';

/**
 * Inizializza il chat manager.
 *
 * @param {Object} config
 * @param {Function} config.getCharacter    - () => character object (mutable ref)
 * @param {Function} config.setCharacter    - (c) => void — aggiorna il character corrente
 * @param {Function} config.getCurrentLocationId - () => string
 * @param {Function} config.setCurrentLocationId - (id) => void
 * @param {Function} config.onHeaderUpdate  - () => void — callback per aggiornare header HP/XP
 * @param {Function} config.onMapRefresh    - () => void — callback per aggiornare la mini-mappa
 * @param {HTMLElement} config.chatMessages  - contenitore messaggi
 * @param {HTMLTextAreaElement} config.chatInput - textarea input
 * @param {HTMLButtonElement} config.btnSend - pulsante invio
 * @param {HTMLElement} config.typingIndicator - indicatore di digitazione
 * @returns {{ addMessage: Function, sendMessage: Function, loadHistory: Function, clear: Function }}
 */
export function initChatManager(config) {
  const {
    getCharacter,
    setCharacter,
    getCurrentLocationId,
    setCurrentLocationId,
    onHeaderUpdate,
    onMapRefresh,
    chatMessages,
    chatInput,
    btnSend,
    typingIndicator,
  } = config;

  let history = [];

  // ── Auto-retry su errori temporanei (529/503) ──
  const MAX_RETRIES = 3;
  const RETRY_DELAY_MS = 3000;

  // ═══════════════════════════════════════
  // CHAT PERSISTENCE (localStorage)
  // ═══════════════════════════════════════

  function getChatStorageKey() {
    const character = getCharacter();
    if (!character) return '';
    return `statisfy_chat_${character.id}_${getCurrentLocationId() || 'default'}`;
  }

  function saveChat() {
    const key = getChatStorageKey();
    if (!key) return;
    try {
      localStorage.setItem(key, JSON.stringify(history));
    } catch (e) {
      console.warn('Impossibile salvare chat:', e);
    }
  }

  function loadChat() {
    const key = getChatStorageKey();
    if (!key) return;
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        history = JSON.parse(saved);
        // Ripopola UI
        history.forEach(msg => {
          addMessage(msg.content, msg.role === 'user', undefined, false);
        });
      }
    } catch (e) {
      console.warn('Impossibile caricare chat:', e);
      history = [];
    }
  }

  // ═══════════════════════════════════════
  // MESSAGES
  // ═══════════════════════════════════════

  function addMessage(content, isUser = false, messageId, persist = true) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message message--${isUser ? 'user' : 'ai'}`;
    msgDiv.dataset.messageId = messageId || `msg-${Date.now()}-${Math.random().toString(36).slice(2,7)}`;

    let displayContent = content;
    if (!isUser) {
      // Rimuovi tag location XML e formatta tag meccanici
      displayContent = stripLocationTags(content);
      displayContent = formatTagsForDisplay(displayContent);
    }

    // Struttura messaggio con pulsante Focus per messaggi GM
    if (isUser) {
      msgDiv.innerHTML = `
        <div class="message__label">Tu</div>
        <div class="message__content">${displayContent}</div>
      `;
    } else {
      const id = msgDiv.dataset.messageId;
      msgDiv.innerHTML = `
        <div class="message__header">
          <span class="message__label">Game Master</span>
          <button class="btn-focus" data-msg-id="${id}" title="Espandi con più dettagli">
            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="M21 21l-4.35-4.35"></path>
              <path d="M11 8v6M8 11h6"></path>
            </svg>
            Focus
          </button>
        </div>
        <div class="message__content" data-original="${encodeURIComponent(content)}">${displayContent}</div>
      `;

      // Aggiungi listener per il pulsante Focus
      const focusBtn = msgDiv.querySelector('.btn-focus');
      focusBtn?.addEventListener('click', () => handleFocus(id, content));
    }

    if (typingIndicator && chatMessages) {
      chatMessages.insertBefore(msgDiv, typingIndicator);
    } else {
      chatMessages?.appendChild(msgDiv);
    }

    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    return msgDiv;
  }

  function addRecapMessage(recap) {
    if (!recap) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message message--recap';
    msgDiv.innerHTML = `
      <div class="message__label">\u{1F4DC} Memoria</div>
      <div class="message__content">${recap.replace(/\n/g, '<br>')}</div>
    `;

    if (typingIndicator && chatMessages) {
      chatMessages.insertBefore(msgDiv, typingIndicator);
    } else {
      chatMessages?.appendChild(msgDiv);
    }
  }

  // ═══════════════════════════════════════
  // LEVEL-UP NOTIFICATION
  // ═══════════════════════════════════════

  function addLevelUpMessage(action) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message message--levelup';

    const bonusText = action.xp_bonus_pct > 0
      ? `(bonus INT: +${action.xp_bonus_pct}%)`
      : '';

    msgDiv.innerHTML = `
      <div class="message__label">\u26A1 LEVEL UP!</div>
      <div class="message__content">
        <strong>Livello ${action.new_level} raggiunto!</strong><br>
        +${action.gained_effective} XP ${bonusText}<br>
        HP e Mana ripristinati al massimo!<br>
        +10 punti da investire disponibili
      </div>
    `;

    if (typingIndicator && chatMessages) {
      chatMessages.insertBefore(msgDiv, typingIndicator);
    } else {
      chatMessages?.appendChild(msgDiv);
    }

    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  // ═══════════════════════════════════════
  // CORONE NOTIFICATION
  // ═══════════════════════════════════════

  function addCoroneMessage(action) {
    const msgDiv = document.createElement('div');
    const isGain = action.amount > 0;
    msgDiv.className = `message message--corone message--corone-${isGain ? 'gain' : 'loss'}`;

    msgDiv.innerHTML = `
      <div class="message__label">🪙 ${isGain ? 'Corone Guadagnate' : 'Corone Spese'}</div>
      <div class="message__content">
        <strong>${isGain ? '+' : ''}${action.amount}</strong> corone
        &nbsp;\u2014&nbsp; Totale: <strong>${action.new_corone}</strong>
      </div>
    `;

    if (typingIndicator && chatMessages) {
      chatMessages.insertBefore(msgDiv, typingIndicator);
    } else {
      chatMessages?.appendChild(msgDiv);
    }

    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  // ═══════════════════════════════════════
  // FOCUS (Espansione con Sonnet)
  // ═══════════════════════════════════════

  async function handleFocus(messageId, originalContent) {
    // Trova il messaggio
    const msgDiv = document.querySelector(`[data-message-id="${messageId}"]`);
    if (!msgDiv) return;

    const contentDiv = msgDiv.querySelector('.message__content');
    const focusBtn = msgDiv.querySelector('.btn-focus');

    if (!contentDiv || !focusBtn) return;

    // Gia' espanso?
    if (msgDiv.classList.contains('expanded')) {
      // Toggle back to original
      const original = decodeURIComponent(contentDiv.getAttribute('data-original') || '');
      let displayContent = stripLocationTags(original);
      displayContent = formatTagsForDisplay(displayContent);
      contentDiv.innerHTML = displayContent;
      msgDiv.classList.remove('expanded');
      focusBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
          <circle cx="11" cy="11" r="8"></circle>
          <path d="M21 21l-4.35-4.35"></path>
          <path d="M11 8v6M8 11h6"></path>
        </svg>
        Focus
      `;
      return;
    }

    // Mostra loading
    focusBtn.disabled = true;
    focusBtn.innerHTML = `
      <span class="loading-spinner"></span>
      Espando...
    `;

    try {
      // Determina il tipo di contesto
      const contextType = detectContextType(originalContent);

      const character = getCharacter();
      const data = await expandMessage(
        originalContent,
        contextType,
        character,
        getCurrentLocationId(),
        history.slice(-10)
      );

      // Aggiorna contenuto con versione espansa
      let expandedDisplay = stripLocationTags(data.expanded);
      expandedDisplay = formatTagsForDisplay(expandedDisplay);
      contentDiv.innerHTML = expandedDisplay;

      // Marca come espanso
      msgDiv.classList.add('expanded');
      focusBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
          <circle cx="11" cy="11" r="8"></circle>
          <path d="M21 21l-4.35-4.35"></path>
          <path d="M8 11h6"></path>
        </svg>
        Riduci
      `;

    } catch (error) {
      console.error('Errore espansione:', error);
      focusBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
          <circle cx="11" cy="11" r="8"></circle>
          <path d="M21 21l-4.35-4.35"></path>
          <path d="M11 8v6M8 11h6"></path>
        </svg>
        Focus
      `;
    }

    focusBtn.disabled = false;
  }

  function detectContextType(content) {
    // Rileva il tipo di contesto per analytics
    if (content.includes('[DMG:') || content.includes('[SPELL:')) return 'combat';
    if (content.includes('[NPC:')) return 'dialogue';
    if (content.includes('[LORE:')) return 'lore';
    if (content.includes('[ITEM:')) return 'discovery';
    return 'description';
  }

  // ═══════════════════════════════════════
  // TYPING INDICATOR
  // ═══════════════════════════════════════

  function showTyping() {
    typingIndicator?.classList.add('active');
    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }

  function hideTyping() {
    typingIndicator?.classList.remove('active');
  }

  // ═══════════════════════════════════════
  // LOCATION CHANGE
  // ═══════════════════════════════════════

  async function handleLocationChange(fromLocation, toLocation) {
    const character = getCharacter();
    if (!character) return;

    try {
      const result = await switchLocation(
        character.id,
        fromLocation,
        toLocation,
        history
      );

      // Aggiorna location corrente
      setCurrentLocationId(toLocation);

      // Pulisci UI e history prima di ricaricare
      history = [];
      if (chatMessages) {
        const messages = chatMessages.querySelectorAll('.message');
        messages.forEach(m => m.remove());
      }

      // Se c'e' un recap (non e' la prima visita), mostralo
      if (result.recap) {
        addRecapMessage(result.recap);
      }

      // Popola chat con messaggi dal backend (source of truth)
      if (result.messages && result.messages.length > 0) {
        history = result.messages.map(m => ({
          role: m.role, content: m.content
        }));
        result.messages.forEach(msg => {
          addMessage(msg.content, msg.role === 'user', undefined, false);
        });
      }

      // Sincronizza localStorage
      saveChat();

    } catch (error) {
      console.error('Errore switch location:', error);
    }
  }

  // ═══════════════════════════════════════
  // SEND MESSAGE
  // ═══════════════════════════════════════

  async function sendMessage() {
    const text = chatInput?.value.trim();
    const character = getCharacter();
    if (!text || !character) return;

    addMessage(text, true);
    history.push({ role: 'user', content: text });
    saveChat();  // Salva dopo messaggio user

    if (chatInput) {
      chatInput.value = '';
      chatInput.style.height = 'auto';
    }
    if (btnSend) btnSend.disabled = true;

    showTyping();

    // Tenta invio con auto-retry su errori temporanei
    await _attemptSend(text, character, 0);

    if (btnSend) btnSend.disabled = false;
    chatInput?.focus();
  }

  /**
   * Tenta l'invio del messaggio al GM con auto-retry ricorsivo.
   * Su errori 529/503, mostra un messaggio temporaneo e riprova dopo 3s.
   */
  async function _attemptSend(text, character, attempt) {
    try {
      const data = await sendChatMessage(
        text,
        history.slice(-20),
        character,
        getCurrentLocationId()
      );

      hideTyping();

      // Parse tag (solo per logging + dispatch eventi client-side)
      const tags = parseTags(data.response);
      console.log('Tags:', tags);
      console.log('Model:', data.model);

      // Dispatch tag che richiedono azione client-side (non stateful)
      for (const tag of tags) {
        if (tag.type === 'SHOP') {
          const npcId = tag.value.trim();
          window.dispatchEvent(new CustomEvent('open-shop', { detail: { npcId } }));
        }
      }

      // Aggiorna stato personaggio dal backend (source of truth)
      if (data.character) {
        setCharacter(data.character);
        onHeaderUpdate();
      }

      // Controlla azioni meccaniche applicate dal backend
      if (data.location_updates?.mechanical_applied) {
        for (const action of data.location_updates.mechanical_applied) {
          if (action.type === 'xp') {
            if (action.levels_gained > 0) {
              addLevelUpMessage(action);
            } else {
              console.log(`XP guadagnata: +${action.gained_effective} (${action.old_xp} → ${action.new_xp})`);
            }
          }
          if (action.type === 'corone') {
            addCoroneMessage(action);
          }
        }
      }

      // Log location updates se presenti
      if (data.location_updates) {
        console.log('Location updates:', data.location_updates);

        // Aggiorna mini-mappa se ci sono stati cambiamenti
        if (data.location_updates.locations_created?.length > 0 ||
            data.location_updates.movements?.length > 0 ||
            data.location_updates.modifications?.length > 0) {
          onMapRefresh();
        }

        // Se c'e' stato un movimento, aggiorna location corrente
        if (data.location_updates.movements?.length > 0) {
          const lastMovement = data.location_updates.movements[data.location_updates.movements.length - 1];
          // Supporta sia oggetto {to: "..."} che stringa diretta
          const newLocation = typeof lastMovement === 'string' ? lastMovement : lastMovement.to;
          if (newLocation) {
            await handleLocationChange(getCurrentLocationId(), newLocation);
          }
        }
      }

      const messageId = `msg-${Date.now()}`;
      addMessage(data.response, false, messageId);
      history.push({ role: 'assistant', content: data.response });
      saveChat();  // Salva dopo messaggio assistant

    } catch (error) {
      hideTyping();

      // Auto-retry su errori temporanei (529 overloaded, 503 service unavailable)
      if ((error.status === 529 || error.status === 503) && attempt < MAX_RETRIES) {
        const retryMsg = addMessage(
          `*\u23F3 Server sovraccarico (${error.status}). Nuovo tentativo tra 3 secondi... (${attempt + 1}/${MAX_RETRIES})*`,
          false
        );
        console.warn(`[Retry ${attempt + 1}/${MAX_RETRIES}] Errore ${error.status}, riprovo tra ${RETRY_DELAY_MS}ms...`);
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
        retryMsg.remove();  // Rimuovi messaggio di retry temporaneo
        showTyping();
        return _attemptSend(text, character, attempt + 1);
      }

      // Errore definitivo (non retryable o tentativi esauriti)
      let errorMsg = '*La connessione con il piano astrale si \u00e8 interrotta momentaneamente...*';

      if (error.status === 529 || error.status === 503) {
        errorMsg = `*\u26A0\uFE0F Server sovraccarico dopo ${MAX_RETRIES} tentativi. Riprova tra qualche minuto.*`;
      } else if (error.errorType === 'ai_service_error') {
        errorMsg = `*${error.serverMessage || 'Il Game Master non \u00e8 raggiungibile...'}*`;
      } else if (error.errorType === 'validation_error') {
        errorMsg = `*Il messaggio non \u00e8 stato accettato: ${error.serverMessage || 'dati non validi'}*`;
      } else if (error.status === 0 || error.message === 'Failed to fetch') {
        errorMsg = '*Il server non risponde... le porte di Aethermoor sono chiuse.*';
      }

      addMessage(errorMsg, false);
      console.error('Chat error:', error);
    }
  }

  // ═══════════════════════════════════════
  // EVENT LISTENERS
  // ═══════════════════════════════════════

  btnSend?.addEventListener('click', sendMessage);

  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  chatInput?.addEventListener('input', () => {
    if (chatInput) {
      chatInput.style.height = 'auto';
      chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + 'px';
    }
  });

  // ═══════════════════════════════════════
  // PUBLIC API
  // ═══════════════════════════════════════

  return {
    addMessage,
    sendMessage,
    loadHistory: loadChat,
    saveCurrentChat: saveChat,
    clear() {
      history = [];
      if (chatMessages) {
        // Rimuovi tutti i messaggi ma mantieni typing indicator
        const messages = chatMessages.querySelectorAll('.message');
        messages.forEach(m => m.remove());
      }
    },
    handleLocationChange,
  };
}
