const yearInput = document.getElementById('year');
const yearLabel = document.getElementById('yearInput');
const issueSelect = document.getElementById('issue');
const scaleSelect = document.getElementById('scale');
const detailsEl = document.getElementById('details');

let meta = null;
let state = null;
let selectedPersonId = null;
let selectedEdgeId = null;

// --- Map ---
let map = null;
let markersByPersonId = new Map();

function initMap() {
  map = L.map('map', { zoomControl: true });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // Default view: South Carolina-ish
  map.setView([33.8, -81.1], 7);
}

function clearMapMarkers() {
  for (const m of markersByPersonId.values()) {
    m.remove();
  }
  markersByPersonId.clear();
}

function renderMap(nodes) {
  clearMapMarkers();

  for (const n of nodes) {
    const place = n.map_place;
    if (!place || place.latitude == null || place.longitude == null) continue;

    const isSelected = n.person_id === selectedPersonId;
    const radius = isSelected ? 9 : 6;

    const marker = L.circleMarker([place.latitude, place.longitude], {
      radius,
      weight: 1,
      color: isSelected ? '#4f7cff' : '#a9acb3',
      fillColor: isSelected ? '#4f7cff' : '#a9acb3',
      fillOpacity: 0.85,
    }).addTo(map);

    marker.on('click', () => {
      selectPerson(n.person_id);
    });

    marker.bindTooltip(`${escapeHtml(n.name)}<br/><span style="color:#a9acb3">${escapeHtml(place.place_name)}</span>`);
    markersByPersonId.set(n.person_id, marker);
  }
}

// --- Network ---
const svg = d3.select('#network');
let sim = null;
let zoomBehavior = null;
let zoomRoot = null; // <g> that zoom/pan transforms apply to

// Filter / display state
const filterState = {
  search: '',
  codedOnly: false,
  hideCoMentions: true,
  focusOnSelected: true,
  showAllLabels: false,
  allYears: false,
  // Layer toggles. "Relationships" and "Shared membership" default ON to
  // preserve the previous network appearance; "Co-residence" is a new opt-in.
  layerRelationship: true,
  layerCoResidence: false,
  layerSharedMembership: true,
};

// --- Layered-edge helpers ----------------------------------------------------
// Each edge from /api/state carries a `layers: []` array. Top-level fields are
// kept for back-compat but the source of truth for what to render is the
// filtered layer set returned by visibleLayers(e).

function visibleLayers(e) {
  if (!Array.isArray(e.layers)) return [];
  return e.layers.filter(layer => {
    if (layer.kind === 'relationship') {
      if (!filterState.layerRelationship) return false;
      if (filterState.hideCoMentions && layer.relationship_type_code === 'co_mentioned') return false;
      return true;
    }
    if (layer.kind === 'shared_membership') return filterState.layerSharedMembership;
    if (layer.kind === 'co_residence') return filterState.layerCoResidence;
    return false;
  });
}

function primaryVisibleLayer(layers) {
  return layers.find(l => l.kind === 'relationship')
      || layers.find(l => l.kind === 'shared_membership')
      || layers.find(l => l.kind === 'co_residence')
      || null;
}

function edgeStrokeColor(layer) {
  if (!layer) return '#a9acb3';
  if (layer.kind === 'relationship') return alignmentColor(layer.alignment_status_code);
  if (layer.kind === 'shared_membership') return '#7aa2ff';
  if (layer.kind === 'co_residence') return '#e0a458';
  return '#a9acb3';
}

function edgeDashArray(layer) {
  if (!layer) return null;
  if (layer.kind === 'shared_membership') return '6 4';
  if (layer.kind === 'co_residence') return '2 4';
  return null;
}

function edgeStrokeWidth(layer) {
  if (!layer) return 1.5;
  if (layer.kind === 'relationship') return (layer.strength || 1) * 1.5;
  if (layer.kind === 'shared_membership') return 3;
  if (layer.kind === 'co_residence') return 2.5;
  return 1.5;
}

