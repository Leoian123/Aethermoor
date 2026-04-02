// equipmentManager.js - Equipment rendering, inventory, drag-and-drop, paper doll (12 slot)
// Supporta: two-hand lock, tooltip confronto stats, context menu, consumabili

const SLOT_LABELS = {
  head: 'Testa',
  neck: 'Collo',
  shoulders: 'Spalle',
  chest: 'Petto',
  gloves: 'Guanti',
  main_hand: 'Mano Px',
  off_hand: 'Mano Sx',
  belt: 'Cintura',
  ring: 'Anello',
  legs: 'Gambe',
  feet: 'Piedi',
  back: 'Schiena'
};

const SLOT_ICONS = {
  head: '\u{1FA96}',
  neck: '\u{1F4FF}',
  shoulders: '\u{1F9E5}',
  chest: '\u{1F6E1}\uFE0F',
  gloves: '\u{1F9E4}',
  main_hand: '\u2694\uFE0F',
  off_hand: '\u{1F6E1}\uFE0F',
  belt: '\u{1F4BF}',
  ring: '\u{1F48D}',
  legs: '\u{1FA73}',
  feet: '\u{1F462}',
  back: '\u{1F9E3}'
};

/**
 * Initialize the equipment manager module.
 * @param {Object} config
 * @param {Function} config.getCharacter - Returns current character data
 * @param {Function} config.apiEquip - equipItem(characterId, itemName, slotId)
 * @param {Function} config.apiUnequip - unequipItem(characterId, slotId)
 * @param {Function} config.apiMove - moveEquipment(characterId, fromSlot, toSlot)
 * @param {Function} config.apiUseItem - useItem(characterId, itemName)
 * @param {Function} config.apiDiscard - removeFromInventory(characterId, itemName, quantity)
 * @param {Function} config.refreshCharacter - Refreshes character data and re-renders
 * @param {HTMLElement} config.tooltipEl - Shared tooltip element
 * @param {Function} config.moveTooltip - Shared moveTooltip(event) handler
 * @param {Function} config.hideTooltip - Shared hideTooltip() handler
 * @returns {{ render: Function, refresh: Function }}
 */
