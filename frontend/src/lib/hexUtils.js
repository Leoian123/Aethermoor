/**
 * Hex Math Utilities — Shared between MiniMap and WorldMap
 * Pointy-top hexagons, axial coordinates
 */

// ══════════════════════════════════════════════════════
// CONSTANTS
// ══════════════════════════════════════════════════════

export const HEX_SIZE_MINI = 18;
export const HEX_SIZE_EXPANDED = 28;
export const SQRT3 = Math.sqrt(3);

export const HEX_DIRECTIONS = [
  { q: +1, r:  0 }, // east
  { q: +1, r: -1 }, // northeast
  { q:  0, r: -1 }, // northwest
  { q: -1, r:  0 }, // west
  { q: -1, r: +1 }, // southwest
  { q:  0, r: +1 }, // southeast
];

// Terrain color palette — lighter tones for parchment background
export const TERRAIN_COLORS = {
  // Sublocation types (used by MiniMap)
  current:   { fill: '#8b2d3a', stroke: '#c41e3a', strokeWidth: 2.5 },
  outdoor:   { fill: '#7a9b5a', stroke: '#5a7a42', strokeWidth: 1.5 },
  indoor:    { fill: '#a08b6f', stroke: '#7a6a50', strokeWidth: 1.5 },
  room:      { fill: '#9a8573', stroke: '#7a6558', strokeWidth: 1.5 },
  shop:      { fill: '#b8a44c', stroke: '#8a7a38', strokeWidth: 1.5 },
  village:   { fill: '#8fa07a', stroke: '#6a7a58', strokeWidth: 1.5 },
  sacred:    { fill: '#8888aa', stroke: '#6a6a8a', strokeWidth: 1.5 },
  dungeon:   { fill: '#7a6b8a', stroke: '#5a4b6a', strokeWidth: 1.5 },
  water:     { fill: '#5a8aaa', stroke: '#3a6a8a', strokeWidth: 1.5 },
  default:   { fill: '#9a8b70', stroke: '#7a6b50', strokeWidth: 1.5 },
  unvisited: { fill: '#6b604a', stroke: '#4a4232', strokeWidth: 1.5 },
  locked:    { fill: '#5a4535', stroke: '#3a2a1a', strokeWidth: 1.5 },

  // World map types (used by WorldMap at higher depth levels)
  kingdom:   { fill: '#6a8b5a', stroke: '#4a6b3a', strokeWidth: 2 },
  valley:    { fill: '#7a8b6a', stroke: '#5a6b4a', strokeWidth: 1.8 },
  city:      { fill: '#8a7a6a', stroke: '#6a5a4a', strokeWidth: 1.5 },
  region:    { fill: '#6a8b5a', stroke: '#4a6b3a', strokeWidth: 2 },
  zone:      { fill: '#7a8b9a', stroke: '#5a6b7a', strokeWidth: 1.8 },
  forest:    { fill: '#5a7a4a', stroke: '#3a5a2a', strokeWidth: 1.5 },
  mountain:  { fill: '#8a8a8a', stroke: '#6a6a6a', strokeWidth: 1.5 },
  swamp:     { fill: '#6a7a5a', stroke: '#4a5a3a', strokeWidth: 1.5 },
  desert:    { fill: '#b8a87a', stroke: '#9a8a5a', strokeWidth: 1.5 },
  crossroad: { fill: '#9a9080', stroke: '#7a7060', strokeWidth: 1.5 },
};

// ══════════════════════════════════════════════════════
// HEX MATH FUNCTIONS
// ══════════════════════════════════════════════════════

export function hexToPixel(q, r, size) {
  const x = size * (SQRT3 * q + SQRT3 / 2 * r);
  const y = size * (3 / 2 * r);
  return { x, y };
}

