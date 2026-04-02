/**
 * WorldMapController — Multi-depth Zoomable Hex World Map
 * Hub di navigazione: Region → Zone → Location → Sublocation → Chat
 */

import {
  HEX_DIRECTIONS, TERRAIN_COLORS,
  hexToPixel, hexPointsString, hexCorners,
  findNearestFreeHex, calculateHexPositions
} from './hexUtils.js';
import { getWorldGraph, getLocationPreview } from './api.js';

const HEX_SIZE_WORLD = 40;
const DEPTH_LABELS = ['Regioni', 'Zone', 'Territori', 'Luoghi', 'Stanze'];

export default class WorldMapController {
  constructor(config) {
    // Config
    this.characterId = config.characterId;
    this.slot = config.slot;
    this.onEnterChat = config.onEnterChat; // callback(locationId)

    // DOM
    this.container = document.getElementById(config.containerId);
    this.svgEl = document.getElementById(config.svgId);
    this.breadcrumbEl = document.getElementById(config.breadcrumbId);
    this.depthLabel = document.getElementById(config.depthLabelId);
    this.tooltip = document.getElementById('worldmap-tooltip');
    this.loadingEl = document.getElementById('worldmap-loading');

    // SVG groups
    this.edgesGroup = document.getElementById('worldmap-edges');
    this.nodesGroup = document.getElementById('worldmap-nodes');
    this.labelsGroup = document.getElementById('worldmap-labels');

    // Navigation state
    this.depth = 0;
    this.parentId = null;
    this.breadcrumb = [];
    this.currentPath = {};
    this.nodes = [];
    this.edges = [];

    // Hex positions
    this.hexPositions = {};

    // Pan & Zoom state
    this.viewBox = { x: -300, y: -300, w: 600, h: 600 };
    this.isPanning = false;
    this.panStart = { x: 0, y: 0 };
    this.panDistance = 0;
    this.minZoom = 0.3;
    this.maxZoom = 4;

    // Animation
    this.isLoading = false;

    this.init();
  }

  init() {
    this.initPanZoom();
    this.initKeyboard();
    this.initPreviewPanel();
    this.loadDepth(0, null);
  }

  // ══════════════════════════════════════════════════════
  // DATA LOADING
  // ══════════════════════════════════════════════════════

  async loadDepth(depth, parentId) {
    if (this.isLoading) return;
    this.isLoading = true;
    this.showLoading(true);

    try {
      const data = await getWorldGraph(this.characterId, depth, parentId);
      this.depth = depth;
      this.parentId = parentId;
      this.nodes = data.nodes || [];
      this.edges = data.edges || [];
      this.breadcrumb = data.breadcrumb || [];
      this.currentPath = data.current_path || {};

      // Se un solo nodo e ha figli, auto-zoom
      if (this.nodes.length === 1 && this.nodes[0].has_children && depth < 3) {
        this.isLoading = false;
        this.showLoading(false);
        await this.loadDepth(depth + 1, this.nodes[0].id);
        return;
      }

      this.renderBreadcrumb();
      this.renderMap();
      this.updateDepthLabel();
    } catch (error) {
      console.error('WorldMap: errore caricamento', error);
    } finally {
      this.isLoading = false;
      this.showLoading(false);
    }
  }

  // ══════════════════════════════════════════════════════
  // BREADCRUMB
  // ══════════════════════════════════════════════════════

  renderBreadcrumb() {
    if (!this.breadcrumbEl) return;
    this.breadcrumbEl.innerHTML = '';

    this.breadcrumb.forEach((crumb, index) => {
      if (index > 0) {
        const sep = document.createElement('span');
        sep.className = 'breadcrumb-sep';
        sep.textContent = '›';
        this.breadcrumbEl.appendChild(sep);
      }

      const item = document.createElement('button');
      item.className = 'breadcrumb-item';
      item.textContent = crumb.name;

      // L'ultimo elemento e' il livello corrente — non cliccabile
      const isLast = index === this.breadcrumb.length - 1;
      if (isLast) {
        item.classList.add('breadcrumb-current');
        item.disabled = true;
      } else {
        item.addEventListener('click', () => this.handleBreadcrumbClick(crumb, index));
      }

      this.breadcrumbEl.appendChild(item);
    });
  }

