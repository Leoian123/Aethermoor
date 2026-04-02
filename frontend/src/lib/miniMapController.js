/**
 * MiniMap Controller — Hex Grid Wargame Edition
 * Rendering SVG esagonale, click-to-move, pan & zoom
 */

import {
  HEX_SIZE_MINI, HEX_SIZE_EXPANDED, SQRT3,
  HEX_DIRECTIONS, TERRAIN_COLORS,
  hexToPixel, hexRound, hexCorners, hexPointsString,
  findNearestFreeHex, calculateHexPositions
} from './hexUtils.js';

// Re-export hex utilities for backward compatibility
export { hexToPixel, hexRound, hexCorners, hexPointsString };

// ══════════════════════════════════════════════════════
// MINIMAP CONTROLLER
// ══════════════════════════════════════════════════════

class MiniMapController {
  constructor() {
    // Mini mappa
    this.container = document.getElementById('minimap-container');
    this.content = document.getElementById('minimap-content');
    this.toggle = document.getElementById('minimap-toggle');
    this.expandBtn = document.getElementById('minimap-expand');
    this.svg = document.getElementById('minimap-svg');
    this.edgesGroup = document.getElementById('minimap-edges');
    this.nodesGroup = document.getElementById('minimap-nodes');
    this.labelsGroup = document.getElementById('minimap-labels');
    this.locationName = document.getElementById('minimap-location-name');
    this.emptyState = document.getElementById('minimap-empty');

    // Tooltip
    this.tooltip = document.getElementById('minimap-tooltip');

    // Modal
    this.modalOverlay = document.getElementById('minimap-modal-overlay');
    this.modalClose = document.getElementById('minimap-modal-close');
    this.svgExpanded = document.getElementById('minimap-svg-expanded');
    this.edgesGroupExpanded = document.getElementById('minimap-edges-expanded');
    this.nodesGroupExpanded = document.getElementById('minimap-nodes-expanded');
    this.labelsGroupExpanded = document.getElementById('minimap-labels-expanded');

    // Movement confirm elements
    this.moveConfirm = document.getElementById('hex-move-confirm');
    this.moveTargetName = document.getElementById('move-target-name');
    this.moveBtnYes = document.getElementById('move-btn-yes');
    this.moveBtnNo = document.getElementById('move-btn-no');
    this.moveFeedback = document.getElementById('hex-move-feedback');
    this.moveFeedbackText = document.getElementById('move-feedback-text');

    this.characterId = null;
    this.data = null;
    this.isExpanded = false;

    // Pan & Zoom state
    this.viewBox = { x: -120, y: -120, w: 240, h: 240 };
    this.viewBoxExpanded = { x: -200, y: -200, w: 400, h: 400 };
    this.isPanning = false;
    this.panStart = { x: 0, y: 0 };
    this.panDistance = 0;
    this.minZoom = 0.5;
    this.maxZoom = 3;

    // Hex state
    this.hexPositions = {};
    this.adjacencyMap = {};
    this.currentNodeId = null;
    this.isMoving = false;
    this.onMoveCallback = null;

    this.init();
  }