export function initEquipmentManager(config) {
  const { getCharacter, apiEquip, apiUnequip, apiMove, apiUseItem, apiDiscard, refreshCharacter, tooltipEl, moveTooltip, hideTooltip } = config;

  let draggedItem = null;
  let contextMenuEl = null;
  let longPressTimer = null;
  let invFilter = 'all';
  let invSort = 'name';

  // Crea context menu container
  createContextMenu();

  // Setup filtro/sort toolbar
  setupInventoryToolbar();

  // ══════════════════════════════════════════════════════
  // TWO-HAND LOCK
  // ══════════════════════════════════════════════════════

  function applyTwoHandLock() {
    const character = getCharacter();
    const twoHandStatus = character.two_hand_status || { is_two_hand: false };
    const offHandSlot = document.querySelector('.equip-slot[data-slot="off_hand"]');
    const mainHandSlot = document.querySelector('.equip-slot[data-slot="main_hand"]');

    if (!offHandSlot) return;

    if (twoHandStatus.is_two_hand) {
      offHandSlot.classList.add('locked');
      const dropArea = offHandSlot.querySelector('.slot-drop-area');
      if (dropArea) {
        dropArea.innerHTML = `
          <div class="slot-lock-content">
            <span class="slot-lock-icon">\u{1F512}</span>
            <span class="slot-lock-text">Bloccato</span>
          </div>
        `;
      }
      if (mainHandSlot) {
        const label = mainHandSlot.querySelector('.slot-label');
        if (label) label.textContent = 'Due Mani';
      }
    } else {
      offHandSlot.classList.remove('locked');
      if (mainHandSlot) {
        const label = mainHandSlot.querySelector('.slot-label');
        if (label) label.textContent = SLOT_LABELS.main_hand;
      }
    }
  }

  // ══════════════════════════════════════════════════════
  // EQUIPMENT RENDERING
  // ══════════════════════════════════════════════════════

  function renderEquipment() {
    const character = getCharacter();

    document.querySelectorAll('.slot-drop-area').forEach(el => {
      const slot = el.parentElement;
      const slotId = slot.dataset.slot;
      const icon = SLOT_ICONS[slotId] || '\u{1F4E6}';
      el.innerHTML = `<span class="slot-icon">${icon}</span><span class="slot-empty">Vuoto</span>`;
      slot.classList.remove('filled');
    });

    if (character.equipment?.length) {
      character.equipment.forEach(item => {
        const dropArea = document.getElementById(`slot-${item.equipped_slot}`);
        if (dropArea) {
          dropArea.innerHTML = createItemCard(item, true);
          dropArea.parentElement.classList.add('filled');

          const card = dropArea.querySelector('.item-card');
          setupItemCardEvents(card, item, true);
        }
      });
    }

    applyTwoHandLock();
  }

  // ══════════════════════════════════════════════════════
  // INVENTORY TOOLBAR (FILTRO + SORT)
  // ══════════════════════════════════════════════════════

  function setupInventoryToolbar() {
    // Tab filtro
    document.querySelectorAll('.inv-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.inv-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        invFilter = tab.dataset.filter;
        renderInventory();
      });
    });

    // Sort
    const sortEl = document.getElementById('inv-sort');
    if (sortEl) {
      sortEl.addEventListener('change', () => {
        invSort = sortEl.value;
        renderInventory();
      });
    }
  }

  function getFilteredInventory() {
    const character = getCharacter();
    let items = [...(character.inventory || [])];

    // Filtro per categoria
    if (invFilter !== 'all') {
      items = items.filter(item => (item.category || 'equipment') === invFilter);
    }

    // Sort
    const RARITY_ORDER = { common: 0, uncommon: 1, rare: 2, epic: 3, legendary: 4 };
    items.sort((a, b) => {
      switch (invSort) {
        case 'name': return (a.name || a.item_name || '').localeCompare(b.name || b.item_name || '');
        case 'rarity': return (RARITY_ORDER[b.rarity] || 0) - (RARITY_ORDER[a.rarity] || 0);
        case 'type': return (a.type || '').localeCompare(b.type || '');
        case 'level': return (b.item_level || 0) - (a.item_level || 0);
        default: return 0;
      }
    });

    return items;
  }

  function renderInventory() {
    const character = getCharacter();
    const grid = document.getElementById('inventory-grid');
    const empty = document.getElementById('inv-empty');
    const totalItems = character.inventory?.length || 0;

    // Aggiorna contatore capacita'
    const capacityEl = document.getElementById('inv-capacity');
    if (capacityEl) capacityEl.textContent = `${totalItems}/32`;

    const filtered = getFilteredInventory();

    if (!filtered.length) {
      empty.style.display = 'block';
      empty.textContent = invFilter === 'all' ? 'Inventario vuoto' : 'Nessun item in questa categoria';
      grid.innerHTML = '';
      return;
    }

    empty.style.display = 'none';
    grid.innerHTML = filtered.map(item => createItemCard(item, false)).join('');

    document.querySelectorAll('#inventory-grid .item-card').forEach(card => {
      const item = JSON.parse(card.dataset.item);
      setupItemCardEvents(card, item, false);
    });
  }

  function createItemCard(item, equipped) {
    const rarity = item.rarity || 'common';
    const icon = getItemIcon(item.type, item.equip_tags);
    const tags = item.equip_tags || [];
    const isConsumable = item.category === 'consumable';

    return `
      <div class="item-card ${rarity}${isConsumable ? ' consumable' : ''}"
           draggable="${isConsumable ? 'false' : 'true'}"
           data-item='${JSON.stringify(item).replace(/'/g, "&#39;")}'
           data-equipped="${equipped}"
           data-equip-tags="${tags.join(',')}"
           data-category="${item.category || 'equipment'}">
        <div class="item-icon">${icon}</div>
        <div class="item-details">
          <span class="item-name">${item.name || item.item_name}</span>
          <span class="item-type">${item.type || 'Oggetto'}</span>
        </div>
        ${item.quantity > 1 ? `<span class="item-qty">\u00D7${item.quantity}</span>` : ''}
      </div>
    `;
  }

  function getItemIcon(type, equipTags) {
    const tags = equipTags || [];

    if (tags.includes('head')) return '\u{1FA96}';
    if (tags.includes('shoulders')) return '\u{1F9E5}';
    if (tags.includes('gloves')) return '\u{1F9E4}';
    if (tags.includes('legs')) return '\u{1FA73}';
    if (tags.includes('feet')) return '\u{1F462}';
    if (tags.includes('ring')) return '\u{1F48D}';
    if (tags.includes('back')) return '\u{1F9E3}';
    if (tags.includes('neck')) return '\u{1F4FF}';
    if (tags.includes('belt')) return '\u{1F4BF}';

    const icons = {
      weapon: '\u2694\uFE0F',
      armor: '\u{1F6E1}\uFE0F',
      shield: '\u{1F6E1}\uFE0F',
      accessory: '\u{1F48D}',
      consumable: '\u{1F9EA}'
    };
    return icons[type] || '\u{1F4E6}';
  }

  // ══════════════════════════════════════════════════════
  // TOOLTIP CON CONFRONTO STATS
  // ══════════════════════════════════════════════════════

  function findEquippedInSlot(slotId) {
    const character = getCharacter();
    if (!character.equipment) return null;
    return character.equipment.find(eq => eq.equipped_slot === slotId) || null;
  }

  function getCompatibleSlot(item) {
    const tags = (item.equip_tags || []).filter(t => t !== 'two_hand');
    const isTwoHand = (item.equip_tags || []).includes('two_hand');
    if (isTwoHand) return 'main_hand';
    return tags[0] || null;
  }

  function buildComparisonHtml(newItem, equippedItem) {
    if (!equippedItem) return '';

    const newBonus = newItem.stats_bonus || {};
    const oldBonus = equippedItem.stats_bonus || {};
    const allStats = new Set([...Object.keys(newBonus), ...Object.keys(oldBonus)]);

    let html = '<div class="tip-comparison"><div class="tip-comp-label">vs equipaggiato:</div>';
    let hasDiff = false;

    allStats.forEach(stat => {
      const newVal = newBonus[stat] || 0;
      const oldVal = oldBonus[stat] || 0;
      const diff = newVal - oldVal;
      if (diff !== 0) {
        hasDiff = true;
        const cls = diff > 0 ? 'stat-up' : 'stat-down';
        const sign = diff > 0 ? '+' : '';
        html += `<span class="tip-comp-stat ${cls}">${sign}${diff} ${stat.toUpperCase()}</span>`;
      }
    });

    // Confronto armor
    const newArmor = newItem.armor_value || 0;
    const oldArmor = equippedItem.armor_value || 0;
    if (newArmor !== oldArmor) {
      const diff = newArmor - oldArmor;
      hasDiff = true;
      const cls = diff > 0 ? 'stat-up' : 'stat-down';
      const sign = diff > 0 ? '+' : '';
      html += `<span class="tip-comp-stat ${cls}">${sign}${diff} Armatura</span>`;
    }

    // Confronto damage
    const newDmg = (newItem.damage_min || 0) + (newItem.damage_max || 0);
    const oldDmg = (equippedItem.damage_min || 0) + (equippedItem.damage_max || 0);
    if (newDmg !== oldDmg) {
      hasDiff = true;
      const diff = newDmg - oldDmg;
      const cls = diff > 0 ? 'stat-up' : 'stat-down';
      const sign = diff > 0 ? '+' : '';
      html += `<span class="tip-comp-stat ${cls}">${sign}${diff} Danno tot.</span>`;
    }

    html += '</div>';
    return hasDiff ? html : '';
  }

  function formatUseEffect(effect) {
    if (!effect) return '';
    switch (effect.type) {
      case 'heal': return `<div class="tip-use-effect">\u2764\uFE0F Guarisce ${effect.value} HP</div>`;
      case 'mana_restore': return `<div class="tip-use-effect">\u{1F535} Ripristina ${effect.value} Mana</div>`;
      case 'buff': return `<div class="tip-use-effect">\u2B06\uFE0F +${effect.value} ${(effect.stat || '').toUpperCase()} (${effect.duration || '1 scena'})</div>`;
      case 'damage': return `<div class="tip-use-effect">\u{1F525} ${effect.value} danni ${effect.damage_type || ''}</div>`;
      default: return '';
    }
  }

  function showItemTooltip(e) {
    const item = JSON.parse(e.currentTarget.dataset.item);
    const tags = (item.equip_tags || []).filter(t => t !== 'two_hand');
    const slotsText = tags.map(t => SLOT_LABELS[t] || t).join(', ');
    const isTwoHand = (item.equip_tags || []).includes('two_hand');
    const isEquipped = e.currentTarget.dataset.equipped === 'true';
    const isConsumable = item.category === 'consumable';

    let bonusHtml = '';
    if (item.stats_bonus && Object.keys(item.stats_bonus).length) {
      bonusHtml = Object.entries(item.stats_bonus)
        .map(([stat, val]) => `<div class="tip-stat bonus">+${val} ${stat.toUpperCase()}</div>`)
        .join('');
    }

    // Linea danno/armatura
    let combatLine = '';
    if (item.damage_min && item.damage_max) {
      combatLine += `<div class="tip-combat">\u2694\uFE0F ${item.damage_min}-${item.damage_max} danno</div>`;
    }
    if (item.armor_value) {
      combatLine += `<div class="tip-combat">\u{1F6E1}\uFE0F ${item.armor_value} armatura</div>`;
    }

    // Confronto stats (solo per item in inventario, non equipaggiati)
    let comparisonHtml = '';
    if (!isEquipped && !isConsumable) {
      const targetSlot = getCompatibleSlot(item);
      if (targetSlot) {
        const equippedItem = findEquippedInSlot(targetSlot);
        if (equippedItem) {
          comparisonHtml = buildComparisonHtml(item, equippedItem);
        }
      }
    }

    // Use effect per consumabili
    const useEffectHtml = formatUseEffect(item.use_effect);

    // Info prezzo/peso/ilvl
    let metaHtml = '';
    const metaParts = [];
    if (item.item_level) metaParts.push(`iLvl ${item.item_level}`);
    if (item.sell_price) metaParts.push(`\u{1FA99} ${item.sell_price}`);
    if (item.weight) metaParts.push(`${item.weight} kg`);
    if (metaParts.length) {
      metaHtml = `<div class="tip-meta">${metaParts.join(' \u00B7 ')}</div>`;
    }

    tooltipEl.innerHTML = `
      <div class="tip-header">
        <span class="tip-name">${item.name || item.item_name}</span>
        <span class="tip-rarity ${item.rarity || 'common'}">${item.rarity || 'common'}</span>
      </div>
      <div class="tip-item-type">${item.type || 'Oggetto'}${isTwoHand ? ' (Due Mani)' : ''}</div>
      ${item.description ? `<p class="tip-desc">${item.description}</p>` : ''}
      ${combatLine}
      ${bonusHtml}
      ${useEffectHtml}
      ${comparisonHtml}
      <div class="tip-slots">Slot: ${isConsumable ? 'Consumabile' : (isTwoHand ? 'Due Mani' : slotsText)}</div>
      ${metaHtml}
    `;
    tooltipEl.classList.add('visible');
    moveTooltip(e);
  }

  // ══════════════════════════════════════════════════════
  // CONTEXT MENU
  // ══════════════════════════════════════════════════════

  function createContextMenu() {
    contextMenuEl = document.createElement('div');
    contextMenuEl.className = 'item-context-menu';
    contextMenuEl.style.display = 'none';
    document.body.appendChild(contextMenuEl);

    // Chiudi al click fuori
    document.addEventListener('click', (e) => {
      if (!contextMenuEl.contains(e.target)) {
        closeContextMenu();
      }
    });
    document.addEventListener('contextmenu', (e) => {
      if (!e.target.closest('.item-card') && !contextMenuEl.contains(e.target)) {
        closeContextMenu();
      }
    });
  }

  function closeContextMenu() {
    if (contextMenuEl) contextMenuEl.style.display = 'none';
  }

  function showContextMenu(e, item, equipped) {
    e.preventDefault();
    hideTooltip();

    const character = getCharacter();
    const isConsumable = item.category === 'consumable';
    let options = [];

    if (equipped) {
      // Item equipaggiato
      options.push({ label: 'Rimuovi', icon: '\u274C', action: () => handleUnequip(item) });
    } else if (isConsumable) {
      // Consumabile in inventario
      options.push({ label: 'Usa', icon: '\u2728', action: () => handleUseItem(item) });
      options.push({ label: 'Scarta', icon: '\u{1F5D1}\uFE0F', action: () => handleDiscard(item) });
    } else {
      // Equipment in inventario
      const tags = (item.equip_tags || []).filter(t => t !== 'two_hand');
      const isTwoHand = (item.equip_tags || []).includes('two_hand');

      if (isTwoHand) {
        options.push({ label: 'Equipaggia (Due Mani)', icon: '\u2694\uFE0F', action: () => handleEquip(item, 'main_hand') });
      } else {
        tags.forEach(tag => {
          const label = SLOT_LABELS[tag] || tag;
          options.push({ label: `Equipaggia (${label})`, icon: '\u2694\uFE0F', action: () => handleEquip(item, tag) });
        });
      }
      options.push({ label: 'Scarta', icon: '\u{1F5D1}\uFE0F', action: () => handleDiscard(item) });
    }

    // Render menu
    contextMenuEl.innerHTML = options.map((opt, i) =>
      `<div class="ctx-option" data-idx="${i}">${opt.icon} ${opt.label}</div>`
    ).join('');

    // Posizione
    const x = Math.min(e.clientX, window.innerWidth - 200);
    const y = Math.min(e.clientY, window.innerHeight - (options.length * 36 + 16));
    contextMenuEl.style.left = `${x}px`;
    contextMenuEl.style.top = `${y}px`;
    contextMenuEl.style.display = 'block';

    // Bind actions
    contextMenuEl.querySelectorAll('.ctx-option').forEach((el) => {
      const idx = parseInt(el.dataset.idx);
      el.addEventListener('click', () => {
        closeContextMenu();
        options[idx].action();
      });
    });
  }

  async function handleEquip(item, slot) {
    const character = getCharacter();
    try {
      const result = await apiEquip(character.id, item.item_name, slot);
      if (result.success) await refreshCharacter();
    } catch (err) {
      console.error('Equip error:', err);
    }
  }

  async function handleUnequip(item) {
    const character = getCharacter();
    try {
      const result = await apiUnequip(character.id, item.equipped_slot);
      if (result.success) await refreshCharacter();
    } catch (err) {
      console.error('Unequip error:', err);
    }
  }

  async function handleUseItem(item) {
    const character = getCharacter();
    try {
      const result = await apiUseItem(character.id, item.item_name);
      if (result.success) await refreshCharacter();
    } catch (err) {
      console.error('UseItem error:', err);
    }
  }

  async function handleDiscard(item) {
    const character = getCharacter();
    try {
      await apiDiscard(character.id, item.item_name, 1);
      await refreshCharacter();
    } catch (err) {
      console.error('Discard error:', err);
    }
  }

  // ══════════════════════════════════════════════════════
  // EVENT SETUP
  // ══════════════════════════════════════════════════════

  function setupItemCardEvents(card, item, equipped) {
    const isConsumable = item.category === 'consumable';

    // Drag start (solo per equipment, non consumabili)
    if (!isConsumable) {
      card.addEventListener('dragstart', (e) => {
        draggedItem = { item, equipped, element: card };
        card.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';

        const tags = item.equip_tags || [];
        const isTwoHand = tags.includes('two_hand');
        const currentSlot = equipped ? item.equipped_slot : null;

        document.querySelectorAll('.equip-slot').forEach(slot => {
          const slotId = slot.dataset.slot;
          if (slot.classList.contains('locked')) return;

          if (isTwoHand) {
            if (slotId === 'main_hand' && slotId !== currentSlot) {
              slot.classList.add('drop-valid');
            }
          } else {
            if (tags.includes(slotId) && slotId !== currentSlot) {
              slot.classList.add('drop-valid');
            }
          }
        });

        if (equipped) {
          document.getElementById('inventory-drop-zone').classList.add('drop-valid');
        }
      });

      card.addEventListener('dragend', () => {
        card.classList.remove('dragging');
        document.querySelectorAll('.drop-valid, .drop-over').forEach(el => {
          el.classList.remove('drop-valid', 'drop-over');
        });
        draggedItem = null;
      });
    }

    // Context menu (click destro)
    card.addEventListener('contextmenu', (e) => {
      showContextMenu(e, item, equipped);
    });

    // Long press per mobile
    card.addEventListener('touchstart', (e) => {
      longPressTimer = setTimeout(() => {
        const touch = e.touches[0];
        showContextMenu({
          preventDefault: () => {},
          clientX: touch.clientX,
          clientY: touch.clientY
        }, item, equipped);
      }, 500);
    }, { passive: true });

    card.addEventListener('touchend', () => {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    });

    card.addEventListener('touchmove', () => {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    });

    // Tooltip
    card.addEventListener('mouseenter', showItemTooltip);
    card.addEventListener('mousemove', moveTooltip);
    card.addEventListener('mouseleave', hideTooltip);
  }

  // ══════════════════════════════════════════════════════
  // DRAG & DROP
  // ══════════════════════════════════════════════════════

  document.querySelectorAll('.slot-drop-area').forEach(dropArea => {
    const slotEl = dropArea.parentElement;
    const slotId = slotEl.dataset.slot;

    dropArea.addEventListener('dragover', (e) => {
      if (!draggedItem) return;
      if (slotEl.classList.contains('locked')) return;

      const tags = draggedItem.item.equip_tags || [];
      const isTwoHand = tags.includes('two_hand');
      const currentSlot = draggedItem.equipped ? draggedItem.item.equipped_slot : null;

      let valid = false;
      if (isTwoHand) {
        valid = slotId === 'main_hand' && slotId !== currentSlot;
      } else {
        valid = tags.includes(slotId) && slotId !== currentSlot;
      }

      if (valid) {
        e.preventDefault();
        slotEl.classList.add('drop-over');
      }
    });

    dropArea.addEventListener('dragleave', () => {
      slotEl.classList.remove('drop-over');
    });

    dropArea.addEventListener('drop', async (e) => {
      e.preventDefault();
      slotEl.classList.remove('drop-over');
      if (!draggedItem) return;
      if (slotEl.classList.contains('locked')) return;

      const { item, equipped } = draggedItem;
      const character = getCharacter();
      const isTwoHand = (item.equip_tags || []).includes('two_hand');
      const targetSlot = isTwoHand ? 'main_hand' : slotId;

      try {
        let result;
        if (equipped) {
          result = await apiMove(character.id, item.equipped_slot, targetSlot);
        } else {
          result = await apiEquip(character.id, item.item_name, targetSlot);
        }
        if (result.success) await refreshCharacter();
      } catch (err) {
        console.error('Equip/Move error:', err);
      }
    });
  });

  // Drop zone inventario (unequip)
  const invDropZone = document.getElementById('inventory-drop-zone');

  invDropZone.addEventListener('dragover', (e) => {
    if (draggedItem?.equipped) {
      e.preventDefault();
      invDropZone.classList.add('drop-over');
    }
  });

  invDropZone.addEventListener('dragleave', () => {
    invDropZone.classList.remove('drop-over');
  });

  invDropZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    invDropZone.classList.remove('drop-over');
    if (!draggedItem?.equipped) return;
    const character = getCharacter();

    try {
      const result = await apiUnequip(character.id, draggedItem.item.equipped_slot);
      if (result.success) await refreshCharacter();
    } catch (err) {
      console.error('Unequip error:', err);
    }
  });

  // ── Public API ──

  function render() {
    renderEquipment();
    renderInventory();
  }

  return { render, refresh: render };
}