  handleBreadcrumbClick(crumb, index) {
    if (crumb.type === 'world') {
      this.loadDepth(0, null);
    } else {
      // Il breadcrumb a index N ci porta al depth N+1 (mostra i figli di quel nodo)
      const targetDepth = index; // breadcrumb[0]=world, [1]=region, [2]=zone...
      const parentForDepth = index > 0 ? this.breadcrumb[index].id : null;

      // Calcola il depth corretto
      const depthMap = { world: 0, region: 1, zone: 2, location: 3, sublocation: 4 };
      const depth = depthMap[crumb.type] || index;
      this.loadDepth(depth, crumb.id);
    }
  }

  updateDepthLabel() {
    if (!this.depthLabel) return;
    this.depthLabel.textContent = DEPTH_LABELS[this.depth] || 'Stanze';

    // Show/hide depth-3 legend items (reachable, locked)
    const legendItems = document.querySelectorAll('.wm-legend-depth3');
    legendItems.forEach(item => {
      item.style.display = this.depth >= 3 ? '' : 'none';
    });
  }

  // ══════════════════════════════════════════════════════
  // HEX LAYOUT
  // ══════════════════════════════════════════════════════

  calculatePositions() {
    const nodes = this.nodes;
    const edges = this.edges;

    // Se i nodi hanno coordinate hex dal seed, usale direttamente
    const hasHexCoords = nodes.some(n => n.hex && Array.isArray(n.hex));

    if (hasHexCoords && edges.length === 0) {
      // Usa coordinate dal seed (depth 0, 1, 2)
      const positions = {};
      nodes.forEach(n => {
        if (n.hex && Array.isArray(n.hex)) {
          positions[n.id] = { q: n.hex[0], r: n.hex[1] };
        }
      });

      // Nodi senza coordinate: piazzali vicino
      const occupied = new Set(Object.values(positions).map(p => `${p.q},${p.r}`));
      nodes.forEach(n => {
        if (!positions[n.id]) {
          const pos = findNearestFreeHex(0, 0, occupied);
          positions[n.id] = pos;
          occupied.add(`${pos.q},${pos.r}`);
        }
      });

      return positions;
    }

    // Fallback: usa BFS layout (depth 3+, hanno edges)
    const currentNode = nodes.find(n => n.is_current);
    const currentId = currentNode?.id || nodes[0]?.id;
    return calculateHexPositions(nodes, edges, currentId);
  }

  // ══════════════════════════════════════════════════════
  // RENDERING
  // ══════════════════════════════════════════════════════

  renderMap() {
    if (!this.edgesGroup || !this.nodesGroup || !this.labelsGroup) return;

    // Fade out
    this.container?.classList.add('worldmap-transitioning');

    // Clear
    this.edgesGroup.innerHTML = '';
    this.nodesGroup.innerHTML = '';
    this.labelsGroup.innerHTML = '';

    if (this.nodes.length === 0) {
      this.container?.classList.remove('worldmap-transitioning');
      return;
    }

    // Calculate positions
    this.hexPositions = this.calculatePositions();

    // Ghost hexes (1 ring)
    this.renderGhostHexes();

    // Edges
    this.edges.forEach(edge => {
      const fromHex = this.hexPositions[edge.from];
      const toHex = this.hexPositions[edge.to];
      if (fromHex && toHex) {
        const fromPx = hexToPixel(fromHex.q, fromHex.r, HEX_SIZE_WORLD);
        const toPx = hexToPixel(toHex.q, toHex.r, HEX_SIZE_WORLD);
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', fromPx.x.toFixed(1));
        line.setAttribute('y1', fromPx.y.toFixed(1));
        line.setAttribute('x2', toPx.x.toFixed(1));
        line.setAttribute('y2', toPx.y.toFixed(1));
        line.classList.add('worldmap-edge');
        if (edge.type === 'enter') line.classList.add('edge-enter');
        this.edgesGroup.appendChild(line);
      }
    });

    // Hex nodes
    this.nodes.forEach(node => {
      const hex = this.hexPositions[node.id];
      if (!hex) return;
      const px = hexToPixel(hex.q, hex.r, HEX_SIZE_WORLD);
      this.renderHexNode(px.x, px.y, node, hex.q, hex.r);
    });

    // Labels
    this.nodes.forEach(node => {
      const hex = this.hexPositions[node.id];
      if (!hex) return;
      const px = hexToPixel(hex.q, hex.r, HEX_SIZE_WORLD);
      this.renderLabel(px.x, px.y + HEX_SIZE_WORLD + 12, node);
    });

    // Auto-fit
    this.autoFitViewBox();

    // Mark reachable hexes at depth 3+ (where edges exist)
    if (this.depth >= 3 && this.edges.length > 0) {
      this.buildAdjacencyMap();
      this.markReachableHexes();
    }

    // Fade in
    requestAnimationFrame(() => {
      this.container?.classList.remove('worldmap-transitioning');
    });
  }