function layerLabel(l) {
  if (l.kind === 'relationship') return l.relationship_type_code || 'relationship';
  if (l.kind === 'shared_membership') {
    const orgs = l.orgs || '';
    return l.count > 1 ? `shared orgs (${l.count}): ${orgs}` : `shared org: ${orgs}`;
  }
  if (l.kind === 'co_residence') {
    const place = l.place_name || '';
    return l.count > 1 ? `co-residence (${l.count} places): ${place}` : `co-residence: ${place}`;
  }
  return l.kind;
}

function edgeKey(e) {
  return e.edge_id || e.relationship_id;
}

function svgSize() {
  const rect = document.getElementById('network').getBoundingClientRect();
  return { width: Math.max(200, rect.width), height: Math.max(200, rect.height) };
}

function alignmentColor(code) {
  // Minimal palette with clear semantics.
  switch (code) {
    case 'aligned': return '#46d369';
    case 'partially_aligned': return '#9be37b';
    case 'strained': return '#f2c14e';
    case 'fractured': return '#ff6b6b';
    case 'adversarial': return '#ff3b3b';
    default: return '#a9acb3';
  }
}

function stanceColor(code) {
  // Categorical stance palette (Phase 2 schema).
  switch (code) {
    case 'supports':  return '#46d369'; // green
    case 'opposes':   return '#ff6b6b'; // red
    case 'qualified': return '#f2c14e'; // amber
    case 'unknown':   return '#9aa0aa'; // mid gray
    default:          return '#e8e8ea'; // no row at this year/issue
  }
}

function normSearch(s) {
  return String(s ?? '').trim().toLowerCase();
}

function nodeMatchesSearch(n, q) {
  if (!q) return false;
  return (
    String(n.name || '').toLowerCase().includes(q) ||
    String(n.full_name || '').toLowerCase().includes(q) ||
    String(n.display_name || '').toLowerCase().includes(q)
  );
}

function isPersonCoded(n) {
  // "Coded" = has a stance row for the current issue at the current year.
  // Falls back to position_label_code for any rows still on the legacy schema.
  return Boolean(n.stance_code || n.position_label_code);
}

function isCoMentionEdge(e) {
  return e.relationship_type_code === 'co_mentioned';
}

function applyFilters(nodes, edges) {
  let filteredNodes = nodes;
  let filteredEdges = edges;

  if (filterState.codedOnly) {
    filteredNodes = filteredNodes.filter(isPersonCoded);
  }

  // Drop edges that have no visible layer under the current toggles.
  // (hideCoMentions is now folded into visibleLayers as a within-layer filter.)
  filteredEdges = filteredEdges.filter(e => visibleLayers(e).length > 0);

  // Keep only edges whose endpoints survived the node filter.
  const keepIds = new Set(filteredNodes.map(n => n.person_id));
  filteredEdges = filteredEdges.filter(e => keepIds.has(e.source) && keepIds.has(e.target));

  return { filteredNodes, filteredEdges };
}