  init() {
    // Toggle collapse
    this.toggle?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleCollapse();
    });

    // Expand button
    this.expandBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.openModal();
    });

    // Close modal
    this.modalClose?.addEventListener('click', () => this.closeModal());
    this.modalOverlay?.addEventListener('click', (e) => {
      if (e.target === this.modalOverlay) this.closeModal();
    });

    // ESC to close
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (this.moveConfirm?.classList.contains('visible')) {
          this.hideMoveConfirmation();
        } else if (this.isExpanded) {
          this.closeModal();
        }
      }
    });

    // Pan & Zoom per mini mappa
    this.initPanZoom(this.svg, false);

    // Load collapsed state
    const collapsed = localStorage.getItem('minimap-collapsed') === 'true';
    if (collapsed) {
      this.container?.classList.add('collapsed');
    }
  }

  initPanZoom(svgElement, isExpanded) {
    if (!svgElement) return;

    // Zoom con rotella
    svgElement.addEventListener('wheel', (e) => {
      e.preventDefault();
      const vb = isExpanded ? this.viewBoxExpanded : this.viewBox;

      const zoomFactor = e.deltaY > 0 ? 1.15 : 0.85;
      const newW = vb.w * zoomFactor;
      const newH = vb.h * zoomFactor;

      const baseSize = isExpanded ? 400 : 240;
      if (newW < baseSize * this.minZoom || newW > baseSize * this.maxZoom) return;

      const rect = svgElement.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left) / rect.width;
      const mouseY = (e.clientY - rect.top) / rect.height;

      vb.x += (vb.w - newW) * mouseX;
      vb.y += (vb.h - newH) * mouseY;
      vb.w = newW;
      vb.h = newH;

      this.updateViewBox(svgElement, vb);
    }, { passive: false });

    // Pan con click + drag (with panDistance tracking)
    svgElement.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      this.isPanning = true;
      this.panDistance = 0;
      this.panStart = { x: e.clientX, y: e.clientY };
      svgElement.style.cursor = 'grabbing';
    });

    svgElement.addEventListener('mousemove', (e) => {
      if (!this.isPanning) return;

      const vb = isExpanded ? this.viewBoxExpanded : this.viewBox;
      const rect = svgElement.getBoundingClientRect();

      const dx = e.clientX - this.panStart.x;
      const dy = e.clientY - this.panStart.y;
      this.panDistance += Math.abs(dx) + Math.abs(dy);

      const svgDx = dx * (vb.w / rect.width);
      const svgDy = dy * (vb.h / rect.height);

      vb.x -= svgDx;
      vb.y -= svgDy;

      this.panStart = { x: e.clientX, y: e.clientY };
      this.updateViewBox(svgElement, vb);
    });

    svgElement.addEventListener('mouseup', () => {
      this.isPanning = false;
      svgElement.style.cursor = 'grab';
    });

    svgElement.addEventListener('mouseleave', () => {
      this.isPanning = false;
      svgElement.style.cursor = 'grab';
    });

    svgElement.style.cursor = 'grab';
  }

  updateViewBox(svgElement, vb) {
    svgElement.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
  }

  toggleCollapse() {
    this.container?.classList.toggle('collapsed');
    const isCollapsed = this.container?.classList.contains('collapsed');
    localStorage.setItem('minimap-collapsed', isCollapsed.toString());
  }

  openModal() {
    this.isExpanded = true;
    this.modalOverlay?.classList.add('active');
    document.body.style.overflow = 'hidden';

    setTimeout(() => {
      this.initPanZoom(this.svgExpanded, true);
      this.renderExpanded();
    }, 50);
  }

  closeModal() {
    this.isExpanded = false;
    this.modalOverlay?.classList.remove('active');
    document.body.style.overflow = '';
    // Reset expanded viewBox
    this.viewBoxExpanded = { x: -200, y: -200, w: 400, h: 400 };
    if (this.svgExpanded) {
      this.updateViewBox(this.svgExpanded, this.viewBoxExpanded);
    }
  }

  setCharacterId(id) {
    this.characterId = id;
  }

  setOnMove(callback) {
    this.onMoveCallback = callback;
  }

  async refresh() {
    if (!this.characterId) return;

    try {
      const token = localStorage.getItem('statisfy_token');
      const API_BASE = import.meta.env?.PUBLIC_API_URL || 'http://localhost:5000';
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(
        `${API_BASE}/api/character/${this.characterId}/location/neighborhood`,
        { headers }
      );

      if (!response.ok) {
        if (response.status === 401) {
          console.warn('MiniMap: token scaduto o assente');
        }
        this.showEmpty();
        return;
      }

      const data = await response.json();
      this.render(data);
    } catch (error) {
      console.warn('MiniMap: impossibile caricare dati', error);
      this.showEmpty();
    }
  }

  render(data) {
    this.data = data;

    const hasNodes = data.nodes && data.nodes.length > 0;

    if (!data.has_location || !hasNodes) {
      this.showEmpty();
      return;
    }

    this.hideEmpty();
    this.renderToSvg(
      this.edgesGroup,
      this.nodesGroup,
      this.labelsGroup,
      data,
      HEX_SIZE_MINI,
      false
    );

    // Update location name
    const nameSpan = this.locationName?.querySelector('.location-current');
    if (nameSpan && hasNodes && data.current_id) {
      const currentNode = data.nodes.find(n => n.id === data.current_id || n.is_current);
      nameSpan.textContent = currentNode?.name || data.location_name || '—';
    }

    if (this.isExpanded) {
      this.renderExpanded();
    }
  }

  renderExpanded() {
    if (!this.data || !this.data.has_location) return;

    this.renderToSvg(
      this.edgesGroupExpanded,
      this.nodesGroupExpanded,
      this.labelsGroupExpanded,
      this.data,
      HEX_SIZE_EXPANDED,
      true
    );
  }

  buildAdjacencyMap(edges) {
    this.adjacencyMap = {};
    edges.forEach(edge => {
      if (!this.adjacencyMap[edge.from]) this.adjacencyMap[edge.from] = new Set();
      if (!this.adjacencyMap[edge.to]) this.adjacencyMap[edge.to] = new Set();
      this.adjacencyMap[edge.from].add(edge.to);
      this.adjacencyMap[edge.to].add(edge.from);
    });
  }

  // ══════════════════════════════════════════════════════
  // RENDERING
  // ══════════════════════════════════════════════════════

  renderToSvg(edgesGroup, nodesGroup, labelsGroup, data, hexSize, isExpanded) {
    if (!edgesGroup || !nodesGroup || !labelsGroup) return;

    edgesGroup.innerHTML = '';
    nodesGroup.innerHTML = '';
    labelsGroup.innerHTML = '';

    const nodes = data.nodes || [];
    const edges = data.edges || [];
    const currentId = data.current_id;
    this.currentNodeId = currentId;

    if (nodes.length === 0) return;

    // Build adjacency map
    this.buildAdjacencyMap(edges);

    // Calculate hex positions (using shared utility)
    this.hexPositions = calculateHexPositions(nodes, edges, currentId);

    // Ghost hex background
    const ghostRings = isExpanded ? 2 : 1;
    this.renderGhostHexes(edgesGroup, this.hexPositions, hexSize, ghostRings);

    // Edges
    edges.forEach(edge => {
      const fromHex = this.hexPositions[edge.from];
      const toHex = this.hexPositions[edge.to];
      if (fromHex && toHex) {
        const fromPx = hexToPixel(fromHex.q, fromHex.r, hexSize);
        const toPx = hexToPixel(toHex.q, toHex.r, hexSize);
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', fromPx.x.toFixed(1));
        line.setAttribute('y1', fromPx.y.toFixed(1));
        line.setAttribute('x2', toPx.x.toFixed(1));
        line.setAttribute('y2', toPx.y.toFixed(1));
        line.setAttribute('data-from', edge.from);
        line.setAttribute('data-to', edge.to);
        if (edge.locked) line.classList.add('locked');
        edgesGroup.appendChild(line);
      }
    });

    // Hex nodes
    nodes.forEach(node => {
      const hex = this.hexPositions[node.id];
      if (!hex) return;
      const px = hexToPixel(hex.q, hex.r, hexSize);
      const isCurrent = node.id === currentId || node.is_current;
      this.renderHexNode(nodesGroup, px.x, px.y, node, hexSize, isExpanded, isCurrent, hex.q, hex.r);
    });

    // Labels
    nodes.forEach(node => {
      const hex = this.hexPositions[node.id];
      if (!hex) return;
      const px = hexToPixel(hex.q, hex.r, hexSize);
      const isCurrent = node.id === currentId || node.is_current;
      const labelY = px.y + hexSize + (isExpanded ? 10 : 6);
      const maxChars = isExpanded ? 18 : 8;
      this.renderLabel(labelsGroup, px.x, labelY, node.name, isCurrent, isExpanded, node.visited, maxChars);
    });

    // Mark reachable
    this.markReachableHexes(nodesGroup);

    // Auto-fit viewBox
    const svgEl = isExpanded ? this.svgExpanded : this.svg;
    const vb = isExpanded ? this.viewBoxExpanded : this.viewBox;
    this.autoFitViewBox(this.hexPositions, hexSize, svgEl, vb);
  }

  renderHexNode(group, cx, cy, nodeData, hexSize, isExpanded, isCurrent, hexQ, hexR) {
    const hexGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    hexGroup.classList.add('hex-node');
    hexGroup.setAttribute('data-node-id', nodeData.id);

    // Pulse ring behind current hex
    if (isCurrent) {
      const ring = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      ring.setAttribute('points', hexPointsString(cx, cy, hexSize + 4));
      ring.classList.add('hex-pulse-ring');
      group.appendChild(ring);
    }

    // Main hex polygon
    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', hexPointsString(cx, cy, hexSize));

    // Determine colors and apply inline SVG attributes (most reliable for dynamic elements)
    let colors;
    if (isCurrent) {
      polygon.classList.add('hex-current');
      colors = TERRAIN_COLORS.current;
    } else if (nodeData.locked) {
      polygon.classList.add('hex-locked');
      colors = TERRAIN_COLORS.locked;
    } else if (nodeData.visited) {
      polygon.classList.add('hex-visited');
      const terrainType = nodeData.type || 'default';
      polygon.setAttribute('data-terrain', terrainType);
      colors = TERRAIN_COLORS[terrainType] || TERRAIN_COLORS.default;
    } else {
      polygon.classList.add('hex-unvisited');
      colors = TERRAIN_COLORS.unvisited;
    }

    // Apply fill, stroke, stroke-width inline — guaranteed to work
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
      token.setAttribute('r', (hexSize * 0.3).toFixed(1));
      token.classList.add('player-token');
      hexGroup.appendChild(token);
    } else if (!nodeData.visited && !nodeData.locked) {
      // Fog overlay
      const fog = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      fog.setAttribute('points', hexPointsString(cx, cy, hexSize));
      fog.classList.add('hex-fog');
      hexGroup.appendChild(fog);
      // Question mark
      const qMark = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      qMark.setAttribute('x', cx.toFixed(1));
      qMark.setAttribute('y', (cy + hexSize * 0.25).toFixed(1));
      qMark.setAttribute('text-anchor', 'middle');
      qMark.classList.add('hex-question');
      qMark.textContent = '?';
      hexGroup.appendChild(qMark);
    } else if (nodeData.locked) {
      const lockIcon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      lockIcon.setAttribute('x', cx.toFixed(1));
      lockIcon.setAttribute('y', (cy + hexSize * 0.25).toFixed(1));
      lockIcon.setAttribute('text-anchor', 'middle');
      lockIcon.classList.add('hex-lock-icon');
      lockIcon.textContent = '\u{1F512}';
      hexGroup.appendChild(lockIcon);
    }

    // Coordinate label (expanded only)
    if (isExpanded) {
      const coord = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      coord.setAttribute('x', (cx + hexSize * 0.5).toFixed(1));
      coord.setAttribute('y', (cy + hexSize * 0.7).toFixed(1));
      coord.textContent = `${hexQ},${hexR}`;
      coord.classList.add('hex-coord');
      hexGroup.appendChild(coord);
    }

    // Tooltip events
    polygon.addEventListener('mouseenter', (e) => {
      if (!this.isPanning) this.showTooltip(e, { ...nodeData, isCurrent });
    });
    polygon.addEventListener('mouseleave', () => this.hideTooltip());
    polygon.addEventListener('mousemove', (e) => {
      if (!this.isPanning) this.moveTooltip(e);
    });

    // Click-to-move
    hexGroup.addEventListener('click', (e) => {
      if (this.panDistance > 5) return; // was a pan, not a click
      e.stopPropagation();
      this.handleHexClick(nodeData);
    });

    group.appendChild(hexGroup);
  }

  renderGhostHexes(group, positions, hexSize, rings) {
    const dataKeys = new Set(Object.values(positions).map(p => `${p.q},${p.r}`));
    const ghostKeys = new Set();

    Object.values(positions).forEach(pos => {
      for (let ring = 1; ring <= rings; ring++) {
        // Walk the hex ring
        let q = pos.q;
        let r = pos.r - ring;
        const ringDirs = [
          { q: +1, r: 0 }, { q: 0, r: +1 }, { q: -1, r: +1 },
          { q: -1, r: 0 }, { q: 0, r: -1 }, { q: +1, r: -1 }
        ];
        for (const dir of ringDirs) {
          for (let step = 0; step < ring; step++) {
            const key = `${q},${r}`;
            if (!dataKeys.has(key) && !ghostKeys.has(key)) {
              ghostKeys.add(key);
            }
            q += dir.q;
            r += dir.r;
          }
        }
      }
    });

    ghostKeys.forEach(key => {
      const [gq, gr] = key.split(',').map(Number);
      const { x, y } = hexToPixel(gq, gr, hexSize);
      const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      polygon.setAttribute('points', hexPointsString(x, y, hexSize));
      polygon.classList.add('hex-ghost');
      group.appendChild(polygon);
    });
  }

  renderLabel(group, x, y, text, isCurrent, isExpanded, isVisited, maxChars) {
    const displayText = isVisited
      ? (text.length > maxChars ? text.substring(0, maxChars - 1) + '\u2026' : text)
      : '???';

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x.toFixed(1));
    label.setAttribute('y', y.toFixed(1));
    label.textContent = displayText;

    if (isCurrent) label.classList.add('label-current');
    if (!isVisited) label.classList.add('label-unknown');

    const fontSize = isExpanded ? 10 : 7;
    label.style.fontSize = `${fontSize}px`;

    group.appendChild(label);
  }

  autoFitViewBox(positions, hexSize, svgElement, viewBoxState) {
    const pixelPositions = Object.values(positions).map(p => hexToPixel(p.q, p.r, hexSize));
    if (pixelPositions.length === 0 || !svgElement) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    pixelPositions.forEach(p => {
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x);
      maxY = Math.max(maxY, p.y);
    });

    const padding = hexSize * 3;
    viewBoxState.x = minX - padding;
    viewBoxState.y = minY - padding;
    viewBoxState.w = (maxX - minX) + padding * 2;
    viewBoxState.h = (maxY - minY) + padding * 2;

    // Ensure minimum size
    const minSize = hexSize * 6;
    if (viewBoxState.w < minSize) {
      const diff = minSize - viewBoxState.w;
      viewBoxState.x -= diff / 2;
      viewBoxState.w = minSize;
    }
    if (viewBoxState.h < minSize) {
      const diff = minSize - viewBoxState.h;
      viewBoxState.y -= diff / 2;
      viewBoxState.h = minSize;
    }

    this.updateViewBox(svgElement, viewBoxState);
  }

  markReachableHexes(nodesGroup) {
    const reachable = this.adjacencyMap[this.currentNodeId] || new Set();
    nodesGroup.querySelectorAll('.hex-node').forEach(hexGroup => {
      const nodeId = hexGroup.getAttribute('data-node-id');
      if (reachable.has(nodeId) && nodeId !== this.currentNodeId) {
        hexGroup.classList.add('hex-reachable');
      }
    });
  }

  // ══════════════════════════════════════════════════════
  // CLICK-TO-MOVE
  // ══════════════════════════════════════════════════════

  handleHexClick(nodeData) {
    if (this.isMoving) return;
    if (nodeData.is_current || nodeData.id === this.currentNodeId) return;
    if (nodeData.locked) {
      this.showMovementFeedback('Passaggio bloccato', 'error');
      return;
    }

    const reachable = this.adjacencyMap[this.currentNodeId] || new Set();
    if (!reachable.has(nodeData.id)) {
      this.showMovementFeedback('Troppo lontano', 'error');
      return;
    }

    this.showMoveConfirmation(nodeData);
  }

  showMoveConfirmation(nodeData) {
    if (!this.moveConfirm || !this.moveTargetName) return;

    this.moveTargetName.textContent = nodeData.visited ? nodeData.name : '???';
    this.moveConfirm.classList.add('visible');

    this.highlightPath(this.currentNodeId, nodeData.id);

    // Clean up previous listeners
    const newYes = this.moveBtnYes.cloneNode(true);
    const newNo = this.moveBtnNo.cloneNode(true);
    this.moveBtnYes.parentNode.replaceChild(newYes, this.moveBtnYes);
    this.moveBtnNo.parentNode.replaceChild(newNo, this.moveBtnNo);
    this.moveBtnYes = newYes;
    this.moveBtnNo = newNo;

    newYes.addEventListener('click', () => {
      this.hideMoveConfirmation();
      this.executeMove(nodeData.id);
    });

    newNo.addEventListener('click', () => {
      this.hideMoveConfirmation();
    });
  }

  hideMoveConfirmation() {
    this.moveConfirm?.classList.remove('visible');
    this.clearPathHighlight();
  }

  highlightPath(fromId, toId) {
    // Highlight in both mini and expanded views
    document.querySelectorAll('.minimap-edges line').forEach(line => {
      const lineFrom = line.getAttribute('data-from');
      const lineTo = line.getAttribute('data-to');
      if ((lineFrom === fromId && lineTo === toId) ||
          (lineFrom === toId && lineTo === fromId)) {
        line.classList.add('edge-highlighted');
      }
    });
  }

  clearPathHighlight() {
    document.querySelectorAll('.edge-highlighted').forEach(el => {
      el.classList.remove('edge-highlighted');
    });
  }

  async executeMove(targetId) {
    if (this.isMoving) return;
    this.isMoving = true;

    try {
      this.showMovementFeedback('Spostamento...', 'info');

      if (this.onMoveCallback) {
        await this.onMoveCallback(this.currentNodeId, targetId);
      }

      await this.refresh();
      this.showMovementFeedback('Arrivato!', 'success');
      setTimeout(() => this.hideMovementFeedback(), 1500);
    } catch (error) {
      console.error('Movement failed:', error);
      this.showMovementFeedback('Movimento fallito', 'error');
      setTimeout(() => this.hideMovementFeedback(), 2000);
    } finally {
      this.isMoving = false;
    }
  }

  showMovementFeedback(text, type) {
    if (!this.moveFeedback || !this.moveFeedbackText) return;
    this.moveFeedbackText.textContent = text;
    this.moveFeedback.className = `hex-move-feedback visible ${type}`;

    if (type === 'error') {
      setTimeout(() => this.hideMovementFeedback(), 2000);
    }
  }

  hideMovementFeedback() {
    this.moveFeedback?.classList.remove('visible', 'info', 'success', 'error');
  }

  // ══════════════════════════════════════════════════════
  // TOOLTIP
  // ══════════════════════════════════════════════════════

  showTooltip(event, nodeData) {
    if (!this.tooltip) return;

    const tooltipName = this.tooltip.querySelector('.tooltip-name');
    const tooltipDesc = this.tooltip.querySelector('.tooltip-desc');
    const tooltipTags = this.tooltip.querySelector('.tooltip-tags');

    if (tooltipName) {
      tooltipName.textContent = nodeData.visited || nodeData.isCurrent ? nodeData.name : '???';
    }

    if (tooltipDesc) {
      if (nodeData.isCurrent) {
        tooltipDesc.textContent = 'Ti trovi qui';
      } else if (nodeData.locked) {
        tooltipDesc.textContent = `Passaggio bloccato${nodeData.label ? ` (${nodeData.label})` : ''}`;
      } else if (!nodeData.visited) {
        tooltipDesc.textContent = 'Chissà cosa c\'è qui...';
      } else {
        tooltipDesc.textContent = nodeData.label ? `Via: ${nodeData.label}` : 'Luogo già esplorato';
      }
    }

    if (tooltipTags) {
      tooltipTags.innerHTML = '';
      if ((nodeData.visited || nodeData.isCurrent) && nodeData.tags && nodeData.tags.length > 0) {
        nodeData.tags.forEach(tag => {
          const tagSpan = document.createElement('span');
          tagSpan.className = 'tooltip-tag';
          tagSpan.textContent = tag;
          tooltipTags.appendChild(tagSpan);
        });
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
    const x = event.clientX;
    const y = event.clientY;
    this.tooltip.style.position = 'fixed';
    this.tooltip.style.left = `${x}px`;
    this.tooltip.style.top = `${y - 90}px`;
    this.tooltip.style.transform = 'translateX(-50%)';
  }

  showEmpty() {
    this.emptyState?.classList.add('active');
    this.svg?.classList.add('hidden');
    this.locationName?.classList.add('hidden');
  }

  hideEmpty() {
    this.emptyState?.classList.remove('active');
    this.svg?.classList.remove('hidden');
    this.locationName?.classList.remove('hidden');
  }
}

export default MiniMapController;