  buildAdjacencyMap() {
    this.adjacencyMap = {};
    this.edges.forEach(edge => {
      if (!this.adjacencyMap[edge.from]) this.adjacencyMap[edge.from] = new Set();
      if (!this.adjacencyMap[edge.to]) this.adjacencyMap[edge.to] = new Set();
      this.adjacencyMap[edge.from].add(edge.to);
      this.adjacencyMap[edge.to].add(edge.from);
    });
  }

  markReachableHexes() {
    const currentNode = this.nodes.find(n => n.is_current);
    if (!currentNode) return;

    const reachable = this.adjacencyMap[currentNode.id] || new Set();
    this.nodesGroup.querySelectorAll('.wm-hex-node').forEach(hexGroup => {
      const nodeId = hexGroup.getAttribute('data-node-id');
      if (reachable.has(nodeId) && nodeId !== currentNode.id) {
        hexGroup.classList.add('wm-hex-reachable');
      }
    });
  }

  renderHexNode(cx, cy, nodeData, hexQ, hexR) {
    const hexGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    hexGroup.classList.add('wm-hex-node');
    hexGroup.setAttribute('data-node-id', nodeData.id);

    const isCurrent = nodeData.is_current;

    // Pulse ring per posizione corrente
    if (isCurrent) {
      const ring = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      ring.setAttribute('points', hexPointsString(cx, cy, HEX_SIZE_WORLD + 5));
      ring.classList.add('wm-pulse-ring');
      this.nodesGroup.appendChild(ring);
    }

    // Hex polygon
    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', hexPointsString(cx, cy, HEX_SIZE_WORLD));

    // Colori basati su tipo
    let colors;
    if (isCurrent) {
      colors = TERRAIN_COLORS.current;
      polygon.classList.add('wm-hex-current');
    } else if (nodeData.locked) {
      colors = TERRAIN_COLORS.locked;
      polygon.classList.add('wm-hex-locked');
    } else if (nodeData.visited === false && this.depth >= 2) {
      colors = TERRAIN_COLORS.unvisited;
      polygon.classList.add('wm-hex-unvisited');
    } else {
      const terrainType = nodeData.type || 'default';
      colors = TERRAIN_COLORS[terrainType] || TERRAIN_COLORS.default;
      polygon.classList.add('wm-hex-visited');
    }

    polygon.setAttribute('fill', colors.fill);
    polygon.setAttribute('stroke', colors.stroke);
    polygon.setAttribute('stroke-width', colors.strokeWidth);
    polygon.setAttribute('stroke-linejoin', 'round');
    hexGroup.appendChild(polygon);

    // Inner content
    if (isCurrent) {
      // Player token
      const token = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      token.setAttribute('cx', cx.toFixed(1));
      token.setAttribute('cy', cy.toFixed(1));
      token.setAttribute('r', (HEX_SIZE_WORLD * 0.25).toFixed(1));
      token.classList.add('wm-player-token');
      hexGroup.appendChild(token);
    } else if (nodeData.locked) {
      // Locked icon
      const lockIcon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      lockIcon.setAttribute('x', cx.toFixed(1));
      lockIcon.setAttribute('y', (cy + HEX_SIZE_WORLD * 0.2).toFixed(1));
      lockIcon.setAttribute('text-anchor', 'middle');
      lockIcon.classList.add('wm-hex-lock-icon');
      lockIcon.textContent = '\u{1F512}';
      hexGroup.appendChild(lockIcon);
    } else if (nodeData.visited === false && this.depth >= 2) {
      // Fog + ?
      const fog = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      fog.setAttribute('points', hexPointsString(cx, cy, HEX_SIZE_WORLD));
      fog.classList.add('wm-hex-fog');
      hexGroup.appendChild(fog);

      const qMark = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      qMark.setAttribute('x', cx.toFixed(1));
      qMark.setAttribute('y', (cy + HEX_SIZE_WORLD * 0.2).toFixed(1));
      qMark.setAttribute('text-anchor', 'middle');
      qMark.classList.add('wm-hex-question');
      qMark.textContent = '?';
      hexGroup.appendChild(qMark);
    }

    // Icona zoom-in per nodi con figli (depth < 3 or has_children)
    if (nodeData.has_children && !isCurrent) {
      const icon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      icon.setAttribute('x', (cx + HEX_SIZE_WORLD * 0.35).toFixed(1));
      icon.setAttribute('y', (cy - HEX_SIZE_WORLD * 0.25).toFixed(1));
      icon.setAttribute('text-anchor', 'middle');
      icon.classList.add('wm-zoom-icon');
      icon.textContent = nodeData.is_leaf === false ? '⊕' : '⊙';
      hexGroup.appendChild(icon);
    }

    // Icona chat per nodi foglia
    if (nodeData.is_leaf && this.depth >= 3) {
      const chatIcon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      chatIcon.setAttribute('x', (cx + HEX_SIZE_WORLD * 0.35).toFixed(1));
      chatIcon.setAttribute('y', (cy - HEX_SIZE_WORLD * 0.25).toFixed(1));
      chatIcon.setAttribute('text-anchor', 'middle');
      chatIcon.classList.add('wm-chat-icon');
      chatIcon.textContent = '💬';
      hexGroup.appendChild(chatIcon);
    }

    // Child count badge (depth < 3)
    if (nodeData.child_count > 0 && this.depth < 3) {
      const badge = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      badge.setAttribute('x', cx.toFixed(1));
      badge.setAttribute('y', (cy + HEX_SIZE_WORLD * 0.15).toFixed(1));
      badge.setAttribute('text-anchor', 'middle');
      badge.classList.add('wm-child-count');
      badge.textContent = `${nodeData.child_count}`;
      hexGroup.appendChild(badge);
    }

    // Tooltip events
    polygon.addEventListener('mouseenter', (e) => {
      if (!this.isPanning) this.showTooltip(e, nodeData);
    });
    polygon.addEventListener('mouseleave', () => this.hideTooltip());
    polygon.addEventListener('mousemove', (e) => {
      if (!this.isPanning) this.moveTooltip(e);
    });

    // Click handler
    hexGroup.addEventListener('click', (e) => {
      if (this.panDistance > 5) return; // was a pan
      e.stopPropagation();
      this.handleNodeClick(nodeData);
    });

    // Hover cursor — differenziato per stato
    const isUnclickable = this.depth >= 3 && !nodeData.visited && !isCurrent &&
                          (nodeData.is_leaf || (!nodeData.has_children && this.depth >= 2));
    if (isUnclickable) {
      hexGroup.classList.add('wm-hex-unclickable');
      hexGroup.style.cursor = 'default';
    } else if (nodeData.locked) {
      hexGroup.style.cursor = 'not-allowed';
    } else {
      hexGroup.style.cursor = 'pointer';
    }

    this.nodesGroup.appendChild(hexGroup);
  }

