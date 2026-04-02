/**
 * STATISFY RPG - Memo Manager
 * Gestione del FAB appunti rapidi: apertura/chiusura modale, salvataggio/caricamento localStorage, debounce.
 */

/**
 * Inizializza il memo manager.
 *
 * @param {Object} config
 * @param {Function} config.getCharacterId - () => string|null — restituisce l'id del personaggio corrente
 * @param {HTMLElement} config.memoFab       - pulsante FAB
 * @param {HTMLElement} config.memoOverlay   - overlay scuro
 * @param {HTMLElement} config.memoClose     - pulsante chiudi
 * @param {HTMLTextAreaElement} config.memoTextarea - textarea degli appunti
 * @param {HTMLElement} config.memoStatus    - span stato salvataggio
 * @returns {{ open: Function, close: Function, save: Function, load: Function }}
 */
export function initMemoManager(config) {
  const {
    getCharacterId,
    memoFab,
    memoOverlay,
    memoClose,
    memoTextarea,
    memoStatus,
  } = config;

  let saveTimer = null;

  // ═══════════════════════════════════════
  // STORAGE KEY
  // ═══════════════════════════════════════

  function getMemoKey() {
    const id = getCharacterId();
    return id ? `statisfy_memo_${id}` : 'statisfy_memo_temp';
  }

  // ═══════════════════════════════════════
  // LOAD / SAVE
  // ═══════════════════════════════════════

  function load() {
    try {
      const saved = localStorage.getItem(getMemoKey());
      if (saved && memoTextarea) memoTextarea.value = saved;
    } catch { /* silently ignore */ }
  }

  function save() {
    try {
      if (memoTextarea) localStorage.setItem(getMemoKey(), memoTextarea.value);
    } catch { /* silently ignore */ }
  }

  // ═══════════════════════════════════════
  // OPEN / CLOSE
  // ═══════════════════════════════════════

  function open() {
    memoOverlay?.classList.add('open');
    load();
    setTimeout(() => memoTextarea?.focus(), 100);
  }

  function close() {
    save();
    memoOverlay?.classList.remove('open');
  }

  // ═══════════════════════════════════════
  // EVENT LISTENERS
  // ═══════════════════════════════════════

  memoFab?.addEventListener('click', open);

  memoClose?.addEventListener('click', close);

  memoOverlay?.addEventListener('click', (e) => {
    if (e.target === memoOverlay) close();
  });

  memoTextarea?.addEventListener('input', () => {
    if (saveTimer) clearTimeout(saveTimer);
    if (memoStatus) memoStatus.textContent = 'Salvando...';
    saveTimer = setTimeout(() => {
      save();
      if (memoStatus) memoStatus.textContent = 'Salvato in locale';
    }, 500);
  });

  // ═══════════════════════════════════════
  // PUBLIC API
  // ═══════════════════════════════════════

  return { open, close, save, load };
}