function renderNetwork(nodes, edges) {
  const { width, height } = svgSize();
  svg.attr('viewBox', `0 0 ${width} ${height}`);
  svg.selectAll('*').remove();

  const { filteredNodes, filteredEdges } = applyFilters(nodes, edges);

  const nodeById = new Map(filteredNodes.map(n => [n.person_id, n]));
  const graphNodes = filteredNodes.map(n => ({ ...n }));
  const graphEdges = filteredEdges
    .filter(e => nodeById.has(e.source) && nodeById.has(e.target))
    .map(e => {
      const vis = visibleLayers(e);
      const primary = primaryVisibleLayer(vis);
      return { ...e, _visibleLayers: vis, _primaryLayer: primary };
    });

  // Compute neighbor map for focus mode.
  const neighborMap = new Map();
  for (const n of graphNodes) neighborMap.set(n.person_id, new Set([n.person_id]));
  for (const e of graphEdges) {
    neighborMap.get(e.source)?.add(e.target);
    neighborMap.get(e.target)?.add(e.source);
  }

  const q = normSearch(filterState.search);
  const searchHits = new Set(
    q ? graphNodes.filter(n => nodeMatchesSearch(n, q)).map(n => n.person_id) : []
  );

  function focusedSet() {
    if (!filterState.focusOnSelected || selectedPersonId == null) return null;
    return neighborMap.get(selectedPersonId) || new Set([selectedPersonId]);
  }

  // Single <g> that holds everything so zoom/pan transforms it as one.
  zoomRoot = svg.append('g').attr('class', 'zoomRoot');

  // Order edges so derived layers (shared_membership / co_residence) render
  // on top of explicit relationships when they are the primary layer.
  const layerOrder = { relationship: 0, co_residence: 1, shared_membership: 2 };
  const orderedEdges = graphEdges.slice().sort((a, b) => {
    const ra = layerOrder[a._primaryLayer?.kind] ?? 0;
    const rb = layerOrder[b._primaryLayer?.kind] ?? 0;
    return ra - rb;
  });

  const link = zoomRoot.append('g')
    .attr('stroke-opacity', 0.7)
    .selectAll('line')
    .data(orderedEdges)
    .join('line')
    .attr('stroke', d => edgeStrokeColor(d._primaryLayer))
    .attr('stroke-width', d => edgeStrokeWidth(d._primaryLayer))
    .attr('stroke-opacity', d => d._primaryLayer?.kind === 'relationship' ? null : 1)
    .attr('stroke-dasharray', d => edgeDashArray(d._primaryLayer))
    .on('click', (evt, d) => {
      evt.stopPropagation();
      selectEdge(edgeKey(d));
    })
    .on('mouseover', function (_evt, d) {
      const key = edgeKey(d);
      edgeLabels.filter(l => edgeKey(l) === key)
        .classed('hovered', true)
        .style('display', null);
    })
    .on('mouseout', function (_evt, d) {
      const key = edgeKey(d);
      edgeLabels.filter(l => edgeKey(l) === key)
        .classed('hovered', false)
        .style('display', 'none');
    });

  // Edge labels (hidden until hover). Show every visible layer joined by ' · '.
  const edgeLabels = zoomRoot.append('g')
    .selectAll('text.edgeLabel')
    .data(graphEdges)
    .join('text')
    .attr('class', 'edgeLabel')
    .attr('text-anchor', 'middle')
    .attr('dy', -4)
    .style('display', 'none')
    .text(d => (d._visibleLayers || []).map(layerLabel).join('  ·  '));

  // Small badge near midpoint when an edge bundles more than one visible layer.
  const edgeBadges = zoomRoot.append('g')
    .selectAll('text.edgeBadge')
    .data(graphEdges.filter(d => (d._visibleLayers || []).length > 1))
    .join('text')
    .attr('class', 'edgeBadge')
    .attr('text-anchor', 'middle')
    .attr('dy', 4)
    .attr('fill', '#cfd6ff')
    .attr('font-size', 10)
    .style('pointer-events', 'none')
    .text(d => `·${d._visibleLayers.length}`);

  const node = zoomRoot.append('g')
    .selectAll('circle')
    .data(graphNodes)
    .join('circle')
    .attr('r', d => (d.person_id === selectedPersonId ? 9 : (searchHits.has(d.person_id) ? 8 : 6)))
    .attr('fill', d => {
      if (searchHits.has(d.person_id)) return '#ffd24a';
      return stanceColor(d.stance_code);
    })
    .attr('stroke', d => d.person_id === selectedPersonId ? '#4f7cff' : '#2a2f3a')
    .attr('stroke-width', d => d.person_id === selectedPersonId ? 3 : 1)
    .call(d3.drag()
      .on('start', (event) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      })
      .on('drag', (event) => {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      })
      .on('end', (event) => {
        if (!event.active) sim.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      })
    )
    .on('click', (evt, d) => {
      evt.stopPropagation();
      selectPerson(d.person_id);
    })
    .on('mouseover', (_evt, d) => {
      labels.filter(l => l.person_id === d.person_id)
        .classed('hovered', true)
        .style('display', null);
    })
    .on('mouseout', (_evt, d) => {
      labels.filter(l => l.person_id === d.person_id)
        .classed('hovered', false)
        .style('display', function (l) {
          if (filterState.showAllLabels) return null;
          if (l.person_id === selectedPersonId) return null;
          if (searchHits.has(l.person_id)) return null;
          if (filterState.codedOnly && isPersonCoded(l)) return null;
          const focus = focusedSet();
          if (focus && focus.has(l.person_id)) return null;
          return 'none';
        });
    });

  node.append('title').text(d => d.name);

  // Labels: show for selected, search hits, coded people when "codedOnly" is on,
  // and everyone when "showAllLabels" is checked.
  const labels = zoomRoot.append('g')
    .selectAll('text.nodeLabel')
    .data(graphNodes)
    .join('text')
    .attr('class', 'nodeLabel')
    .attr('dx', 10)
    .attr('dy', 4)
    .text(d => d.name)
    .style('display', d => {
      if (filterState.showAllLabels) return null;
      if (d.person_id === selectedPersonId) return null;
      if (searchHits.has(d.person_id)) return null;
      if (filterState.codedOnly && isPersonCoded(d)) return null;
      // In focus mode, label the focused person + neighbors.
      const focus = focusedSet();
      if (focus && focus.has(d.person_id)) return null;
      return 'none';
    });

  // Apply dimming for focus mode + search.
  function applyDimming() {
    const focus = focusedSet();
    node.classed('dimmed', d => {
      if (focus && !focus.has(d.person_id)) return true;
      if (q && !searchHits.has(d.person_id) && !(focus && focus.has(d.person_id))) return true;
      return false;
    });
    link.classed('dimmed', d => {
      if (focus && !(focus.has(d.source.person_id ?? d.source) && focus.has(d.target.person_id ?? d.target))) return true;
      return false;
    });
  }
  applyDimming();

  sim = d3.forceSimulation(graphNodes)
    .force('link', d3.forceLink(graphEdges).id(d => d.person_id).distance(90))
    .force('charge', d3.forceManyBody().strength(-240))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(14))
    .on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      edgeLabels
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2);

      edgeBadges
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2);

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      labels
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

  // Background click clears selection
  svg.on('click', () => {
    selectedPersonId = null;
    selectedEdgeId = null;
    render();
  });

  // Zoom & pan (mouse wheel + drag on empty space).
  zoomBehavior = d3.zoom()
    .scaleExtent([0.1, 8])
    .filter((event) => {
      // Allow wheel always; allow drag-pan only when starting on empty SVG background,
      // so node-drag (which uses pointerdown on circles) still works.
      if (event.type === 'wheel') return true;
      return event.target === svg.node();
    })
    .on('zoom', (event) => {
      zoomRoot.attr('transform', event.transform);
    });
  svg.call(zoomBehavior).on('dblclick.zoom', null);

  // If there's a search query with hits, gently pan/zoom to fit them.
  if (q && searchHits.size > 0) {
    // Wait for simulation to settle a tick or two, then fit to hits.
    setTimeout(() => fitToNodes(graphNodes.filter(n => searchHits.has(n.person_id))), 400);
  }
}