  renderGhostHexes() {
    const positions = this.hexPositions;
    const dataKeys = new Set(Object.values(positions).map(p => `${p.q},${p.r}`));
    const ghostKeys = new Set();

    Object.values(positions).forEach(pos => {
      HEX_DIRECTIONS.forEach(dir => {
        const key = `${pos.q + dir.q},${pos.r + dir.r}`;
        if (!dataKeys.has(key) && !ghostKeys.has(key)) {
          ghostKeys.add(key);
        }
      });
    });

    ghostKeys.forEach(key => {
      const [gq, gr] = key.split(',').map(Number);
      const { x, y } = hexToPixel(gq, gr, HEX_SIZE_WORLD);
      const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      polygon.setAttribute('points', hexPointsString(x, y, HEX_SIZE_WORLD));
      polygon.classList.add('wm-hex-ghost');
      this.edgesGroup.appendChild(polygon);
    });
  }

  renderLabel(x, y, nodeData) {
    const isVisible = nodeData.visited !== false || this.depth < 2;
    const text = isVisible ? nodeData.name : '???';
    const maxChars = 20;
    const displayText = text.length > maxChars ? text.substring(0, maxChars - 1) + '\u2026' : text;

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x.toFixed(1));
    label.setAttribute('y', y.toFixed(1));
    label.textContent = displayText;
    label.classList.add('wm-label');

