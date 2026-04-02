// journalManager.js - Journal, quest log, and personal notes management
// Extracted from sheet.astro

const RARITY_COLORS = {
  comune: 'var(--ash)',
  non_comune: '#2ecc71',
  raro: '#3498db',
  epico: '#9b59b6',
  unico: '#e67e22',
  leggendario: '#f1c40f',
  mitico: '#e74c3c',
  divino: 'var(--accent)',
};

const RARITY_LABELS = {
  comune: 'Comune', non_comune: 'Non Comune', raro: 'Raro',
  epico: 'Epico', unico: 'Unico', leggendario: 'Leggendario',
  mitico: 'Mitico', divino: 'Divino',
};

/**
 * Initialize the journal manager module.
 * @param {Object} config
 * @param {Function} config.getCharacter - Returns current character data
 * @param {Function} config.getCharacterQuests - API: getCharacterQuests(characterId)
 * @param {Function} config.updateQuestNotes - API: updateQuestNotes(characterId, questId, notes)
 * @param {Function} config.getJournalNotes - API: getJournalNotes(characterId)
 * @param {Function} config.apiSaveJournalNote - API: saveJournalNote(characterId, content, noteId?)
 * @param {Function} config.apiDeleteJournalNote - API: deleteJournalNote(characterId, noteId)
 * @returns {{ load: Function, render: Function }}
 */
