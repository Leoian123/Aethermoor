// sheetRenderer.js - Character sheet header, stats, invest points, and skills rendering
// Extracted from sheet.astro

/**
 * Initialize the sheet renderer module.
 * @param {Object} config
 * @param {Function} config.getCharacter - Returns current character data
 * @param {Function} config.investStats - API call: investStats(characterId, allocations)
 * @param {Function} config.refreshCharacter - Refreshes character data and re-renders
 * @param {HTMLElement} config.tooltipEl - Shared tooltip element
 * @param {Function} config.moveTooltip - Shared moveTooltip(event) handler
 * @param {Function} config.hideTooltip - Shared hideTooltip() handler
 * @returns {{ renderAll: Function, updateCharacter: Function }}
 */
export function initSheetRenderer(config) {
  const { getCharacter, investStats, refreshCharacter, tooltipEl, moveTooltip, hideTooltip } = config;

  // ── Invest state ──
  let pendingInvest = { str: 0, dex: 0, vit: 0, int: 0 };
  let investAvailable = 0;

  // ══════════════════════════════════════════════════════
  // HEADER
  // ══════════════════════════════════════════════════════

  function renderHeader() {
    const character = getCharacter();
    document.getElementById('char-name').textContent = character.name;
    document.getElementById('char-class').textContent = character.class?.name || '—';
    document.getElementById('char-level').textContent = character.level;

    document.getElementById('hp-current').textContent = character.hp_current;
    document.getElementById('hp-max').textContent = character.hp_max;
    document.getElementById('hp-bar').style.width = `${(character.hp_current / character.hp_max) * 100}%`;

    document.getElementById('mana-current').textContent = character.mana_current;
    document.getElementById('mana-max').textContent = character.mana_max;
    document.getElementById('mana-bar').style.width = `${(character.mana_current / character.mana_max) * 100}%`;

    // XP bar
    const xp = character.xp || 0;
    const xpNext = character.xp_next || (character.level || 1) * 100;
    document.getElementById('xp-current').textContent = xp;
    document.getElementById('xp-next').textContent = xpNext;
    document.getElementById('xp-bar').style.width = `${(xp / xpNext) * 100}%`;

    // Corone
    const coroneEl = document.getElementById('corone-display');
    if (coroneEl) coroneEl.textContent = character.corone || 0;
  }

  // ══════════════════════════════════════════════════════
  // STATS
  // ══════════════════════════════════════════════════════

  function renderStats() {
    const character = getCharacter();
    const totals = character.total_stats || {};
    const derived = character.derived || {};

    ['str', 'dex', 'vit', 'int'].forEach(stat => {
      const base = character[stat] || 10;
      const total = totals[stat] || base;
      const bonus = total - base;

      document.getElementById(`base-${stat}`).textContent = base;
      document.getElementById(`total-${stat}`).textContent = total;

      const modEl = document.getElementById(`mod-${stat}`);
      if (bonus !== 0) {
        modEl.textContent = bonus > 0 ? `+${bonus}` : `${bonus}`;
        modEl.className = `stat-mod ${bonus > 0 ? 'buff' : 'debuff'}`;
      } else {
        modEl.textContent = '';
      }
    });

    // 12 derived stats (HP e Mana sono nell'header)
    document.getElementById('derived-phys').textContent = `x${derived.phys_dmg_mult ?? '1.00'}`;
    document.getElementById('derived-magic').textContent = `x${derived.magic_dmg_mult ?? '1.00'}`;
    document.getElementById('derived-prec').textContent = `${derived.precision ?? 60}%`;
    document.getElementById('derived-eva').textContent = `${derived.evasion ?? 0}%`;
    document.getElementById('derived-apt').textContent = `${derived.attacks_per_turn ?? 1.0}`;
    document.getElementById('derived-speed').textContent = `${derived.move_speed ?? 100}%`;
    document.getElementById('derived-carry').textContent = `${derived.carry_max ?? 50}kg`;
    document.getElementById('derived-regen').textContent = `${derived.hp_regen ?? 0}/min`;
    document.getElementById('derived-poison').textContent = `${derived.poison_resist ?? 0}%`;
    document.getElementById('derived-element').textContent = `${derived.element_resist ?? 0}%`;
    document.getElementById('derived-xp').textContent = `${derived.xp_bonus ?? 0}%`;
    document.getElementById('derived-craft').textContent = `${derived.craft_bonus ?? 0}%`;

    // Investimento punti
    renderInvestSection();
  }

  function renderInvestSection() {
    const character = getCharacter();
    investAvailable = character.invest_points_available || 0;
    pendingInvest = { str: 0, dex: 0, vit: 0, int: 0 };

    const section = document.getElementById('invest-section');
    if (investAvailable <= 0) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    updateInvestUI();
  }

  function updateInvestUI() {
    const spent = Object.values(pendingInvest).reduce((a, b) => a + b, 0);
    const remaining = investAvailable - spent;

    document.getElementById('invest-available').textContent = remaining;

    ['str', 'dex', 'vit', 'int'].forEach(stat => {
      document.getElementById(`invest-${stat}`).textContent = pendingInvest[stat] > 0 ? `+${pendingInvest[stat]}` : '0';
    });

    // Disabilita +1 se non ci sono punti
    document.querySelectorAll('.invest-btn').forEach(btn => {
      btn.disabled = remaining <= 0;
    });

    // Abilita conferma solo se almeno un punto allocato
    document.getElementById('invest-confirm').disabled = spent === 0;
  }

  // ── Invest event bindings ──

  document.querySelectorAll('.invest-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const stat = btn.dataset.stat;
      const spent = Object.values(pendingInvest).reduce((a, b) => a + b, 0);
      if (spent < investAvailable) {
        pendingInvest[stat]++;
        updateInvestUI();
      }
    });
  });

  document.getElementById('invest-reset').addEventListener('click', () => {
    pendingInvest = { str: 0, dex: 0, vit: 0, int: 0 };
    updateInvestUI();
  });

  document.getElementById('invest-confirm').addEventListener('click', async () => {
    const character = getCharacter();
    const spent = Object.values(pendingInvest).reduce((a, b) => a + b, 0);
    if (spent === 0) return;

    const confirmBtn = document.getElementById('invest-confirm');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Applicando...';

    try {
      await investStats(character.id, pendingInvest);
      await refreshCharacter();
    } catch (err) {
      console.error('Invest error:', err);
      confirmBtn.textContent = 'Errore!';
      setTimeout(() => { confirmBtn.textContent = 'Conferma'; confirmBtn.disabled = false; }, 2000);
    }
  });

  // ══════════════════════════════════════════════════════
  // SKILLS
  // ══════════════════════════════════════════════════════

  function renderSkills() {
    const character = getCharacter();
    if (!character.skills?.length) {
      document.getElementById('skills-empty').style.display = 'block';
      return;
    }
    document.getElementById('skills-empty').style.display = 'none';

    const spheres = character.skills.filter(s => s.category === 'sphere');
    const martial = character.skills.filter(s => s.category === 'martial');
    const knowledge = character.skills.filter(s => s.category === 'knowledge');

    document.getElementById('skills-spheres').innerHTML = spheres.map(createSkillCard).join('');
    document.getElementById('skills-martial').innerHTML = martial.map(createSkillCard).join('');
    document.getElementById('skills-knowledge').innerHTML = knowledge.map(createSkillCard).join('');

    document.querySelectorAll('.skill-card').forEach(card => {
      card.addEventListener('mouseenter', showSkillTooltip);
      card.addEventListener('mousemove', moveTooltip);
      card.addEventListener('mouseleave', hideTooltip);
    });
  }

  function createSkillCard(skill) {
    const color = getSkillColor(skill.tag);
    const icon = getSkillIcon(skill);
    return `
      <div class="skill-card ${skill.type}" style="--skill-color: ${color}" data-skill='${JSON.stringify(skill).replace(/'/g, "&#39;")}'>
        <div class="skill-icon-wrap">
          <span class="skill-icon">${icon}</span>
          <span class="skill-mastery">${skill.mastery}</span>
        </div>
        <div class="skill-info">
          <span class="skill-name">${skill.name}</span>
          <span class="skill-type-label">${skill.type === 'active' ? 'Attiva' : 'Passiva'}</span>
        </div>
      </div>
    `;
  }

  function getSkillIcon(skill) {
    const icons = { 'IGNIS': '\u{1F525}', 'AQUA': '\u{1F4A7}', 'TERRA': '\u{1FAA8}', 'VENTUS': '\u{1F4A8}', 'MENS': '\u{1F9FF}', 'ANIMA': '\u{1F47B}', 'VIS': '\u26A1', 'VITA': '\u{1F49A}', 'SPATIUM': '\u{1F300}', 'TEMPUS': '\u231B', 'SWORD': '\u2694\uFE0F', 'DAGGER': '\u{1F5E1}\uFE0F', 'SHIELD': '\u{1F6E1}\uFE0F' };
    for (const [key, icon] of Object.entries(icons)) {
      if (skill.tag.includes(key)) return icon;
    }
    return '\u2728';
  }

  function getSkillColor(tag) {
    const colors = { 'IGNIS': '#ff6b35', 'AQUA': '#4ecdc4', 'TERRA': '#8b7355', 'VENTUS': '#a8d5e5', 'MENS': '#9b59b6', 'ANIMA': '#1abc9c', 'VIS': '#f1c40f', 'VITA': '#2ecc71', 'SPATIUM': '#3498db', 'TEMPUS': '#e74c3c', 'SWORD': '#e67e22', 'DAGGER': '#c0392b' };
    for (const [key, color] of Object.entries(colors)) {
      if (tag.includes(key)) return color;
    }
    return '#c9a959';
  }

  function showSkillTooltip(e) {
    const skill = JSON.parse(e.currentTarget.dataset.skill);
    tooltipEl.innerHTML = `
      <div class="tip-header">
        <span class="tip-name">${skill.name}</span>
        <span class="tip-type ${skill.type}">${skill.type === 'active' ? 'Attiva' : 'Passiva'}</span>
      </div>
      <p class="tip-desc">${skill.description}</p>
      <div class="tip-mastery">Maestria: ${skill.mastery}/10</div>
      ${skill.base_cost > 0 ? `<div class="tip-stat">\u{1F4A7} Costo: ${skill.base_cost} mana</div>` : ''}
      ${skill.cooldown > 0 ? `<div class="tip-stat">\u23F1\uFE0F Cooldown: ${skill.cooldown} turni</div>` : ''}
      <div class="tip-footer">${skill.tag}</div>
    `;
    tooltipEl.classList.add('visible');
    moveTooltip(e);
  }

  // ── Public API ──

  function renderAll() {
    renderHeader();
    renderStats();
    renderSkills();
  }

  return { renderAll, updateCharacter: renderAll };
}