    if (nodeData.is_current) label.classList.add('wm-label-current');
    if (!isVisible) label.classList.add('wm-label-unknown');

    this.labelsGroup.appendChild(label);
  }

  // ══════════════════════════════════════════════════════
  // NODE CLICK — Zoom In / Enter Chat
  // ══════════════════════════════════════════════════════

  handleNodeClick(nodeData) {
    if (this.isLoading) return;

    // Nodo foglia a depth >= 3 → mostra preview SOLO se visitato o corrente
    if (nodeData.is_leaf && this.depth >= 3) {
      if (!nodeData.visited && !nodeData.is_current) {
        // Location inesplorata — non accessibile dalla mappa
        return;
      }
      this.showLocationPreview(nodeData);
      return;
    }

    // Nodo con figli → zoom in
    if (nodeData.has_children) {
      this.loadDepth(this.depth + 1, nodeData.id);
      return;
    }

    // Nodo senza figli a depth >= 2 (location senza sublocation)
    if (this.depth >= 2 && !nodeData.has_children) {
      if (!nodeData.visited && !nodeData.is_current) {
        return;
      }
      this.showLocationPreview(nodeData);
      return;
    }
  }

  // ══════════════════════════════════════════════════════
  // NAVIGATE TO PLAYER POSITION
  // ══════════════════════════════════════════════════════

  async navigateToPlayer() {
    // Zoom diretto alla posizione del giocatore
    const cp = this.currentPath;
    if (cp.sublocation_id) {
      // Determina il parent_id (location) dalla sublocation
      const parts = cp.sublocation_id.split('.');
      if (parts.length >= 2) {
        const locationId = parts[0]; // es. "albachiara"
        await this.loadDepth(3, locationId);
      }
    } else if (cp.location_id) {
      await this.loadDepth(2, cp.zone_id);
    } else if (cp.zone_id) {
      await this.loadDepth(1, cp.region_id);
    } else {
      await this.loadDepth(0, null);
    }
  }

  // ══════════════════════════════════════════════════════
  // TOOLTIP
  // ══════════════════════════════════════════════════════

  showTooltip(event, nodeData) {
    if (!this.tooltip) return;

    const nameEl = this.tooltip.querySelector('.wt-name');
    const descEl = this.tooltip.querySelector('.wt-desc');
    const tagsEl = this.tooltip.querySelector('.wt-tags');
    const hintEl = this.tooltip.querySelector('.wt-hint');

    const isVisible = nodeData.visited !== false || this.depth < 2;

    if (nameEl) nameEl.textContent = isVisible ? nodeData.name : '???';

    if (descEl) {
      if (nodeData.is_current) {
        descEl.textContent = 'Ti trovi qui';
      } else if (!isVisible) {
        descEl.textContent = 'Luogo inesplorato';
      } else if (nodeData.description) {
        // Mostra max 80 caratteri della descrizione
        const desc = nodeData.description;
        descEl.textContent = desc.length > 80 ? desc.substring(0, 77) + '...' : desc;
      } else {
        descEl.textContent = '';
      }
    }

    if (tagsEl) {
      tagsEl.innerHTML = '';
      if (isVisible && nodeData.tags && nodeData.tags.length > 0) {
        nodeData.tags.forEach(tag => {
          const span = document.createElement('span');
          span.className = 'wt-tag';
          span.textContent = tag;
          tagsEl.appendChild(span);
        });
      }
    }

    if (hintEl) {
      if (nodeData.is_leaf && this.depth >= 3) {
        if (!nodeData.visited && !nodeData.is_current) {
          hintEl.textContent = 'Devi esplorare questo luogo dal gioco';
        } else {
          hintEl.textContent = 'Clicca per entrare';
        }
      } else if (nodeData.has_children) {
        hintEl.textContent = 'Clicca per esplorare';
      } else {
        hintEl.textContent = '';
      }
    }

    this.tooltip.classList.add('visible');
    this.moveTooltip(event);
  }

  hideTooltip() {
    this.tooltip?.classList.remove('visible');
  }

  moveTooltip(event) {
    if (!this.tooltip) return;
    this.tooltip.style.left = `${event.clientX}px`;
    this.tooltip.style.top = `${event.clientY - 100}px`;
  }

  // ══════════════════════════════════════════════════════
  // LOCATION PREVIEW PANEL
  // ══════════════════════════════════════════════════════

  initPreviewPanel() {
    this.previewOverlay = document.getElementById('wm-preview-overlay');
    this.previewPanel = document.getElementById('wm-preview-panel');
    this.previewClose = document.getElementById('wm-preview-close');
    this.previewEnter = document.getElementById('wm-preview-enter');
    this.previewBack = document.getElementById('wm-preview-back');

    if (!this.previewOverlay) return;

    // Close handlers
    this.previewClose?.addEventListener('click', () => this.hideLocationPreview());
    this.previewBack?.addEventListener('click', () => this.hideLocationPreview());
    this.previewOverlay?.addEventListener('click', (e) => {
      if (e.target === this.previewOverlay) this.hideLocationPreview();
    });

    // Enter handler — set dynamically in showLocationPreview
    this._previewLocationId = null;
    this.previewEnter?.addEventListener('click', () => {
      if (this._previewLocationId && this.onEnterChat) {
        this.hideLocationPreview();
        this.onEnterChat(this._previewLocationId);
      }
    });
  }

  async showLocationPreview(nodeData) {
    if (!this.previewOverlay) return;

    this._previewLocationId = nodeData.id;
    this.hideTooltip();

    // Show overlay with loading state
    this.previewOverlay.classList.add('visible', 'loading');

    try {
      const data = await getLocationPreview(this.characterId, nodeData.id);

      // Remove loading state
      this.previewOverlay.classList.remove('loading');

      // Populate panel
      const nameEl = document.getElementById('wm-preview-name');
      const typeEl = document.getElementById('wm-preview-type');
      const descEl = document.getElementById('wm-preview-desc');
      const tagsEl = document.getElementById('wm-preview-tags');
      const npcsEl = document.getElementById('wm-preview-npcs');
      const npcsSection = document.getElementById('wm-preview-npcs-section');
      const visitsEl = document.getElementById('wm-preview-visits');
      const visitsSection = document.getElementById('wm-preview-visits-section');

      if (nameEl) nameEl.textContent = data.name || nodeData.name;
      if (typeEl) typeEl.textContent = data.type || '';
      if (descEl) descEl.textContent = data.description || 'Nessuna descrizione disponibile.';

      // Tags
      if (tagsEl) {
        tagsEl.innerHTML = '';
        (data.tags || []).forEach(tag => {
          const span = document.createElement('span');
          span.className = 'wm-preview-tag';
          span.textContent = tag;
          tagsEl.appendChild(span);
        });
      }

      // NPCs
      if (npcsEl && npcsSection) {
        npcsEl.innerHTML = '';
        if (data.npcs && data.npcs.length > 0) {
          npcsSection.style.display = '';
          data.npcs.forEach(npc => {
            const div = document.createElement('div');
            div.className = 'wm-preview-npc';
            div.innerHTML = `
              <span class="wm-preview-npc-name">${npc.name}</span>
              <span class="wm-preview-npc-title">${npc.title || ''}</span>
              <span class="wm-preview-npc-disp ${npc.disposition || 'neutral'}">${npc.disposition || 'neutral'}</span>
            `;
            npcsEl.appendChild(div);
          });
        } else {
          npcsSection.style.display = 'none';
        }
      }

      // Visits
      if (visitsEl && visitsSection) {
        if (data.visit_count > 0) {
          visitsSection.style.display = '';
          const firstDate = data.first_visited ? new Date(data.first_visited).toLocaleDateString('it-IT') : '—';
          const lastDate = data.last_visited ? new Date(data.last_visited).toLocaleDateString('it-IT') : '—';
          visitsEl.innerHTML = `
            Visite totali: <strong>${data.visit_count}</strong><br>
            Prima visita: ${firstDate}<br>
            Ultima visita: ${lastDate}
          `;
        } else {
          visitsSection.style.display = 'none';
        }
      }

      // Update enter button with current indicator
      if (this.previewEnter) {
        if (data.is_current) {
          this.previewEnter.innerHTML = `
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
              <polyline points="10 17 15 12 10 7"></polyline>
              <line x1="15" y1="12" x2="3" y2="12"></line>
            </svg>
            Continua qui
          `;
        } else {
          this.previewEnter.innerHTML = `
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
              <polyline points="10 17 15 12 10 7"></polyline>
              <line x1="15" y1="12" x2="3" y2="12"></line>
            </svg>
            Entra
          `;
        }
      }

    } catch (error) {
      console.error('Preview load error:', error);
      this.previewOverlay.classList.remove('loading');
      // Fallback: show basic info from nodeData
      const nameEl = document.getElementById('wm-preview-name');
      const descEl = document.getElementById('wm-preview-desc');
      if (nameEl) nameEl.textContent = nodeData.name || nodeData.id;
      if (descEl) descEl.textContent = nodeData.description || '';
      document.getElementById('wm-preview-npcs-section').style.display = 'none';
      document.getElementById('wm-preview-visits-section').style.display = 'none';
    }
  }

  hideLocationPreview() {
    this.previewOverlay?.classList.remove('visible', 'loading');
    this._previewLocationId = null;
  }

  // ══════════════════════════════════════════════════════
  // PAN & ZOOM
  // ══════════════════════════════════════════════════════

  initPanZoom() {
    if (!this.svgEl) return;

    // Zoom con rotella
    this.svgEl.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY > 0 ? 1.15 : 0.85;
      const newW = this.viewBox.w * zoomFactor;
      const newH = this.viewBox.h * zoomFactor;

      const baseSize = 600;
      if (newW < baseSize * this.minZoom || newW > baseSize * this.maxZoom) return;

      const rect = this.svgEl.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left) / rect.width;
      const mouseY = (e.clientY - rect.top) / rect.height;

      this.viewBox.x += (this.viewBox.w - newW) * mouseX;
      this.viewBox.y += (this.viewBox.h - newH) * mouseY;
      this.viewBox.w = newW;
      this.viewBox.h = newH;

      this.updateViewBox();
    }, { passive: false });

    // Pan con drag
    this.svgEl.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      this.isPanning = true;
      this.panDistance = 0;
      this.panStart = { x: e.clientX, y: e.clientY };
      this.svgEl.style.cursor = 'grabbing';
    });

    this.svgEl.addEventListener('mousemove', (e) => {
      if (!this.isPanning) return;
      const rect = this.svgEl.getBoundingClientRect();
      const dx = e.clientX - this.panStart.x;
      const dy = e.clientY - this.panStart.y;
      this.panDistance += Math.abs(dx) + Math.abs(dy);

      this.viewBox.x -= dx * (this.viewBox.w / rect.width);
      this.viewBox.y -= dy * (this.viewBox.h / rect.height);
      this.panStart = { x: e.clientX, y: e.clientY };
      this.updateViewBox();
    });

    this.svgEl.addEventListener('mouseup', () => {
      this.isPanning = false;
      this.svgEl.style.cursor = 'grab';
    });

    this.svgEl.addEventListener('mouseleave', () => {
      this.isPanning = false;
      this.svgEl.style.cursor = 'grab';
    });

    this.svgEl.style.cursor = 'grab';

    // Touch support
    let touchStart = null;
    this.svgEl.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        this.panDistance = 0;
      }
    }, { passive: true });

    this.svgEl.addEventListener('touchmove', (e) => {
      if (!touchStart || e.touches.length !== 1) return;
      e.preventDefault();
      const rect = this.svgEl.getBoundingClientRect();
      const dx = e.touches[0].clientX - touchStart.x;
      const dy = e.touches[0].clientY - touchStart.y;
      this.panDistance += Math.abs(dx) + Math.abs(dy);

      this.viewBox.x -= dx * (this.viewBox.w / rect.width);
      this.viewBox.y -= dy * (this.viewBox.h / rect.height);
      touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      this.updateViewBox();
    }, { passive: false });

    this.svgEl.addEventListener('touchend', () => {
      touchStart = null;
    }, { passive: true });
  }

  initKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        // Prima chiudi il preview se aperto
        if (this.previewOverlay?.classList.contains('visible')) {
          this.hideLocationPreview();
          return;
        }
        // Poi zoom out di un livello
        if (this.depth > 0) {
          const parentCrumb = this.breadcrumb[this.breadcrumb.length - 2];
          if (parentCrumb) {
            if (parentCrumb.type === 'world') {
              this.loadDepth(0, null);
            } else {
              const depthMap = { region: 1, zone: 2, location: 3, sublocation: 4 };
              this.loadDepth(depthMap[parentCrumb.type] || 0, parentCrumb.id);
            }
          }
        }
      }
    });
  }

  updateViewBox() {
    if (!this.svgEl) return;
    const vb = this.viewBox;
    this.svgEl.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
  }

  autoFitViewBox() {
    const positions = this.hexPositions;
    const pixelPositions = Object.values(positions).map(p => hexToPixel(p.q, p.r, HEX_SIZE_WORLD));
    if (pixelPositions.length === 0 || !this.svgEl) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    pixelPositions.forEach(p => {
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x);
      maxY = Math.max(maxY, p.y);
    });

    const padding = HEX_SIZE_WORLD * 4;
    this.viewBox.x = minX - padding;
    this.viewBox.y = minY - padding;
    this.viewBox.w = (maxX - minX) + padding * 2;
    this.viewBox.h = (maxY - minY) + padding * 2;

    // Minimo
    const minSize = HEX_SIZE_WORLD * 8;
    if (this.viewBox.w < minSize) {
      const diff = minSize - this.viewBox.w;
      this.viewBox.x -= diff / 2;
      this.viewBox.w = minSize;
    }
    if (this.viewBox.h < minSize) {
      const diff = minSize - this.viewBox.h;
      this.viewBox.y -= diff / 2;
      this.viewBox.h = minSize;
    }

    this.updateViewBox();
  }

  // ══════════════════════════════════════════════════════
  // UI HELPERS
  // ══════════════════════════════════════════════════════

  showLoading(show) {
    if (this.loadingEl) {
      this.loadingEl.style.display = show ? 'flex' : 'none';
    }
  }
}