// Fit the current graph to the viewport.
function fitNetwork() {
  if (!zoomRoot || !zoomBehavior) return;
  const { width, height } = svgSize();
  const bbox = zoomRoot.node().getBBox();
  if (!bbox.width || !bbox.height) return;
  const pad = 24;
  const scale = Math.min(
    (width - pad * 2) / bbox.width,
    (height - pad * 2) / bbox.height,
    4
  );
  const tx = (width - bbox.width * scale) / 2 - bbox.x * scale;
  const ty = (height - bbox.height * scale) / 2 - bbox.y * scale;
  svg.transition().duration(400).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(tx, ty).scale(scale)
  );
}

// Fit to a subset of nodes (used after a search hit).
function fitToNodes(subset) {
  if (!zoomRoot || !zoomBehavior || !subset || subset.length === 0) return;
  const { width, height } = svgSize();
  const xs = subset.map(n => n.x).filter(v => Number.isFinite(v));
  const ys = subset.map(n => n.y).filter(v => Number.isFinite(v));
  if (xs.length === 0 || ys.length === 0) return;
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const bw = Math.max(40, maxX - minX);
  const bh = Math.max(40, maxY - minY);
  const pad = 120;
  const scale = Math.min((width - pad * 2) / bw, (height - pad * 2) / bh, 2.5);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const tx = width / 2 - cx * scale;
  const ty = height / 2 - cy * scale;
  svg.transition().duration(400).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(tx, ty).scale(scale)
  );
}