export function initJournalManager(config) {
  const { getCharacter, getCharacterQuests, updateQuestNotes, getJournalNotes, apiSaveJournalNote, apiDeleteJournalNote } = config;

  // ── State ──
  let journalLoaded = false;
  let questsData = { active: [], history: [] };
  let journalNotesData = [];
  let selectedQuestId = null;
  let selectedNoteId = null;
  let noteSaveTimer = null;
  let questNoteSaveTimer = null;

  // ══════════════════════════════════════════════════════
  // LOAD
  // ══════════════════════════════════════════════════════

  async function loadJournal() {
    const character = getCharacter();
    if (!character) return;
    try {
      const [questRes, notesRes] = await Promise.all([
        getCharacterQuests(character.id),
        getJournalNotes(character.id),
      ]);
      questsData = questRes;
      journalNotesData = notesRes.notes || [];
      journalLoaded = true;
      renderJournal();
    } catch (e) {
      console.error('Errore caricamento journal:', e);
    }
  }

  // ══════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════

  function renderJournal() {
    renderQuestList('active', questsData.active || [], 'quest-list-active', 'quest-empty-active');
    renderQuestList('history', questsData.history || [], 'quest-list-history', 'quest-empty-history');
    renderJournalNotesList();
  }

  function renderQuestList(type, quests, containerId, emptyId) {
    const container = document.getElementById(containerId);
    const empty = document.getElementById(emptyId);

    if (!quests.length) {
      empty.style.display = 'block';
      // Remove old cards but keep empty msg
      container.querySelectorAll('.quest-card').forEach(c => c.remove());
      return;
    }
    empty.style.display = 'none';

    const html = quests.map(q => {
      const rarity = q.rarity || 'comune';
      const color = RARITY_COLORS[rarity] || 'var(--ash)';
      const statusIcon = type === 'active' ? '\u{1F536}' : (q.status === 'completed' ? '\u2705' : '\u274C');
      const progress = q.objectives?.length
        ? q.objectives.filter(o => o.done).length + '/' + q.objectives.length
        : '';
      const isSelected = q.quest_id === selectedQuestId;

      return `<div class="quest-card ${isSelected ? 'selected' : ''}" data-quest-id="${q.quest_id}" data-quest-type="${type}" style="--quest-color: ${color}">
        <div class="quest-card-icon">${statusIcon}</div>
        <div class="quest-card-info">
          <span class="quest-card-name">${q.quest_name}</span>
          ${progress ? `<span class="quest-card-progress">${progress} obiettivi</span>` : ''}
        </div>
      </div>`;
    }).join('');

    // Replace only quest cards
    container.querySelectorAll('.quest-card').forEach(c => c.remove());
    container.insertAdjacentHTML('beforeend', html);

    // Bind click
    container.querySelectorAll('.quest-card').forEach(card => {
      card.addEventListener('click', () => {
        const qid = card.dataset.questId;
        const qtype = card.dataset.questType;
        selectQuest(qid, qtype);
      });
    });
  }

  function selectQuest(questId, type) {
    selectedQuestId = questId;
    selectedNoteId = null;

    // Highlight sidebar
    document.querySelectorAll('.quest-card, .note-card').forEach(c => c.classList.remove('selected'));
    const card = document.querySelector(`.quest-card[data-quest-id="${questId}"]`);
    if (card) card.classList.add('selected');

    // Find quest data
    const allQuests = [...(questsData.active || []), ...(questsData.history || [])];
    const quest = allQuests.find(q => q.quest_id === questId);
    if (!quest) return;

    renderQuestDetail(quest);
  }

  function renderQuestDetail(quest) {
    const emptyState = document.getElementById('journal-empty-state');
    const detailView = document.getElementById('quest-detail-view');
    const noteView = document.getElementById('note-detail-view');

    emptyState.style.display = 'none';
    noteView.style.display = 'none';
    detailView.style.display = 'block';

    // Header
    document.getElementById('quest-detail-name').textContent = quest.quest_name;

    const rarity = quest.rarity || 'comune';
    const rarityBadge = document.getElementById('quest-detail-rarity');
    rarityBadge.textContent = RARITY_LABELS[rarity] || rarity;
    rarityBadge.style.background = RARITY_COLORS[rarity] || 'var(--ash)';
    rarityBadge.style.color = ['leggendario', 'divino'].includes(rarity) ? 'var(--void)' : '#fff';

    const scopeBadge = document.getElementById('quest-detail-scope');
    scopeBadge.textContent = quest.scope || 'principale';

    const statusBadge = document.getElementById('quest-detail-status');
    const statusMap = { active: 'In Corso', completed: 'Completata', failed: 'Fallita' };
    statusBadge.textContent = statusMap[quest.status] || quest.status;
    statusBadge.className = `quest-badge status-badge status-${quest.status}`;

    // Objectives
    const objContainer = document.getElementById('quest-detail-objectives');
    if (quest.objectives?.length) {
      objContainer.innerHTML = `<h3 class="section-label">Obiettivi</h3>` +
        quest.objectives.map(obj => {
          const done = obj.done;
          const progress = obj.current !== undefined && obj.target !== undefined
            ? `${obj.current}/${obj.target}`
            : '';
          const pct = obj.target ? Math.min((obj.current || 0) / obj.target * 100, 100) : (done ? 100 : 0);
          return `<div class="objective-item ${done ? 'done' : ''}">
            <span class="obj-check">${done ? '\u2611' : '\u2610'}</span>
            <span class="obj-text">${obj.description}</span>
            ${progress ? `<div class="obj-progress-bar"><div class="obj-progress-fill" style="width:${pct}%"></div><span class="obj-progress-text">${progress}</span></div>` : ''}
          </div>`;
        }).join('');
    } else {
      objContainer.innerHTML = '';
    }

    // Rewards
    const rewardsContainer = document.getElementById('quest-detail-rewards');
    if (quest.rewards) {
      const r = quest.rewards;
      let rewardsHtml = '<h3 class="section-label">Ricompense</h3><div class="rewards-grid">';
      if (r.xp) rewardsHtml += `<span class="reward-chip">\u2B50 ${r.xp} XP</span>`;
      if (r.corone) rewardsHtml += `<span class="reward-chip">\u{1F451} ${r.corone} Corone</span>`;
      if (r.items?.length) r.items.forEach(i => { rewardsHtml += `<span class="reward-chip">\u{1F4E6} ${i}</span>`; });
      rewardsHtml += '</div>';
      rewardsContainer.innerHTML = rewardsHtml;
    } else {
      rewardsContainer.innerHTML = '';
    }

    // Dates
    const datesContainer = document.getElementById('quest-detail-dates');
    let datesHtml = '<div class="quest-dates-grid">';
    if (quest.started_at) datesHtml += `<span class="quest-date-item">Iniziata: ${formatDate(quest.started_at)}</span>`;
    if (quest.completed_at) datesHtml += `<span class="quest-date-item">Completata: ${formatDate(quest.completed_at)}</span>`;
    datesHtml += '</div>';
    datesContainer.innerHTML = datesHtml;

    // Notes textarea
    const textarea = document.getElementById('quest-notes-textarea');
    textarea.value = quest.player_notes || '';
    document.getElementById('quest-notes-status').textContent = '';

    // Remove old listener, add new
    const newTextarea = textarea.cloneNode(true);
    textarea.parentNode.replaceChild(newTextarea, textarea);
    newTextarea.addEventListener('input', () => {
      debouncedSaveQuestNotes(quest.quest_id, newTextarea.value);
    });
  }

  function debouncedSaveQuestNotes(questId, notes) {
    const character = getCharacter();
    clearTimeout(questNoteSaveTimer);
    document.getElementById('quest-notes-status').textContent = 'Salvando...';
    questNoteSaveTimer = setTimeout(async () => {
      try {
        await updateQuestNotes(character.id, questId, notes);
        document.getElementById('quest-notes-status').textContent = 'Salvato \u2713';
        // Update local data
        const allQuests = [...(questsData.active || []), ...(questsData.history || [])];
        const q = allQuests.find(q => q.quest_id === questId);
        if (q) q.player_notes = notes;
        setTimeout(() => {
          const el = document.getElementById('quest-notes-status');
          if (el && el.textContent === 'Salvato \u2713') el.textContent = '';
        }, 2000);
      } catch (e) {
        document.getElementById('quest-notes-status').textContent = 'Errore salvataggio';
        console.error('Save quest notes error:', e);
      }
    }, 800);
  }

  // ── Journal Notes (personal) ──

  function renderJournalNotesList() {
    const container = document.getElementById('journal-notes-list');
    if (!journalNotesData.length) {
      container.innerHTML = '<p class="empty-msg" style="padding:var(--space-sm)">Nessuna nota</p>';
      return;
    }

    container.innerHTML = journalNotesData.map(note => {
      const preview = (note.content || '').substring(0, 40) + ((note.content || '').length > 40 ? '...' : '');
      const isSelected = note.id === selectedNoteId;
      return `<div class="note-card ${isSelected ? 'selected' : ''}" data-note-id="${note.id}">
        <span class="note-card-preview">${preview || 'Nota vuota'}</span>
        <span class="note-card-date">${formatDate(note.updated_at || note.created_at)}</span>
      </div>`;
    }).join('');

    container.querySelectorAll('.note-card').forEach(card => {
      card.addEventListener('click', () => selectNote(card.dataset.noteId));
    });
  }

  function selectNote(noteId) {
    selectedNoteId = noteId;
    selectedQuestId = null;

    document.querySelectorAll('.quest-card, .note-card').forEach(c => c.classList.remove('selected'));
    const card = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
    if (card) card.classList.add('selected');

    const note = journalNotesData.find(n => n.id === noteId);
    if (!note) return;

    const emptyState = document.getElementById('journal-empty-state');
    const questView = document.getElementById('quest-detail-view');
    const noteView = document.getElementById('note-detail-view');

    emptyState.style.display = 'none';
    questView.style.display = 'none';
    noteView.style.display = 'flex';

    const textarea = document.getElementById('journal-note-textarea');
    textarea.value = note.content || '';
    document.getElementById('note-save-status').textContent = '';

    // Re-bind input
    const newTextarea = textarea.cloneNode(true);
    textarea.parentNode.replaceChild(newTextarea, textarea);
    newTextarea.addEventListener('input', () => {
      debouncedSaveNote(noteId, newTextarea.value);
    });
  }

  function debouncedSaveNote(noteId, content) {
    const character = getCharacter();
    clearTimeout(noteSaveTimer);
    document.getElementById('note-save-status').textContent = 'Salvando...';
    noteSaveTimer = setTimeout(async () => {
      try {
        await apiSaveJournalNote(character.id, content, noteId);
        document.getElementById('note-save-status').textContent = 'Salvato \u2713';
        // Update local
        const note = journalNotesData.find(n => n.id === noteId);
        if (note) note.content = content;
        renderJournalNotesList();
        // Re-select to keep highlight
        const card = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
        if (card) card.classList.add('selected');
        setTimeout(() => {
          const el = document.getElementById('note-save-status');
          if (el && el.textContent === 'Salvato \u2713') el.textContent = '';
        }, 2000);
      } catch (e) {
        document.getElementById('note-save-status').textContent = 'Errore';
        console.error('Save note error:', e);
      }
    }, 800);
  }

  // ── Add note button ──
  document.getElementById('btn-add-note').addEventListener('click', async () => {
    const character = getCharacter();
    if (!character) return;
    try {
      const result = await apiSaveJournalNote(character.id, '');
      if (result.note) {
        journalNotesData.unshift(result.note);
        renderJournalNotesList();
        selectNote(result.note.id);
      }
    } catch (e) {
      console.error('Add note error:', e);
    }
  });

  // ── Delete note button ──
  document.getElementById('btn-delete-note').addEventListener('click', async () => {
    const character = getCharacter();
    if (!character || !selectedNoteId) return;
    try {
      await apiDeleteJournalNote(character.id, selectedNoteId);
      journalNotesData = journalNotesData.filter(n => n.id !== selectedNoteId);
      selectedNoteId = null;
      renderJournalNotesList();
      // Show empty state
      document.getElementById('note-detail-view').style.display = 'none';
      document.getElementById('quest-detail-view').style.display = 'none';
      document.getElementById('journal-empty-state').style.display = 'flex';
    } catch (e) {
      console.error('Delete note error:', e);
    }
  });

  // ── Utility ──

  function formatDate(isoStr) {
    if (!isoStr) return '\u2014';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch { return isoStr; }
  }

  // ── Public API ──

  function isLoaded() {
    return journalLoaded;
  }

  return { load: loadJournal, render: renderJournal, isLoaded };
}