export function hexRound(q, r) {
  const s = -q - r;
  let rq = Math.round(q);
  let rr = Math.round(r);
  let rs = Math.round(s);
  const qDiff = Math.abs(rq - q);
  const rDiff = Math.abs(rr - r);
  const sDiff = Math.abs(rs - s);
  if (qDiff > rDiff && qDiff > sDiff) {
    rq = -rr - rs;
  } else if (rDiff > sDiff) {
    rr = -rq - rs;
  }
  return { q: rq, r: rr };
}

export function hexCorners(cx, cy, size) {
  const points = [];
  for (let i = 0; i < 6; i++) {
    const angleDeg = 60 * i - 30; // pointy-top: first corner at -30°
    const angleRad = (Math.PI / 180) * angleDeg;
    points.push({
      x: cx + size * Math.cos(angleRad),
      y: cy + size * Math.sin(angleRad)
    });
  }
  return points;
}

export function hexPointsString(cx, cy, size) {
  return hexCorners(cx, cy, size)
    .map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ');
}

// ══════════════════════════════════════════════════════
// HEX LAYOUT ALGORITHMS
// ══════════════════════════════════════════════════════

/**
 * Find the nearest free hex position in expanding rings.
 */
export function findNearestFreeHex(centerQ, centerR, occupied) {
  const ringDirs = [
    { q: 0, r: -1 }, { q: +1, r: -1 }, { q: +1, r: 0 },
    { q: 0, r: +1 }, { q: -1, r: +1 }, { q: -1, r: 0 }
  ];
  for (let ring = 1; ring < 10; ring++) {
    let q = centerQ;
    let r = centerR - ring;
    for (const dir of ringDirs) {
      for (let step = 0; step < ring; step++) {
        const key = `${q},${r}`;
        if (!occupied.has(key)) return { q, r };
        q += dir.q;
        r += dir.r;
      }
    }
  }
  return { q: centerQ + 5, r: centerR };
}

/**
 * Calculate hex positions for nodes using BFS layout from the current node.
 * Pure function — no side effects, returns {nodeId: {q, r}} map.
 */
export function calculateHexPositions(nodes, edges, currentId) {
  const positions = {};
  const occupied = new Set();

  if (!nodes || nodes.length === 0) return positions;

  // Build adjacency list
  const adj = {};
  nodes.forEach(n => { adj[n.id] = []; });
  edges.forEach(e => {
    if (adj[e.from]) adj[e.from].push(e.to);
    if (adj[e.to]) adj[e.to].push(e.from);
  });

  // Place current node at origin
  const centerId = currentId || nodes.find(n => n.is_current)?.id || nodes[0]?.id;
  positions[centerId] = { q: 0, r: 0 };
  occupied.add('0,0');

  // BFS
  const queue = [centerId];
  const visited = new Set([centerId]);

  while (queue.length > 0) {
    const nodeId = queue.shift();
    const parentPos = positions[nodeId];
    const neighbors = (adj[nodeId] || []).filter(id => !visited.has(id));

    let dirIndex = 0;
    for (const neighborId of neighbors) {
      visited.add(neighborId);
      queue.push(neighborId);

      let placed = false;
      for (let attempt = 0; attempt < 6; attempt++) {
        const dir = HEX_DIRECTIONS[(dirIndex + attempt) % 6];
        const cq = parentPos.q + dir.q;
        const cr = parentPos.r + dir.r;
        const key = `${cq},${cr}`;
        if (!occupied.has(key)) {
          positions[neighborId] = { q: cq, r: cr };
          occupied.add(key);
          dirIndex = (dirIndex + attempt + 1) % 6;
          placed = true;
          break;
        }
      }

      if (!placed) {
        const pos = findNearestFreeHex(parentPos.q, parentPos.r, occupied);
        positions[neighborId] = pos;
        occupied.add(`${pos.q},${pos.r}`);
      }
    }
  }

  // Handle disconnected nodes
  nodes.forEach(n => {
    if (!positions[n.id]) {
      const pos = findNearestFreeHex(0, 0, occupied);
      positions[n.id] = pos;
      occupied.add(`${pos.q},${pos.r}`);
    }
  });

  return positions;
}