// --- Details ---
function escapeHtml(str) {
  return String(str ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderDetails() {
  if (!state) {
    detailsEl.innerHTML = '<div class="muted">No data loaded.</div>';
    return;
  }

  const sourcesById = new Map((state.sources || []).map(s => [s.source_id, s]));

  if (selectedPersonId != null) {
    const p = state.nodes.find(n => n.person_id === selectedPersonId);
    if (!p) return;

    const place = p.map_place;
    const src = p.stance_source_id ? sourcesById.get(p.stance_source_id) : null;

    detailsEl.innerHTML = `
      <div class="kv">
        <div class="k">Person</div><div>${escapeHtml(p.name)}</div>
        <div class="k">Issue</div><div>${escapeHtml(state.issue)}</div>
        <div class="k">Year</div><div>${state.year === 0 ? 'All years' : escapeHtml(state.year)}</div>
        <div class="k">Map place</div><div>${place ? escapeHtml(place.place_name) : '<span class="muted">(none)</span>'}</div>
        <div class="k">Label</div><div>${p.position_label_code ? escapeHtml(p.position_label_code) : '<span class="muted">(no coded position)</span>'}</div>
      </div>
      <div class="kv">
        <div class="k">Stance</div>
        <div>${p.stance_code ? `<span class="stancePill stance-${escapeHtml(p.stance_code)}">${escapeHtml(p.stance_code)}</span>` : '<span class="muted">(no row at this year)</span>'}</div>
      </div>
      <hr/>
      <div class="muted">Notes / evidence</div>
      <div style="margin-top:6px">${p.position_notes ? escapeHtml(p.position_notes) : '<span class="muted">(none)</span>'}</div>
      ${src ? `
        <hr/>
        <div class="muted">Primary source</div>
        <div style="margin-top:6px">${escapeHtml(src.citation_full || src.title || '')}</div>
        ${src.url ? `<div style="margin-top:6px"><a href="${escapeHtml(src.url)}" target="_blank" rel="noopener">Source link</a></div>` : ''}
      ` : ''}
    `;
    return;
  }

  if (selectedEdgeId != null) {
    const e = state.edges.find(x => edgeKey(x) === selectedEdgeId);
    if (!e) return;

    const source = state.nodes.find(n => n.person_id === e.source);
    const target = state.nodes.find(n => n.person_id === e.target);
    const vis = visibleLayers(e);

    const layerBlocks = vis.map(layer => {
      const lsrc = layer.source_id ? sourcesById.get(layer.source_id) : null;
      if (layer.kind === 'relationship') {
        return `
          <div class="layerBlock">
            <div class="layerHeader">Relationship · ${escapeHtml(layer.relationship_type_code || '')}</div>
            <div class="kv">
              <div class="k">Alignment</div><div>${escapeHtml(layer.alignment_status_code || '(none)')}</div>
              <div class="k">Strength</div><div>${layer.strength ?? '<span class="muted">—</span>'}</div>
            </div>
            <div class="muted" style="margin-top:6px">Evidence</div>
            <div style="margin-top:4px">${layer.justification_note ? escapeHtml(layer.justification_note) : '<span class="muted">(baseline; no issue-specific characterization active)</span>'}</div>
            ${lsrc ? `<div style="margin-top:6px" class="muted">Citation: ${escapeHtml(lsrc.citation_full || lsrc.title || '')}</div>` : ''}
          </div>`;
      }
      if (layer.kind === 'shared_membership') {
        return `
          <div class="layerBlock">
            <div class="layerHeader">Shared membership${layer.count > 1 ? ` · ${layer.count} orgs` : ''}</div>
            <div style="margin-top:4px">${escapeHtml(layer.orgs || '')}</div>
          </div>`;
      }
      if (layer.kind === 'co_residence') {
        const places = (layer.places || []).map(p => escapeHtml(p.place_name)).join(', ') || escapeHtml(layer.place_name || '');
        return `
          <div class="layerBlock">
            <div class="layerHeader">Co-residence${layer.count > 1 ? ` · ${layer.count} places` : ''}</div>
            <div style="margin-top:4px">${places}</div>
          </div>`;
      }
      return '';
    }).join('');

    detailsEl.innerHTML = `
      <div class="kv">
        <div class="k">Edge</div><div>${escapeHtml(source?.name)}  ↔  ${escapeHtml(target?.name)}</div>
        <div class="k">Issue</div><div>${escapeHtml(state.issue)}</div>
        <div class="k">Year</div><div>${state.year === 0 ? 'All years' : escapeHtml(state.year)}</div>
        <div class="k">Layers</div><div>${vis.length} visible${e.layers && e.layers.length !== vis.length ? ` <span class="muted">(${e.layers.length - vis.length} hidden by filters)</span>` : ''}</div>
      </div>
      <hr/>
      ${layerBlocks || '<div class="muted">(no visible layers)</div>'}
    `;
    return;
  }

  detailsEl.innerHTML = '<div class="muted">Click a person or edge.</div>';
}

function selectPerson(personId) {
  selectedPersonId = personId;
  selectedEdgeId = null;
  render();
}

function selectEdge(edgeId) {
  selectedEdgeId = edgeId;
  selectedPersonId = null;
  render();
}

// --- Data fetch ---
async function loadMeta() {
  const res = await fetch('/api/meta');
  if (!res.ok) throw new Error('Failed to load meta');
  meta = await res.json();

  // Populate issues
  issueSelect.innerHTML = '';
  for (const it of meta.issues) {
    const opt = document.createElement('option');
    opt.value = it.code;
    opt.textContent = it.label;
    issueSelect.appendChild(opt);
  }
  issueSelect.value = 'nullification';

  // Populate scales
  for (const it of meta.scales) {
    const opt = document.createElement('option');
    opt.value = it.code;
    opt.textContent = it.label;
    scaleSelect.appendChild(opt);
  }
}

async function loadState() {
  const year = filterState.allYears ? 0 : parseInt(yearInput.value, 10);
  const issue = issueSelect.value;
  const scale = scaleSelect.value;

  const params = new URLSearchParams({ year: String(year), issue });
  if (scale) params.set('scale', scale);

  const res = await fetch(`/api/state?${params.toString()}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || 'Failed to load state');
  }
  state = await res.json();
}

function render() {
  if (!state) return;
  // Keep the year inputs in sync with the response unless we're in all-years mode,
  // in which case the server echoes year=0 (sentinel) and the inputs stay disabled.
  if (!filterState.allYears) {
    yearInput.value = String(state.year);
    yearLabel.value = String(state.year);
  }

  renderMap(state.nodes);
  renderNetwork(state.nodes, state.edges);
  renderDetails();
}

function wireControls() {
  // Slider drives the number input live; commit triggers refresh.
  yearInput.addEventListener('input', () => {
    yearLabel.value = yearInput.value;
  });
  // Number input drives the slider live; commit (Enter/blur) triggers refresh.
  yearLabel.addEventListener('input', () => {
    const v = parseInt(yearLabel.value, 10);
    if (!Number.isNaN(v)) yearInput.value = String(v);
  });

  const refresh = async () => {
    await loadState();
    render();
  };

  yearInput.addEventListener('change', refresh);
  yearLabel.addEventListener('change', refresh);
  issueSelect.addEventListener('change', refresh);
  scaleSelect.addEventListener('change', refresh);

  window.addEventListener('resize', () => {
    render();
  });

  const fitBtn = document.getElementById('networkFit');
  if (fitBtn) fitBtn.addEventListener('click', fitNetwork);

  // Filter / display controls
  const searchInput = document.getElementById('search');
  if (searchInput) {
    let t = null;
    searchInput.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => {
        filterState.search = searchInput.value;
        render();
      }, 150);
    });
  }
  const codedCb = document.getElementById('filterCoded');
  if (codedCb) codedCb.addEventListener('change', () => {
    filterState.codedOnly = codedCb.checked;
    render();
  });
  const hideComCb = document.getElementById('filterHideCoMentions');
  if (hideComCb) {
    filterState.hideCoMentions = hideComCb.checked;
    hideComCb.addEventListener('change', () => {
      filterState.hideCoMentions = hideComCb.checked;
      render();
    });
  }
  const focusCb = document.getElementById('filterFocus');
  if (focusCb) {
    filterState.focusOnSelected = focusCb.checked;
    focusCb.addEventListener('change', () => {
      filterState.focusOnSelected = focusCb.checked;
      render();
    });
  }
  const labelsCb = document.getElementById('showLabels');
  if (labelsCb) labelsCb.addEventListener('change', () => {
    filterState.showAllLabels = labelsCb.checked;
    render();
  });

  // All-years toggle: disables the year inputs and sends year=0 sentinel.
  const allYearsCb = document.getElementById('allYears');
  if (allYearsCb) {
    const syncYearDisabled = () => {
      yearInput.disabled = filterState.allYears;
      yearLabel.disabled = filterState.allYears;
      yearInput.style.opacity = filterState.allYears ? '0.4' : '';
      yearLabel.style.opacity = filterState.allYears ? '0.4' : '';
    };
    filterState.allYears = allYearsCb.checked;
    syncYearDisabled();
    allYearsCb.addEventListener('change', async () => {
      filterState.allYears = allYearsCb.checked;
      syncYearDisabled();
      await loadState();
      render();
    });
  }

  // Layer toggles.
  const layerRel = document.getElementById('layerRelationship');
  if (layerRel) {
    filterState.layerRelationship = layerRel.checked;
    layerRel.addEventListener('change', () => {
      filterState.layerRelationship = layerRel.checked;
      render();
    });
  }
  const layerCo = document.getElementById('layerCoResidence');
  if (layerCo) {
    filterState.layerCoResidence = layerCo.checked;
    layerCo.addEventListener('change', () => {
      filterState.layerCoResidence = layerCo.checked;
      render();
    });
  }
  const layerSm = document.getElementById('layerSharedMembership');
  if (layerSm) {
    filterState.layerSharedMembership = layerSm.checked;
    layerSm.addEventListener('change', () => {
      filterState.layerSharedMembership = layerSm.checked;
      render();
    });
  }

  const expandBtn = document.getElementById('networkExpand');
  const networkPanel = document.getElementById('networkPanel');
  if (expandBtn && networkPanel) {
    expandBtn.addEventListener('click', () => {
      const expanded = networkPanel.classList.toggle('expanded');
      expandBtn.textContent = expanded ? 'Collapse' : 'Expand';
      expandBtn.classList.toggle('active', expanded);
      // Re-render at the new size so the simulation uses the larger viewport.
      render();
      // After layout settles, fit to the new viewport.
      setTimeout(fitNetwork, 350);
    });
    // Allow Escape to collapse when expanded.
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && networkPanel.classList.contains('expanded')) {
        expandBtn.click();
      }
    });
  }
}

(async function main() {
  initMap();
  await loadMeta();
  wireControls();
  await loadState();
  render();
})();
