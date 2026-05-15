const yearInput = document.getElementById('year');
const yearLabel = document.getElementById('yearLabel');
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

function renderNetwork(nodes, edges) {
  const { width, height } = svgSize();
  svg.attr('viewBox', `0 0 ${width} ${height}`);
  svg.selectAll('*').remove();

  const nodeById = new Map(nodes.map(n => [n.person_id, n]));
  const graphNodes = nodes.map(n => ({ ...n }));
  const graphEdges = edges
    .filter(e => nodeById.has(e.source) && nodeById.has(e.target))
    .map(e => ({ ...e }));

  // Single <g> that holds everything so zoom/pan transforms it as one.
  zoomRoot = svg.append('g').attr('class', 'zoomRoot');

  const link = zoomRoot.append('g')
    .attr('stroke-opacity', 0.7)
    .selectAll('line')
    .data(graphEdges)
    .join('line')
    .attr('stroke', d => alignmentColor(d.alignment_status_code))
    .attr('stroke-width', d => (d.strength || 1) * 1.5)
    .on('click', (evt, d) => {
      evt.stopPropagation();
      selectEdge(d.relationship_id);
    });

  const node = zoomRoot.append('g')
    .selectAll('circle')
    .data(graphNodes)
    .join('circle')
    .attr('r', d => (d.person_id === selectedPersonId ? 9 : 6))
    .attr('fill', d => (d.person_id === selectedPersonId ? '#4f7cff' : '#e8e8ea'))
    .attr('stroke', '#2a2f3a')
    .attr('stroke-width', 1)
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
    });

  node.append('title').text(d => d.name);

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

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);
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
        <div class="k">Year</div><div>${escapeHtml(state.year)}</div>
        <div class="k">Map place</div><div>${place ? escapeHtml(place.place_name) : '<span class="muted">(none)</span>'}</div>
        <div class="k">Label</div><div>${p.position_label_code ? escapeHtml(p.position_label_code) : '<span class="muted">(no coded position)</span>'}</div>
      </div>
      <div class="kv">
        <div class="k">Union</div><div>${p.stance_on_union ?? '<span class="muted">—</span>'}</div>
        <div class="k">States’ rights</div><div>${p.stance_on_states_rights ?? '<span class="muted">—</span>'}</div>
        <div class="k">Slavery</div><div>${p.stance_on_slavery ?? '<span class="muted">—</span>'}</div>
        <div class="k">Secession</div><div>${p.stance_on_secession ?? '<span class="muted">—</span>'}</div>
      </div>
      <hr/>
      <div class="muted">Evidence</div>
      <div style="margin-top:6px">${p.stance_justification ? escapeHtml(p.stance_justification) : '<span class="muted">(none)</span>'}</div>
      ${src ? `
        <hr/>
        <div class="muted">Citation</div>
        <div style="margin-top:6px">${escapeHtml(src.citation_full || src.title || '')}</div>
        ${src.url ? `<div style="margin-top:6px"><a href="${escapeHtml(src.url)}" target="_blank" rel="noopener">Source link</a></div>` : ''}
      ` : ''}
    `;
    return;
  }

  if (selectedEdgeId != null) {
    const e = state.edges.find(x => x.relationship_id === selectedEdgeId);
    if (!e) return;

    const source = state.nodes.find(n => n.person_id === e.source);
    const target = state.nodes.find(n => n.person_id === e.target);
    const src = e.source_id ? sourcesById.get(e.source_id) : null;

    detailsEl.innerHTML = `
      <div class="kv">
        <div class="k">Edge</div><div>${escapeHtml(source?.name)}  ↔  ${escapeHtml(target?.name)}</div>
        <div class="k">Issue</div><div>${escapeHtml(state.issue)}</div>
        <div class="k">Year</div><div>${escapeHtml(state.year)}</div>
        <div class="k">Type</div><div>${escapeHtml(e.relationship_type_code)}</div>
        <div class="k">Alignment</div><div>${escapeHtml(e.alignment_status_code || '(none)')}</div>
        <div class="k">Strength</div><div>${e.strength ?? '<span class="muted">—</span>'}</div>
      </div>
      <hr/>
      <div class="muted">Evidence</div>
      <div style="margin-top:6px">${e.justification_note ? escapeHtml(e.justification_note) : '<span class="muted">(baseline relationship; no issue-specific characterization active)</span>'}</div>
      ${src ? `
        <hr/>
        <div class="muted">Citation</div>
        <div style="margin-top:6px">${escapeHtml(src.citation_full || src.title || '')}</div>
        ${src.url ? `<div style="margin-top:6px"><a href="${escapeHtml(src.url)}" target="_blank" rel="noopener">Source link</a></div>` : ''}
      ` : ''}
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
  const year = parseInt(yearInput.value, 10);
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
  yearLabel.textContent = String(state.year);

  renderMap(state.nodes);
  renderNetwork(state.nodes, state.edges);
  renderDetails();
}

function wireControls() {
  yearInput.addEventListener('input', async () => {
    yearLabel.textContent = yearInput.value;
  });

  const refresh = async () => {
    await loadState();
    render();
  };

  yearInput.addEventListener('change', refresh);
  issueSelect.addEventListener('change', refresh);
  scaleSelect.addEventListener('change', refresh);

  window.addEventListener('resize', () => {
    render();
  });

  const fitBtn = document.getElementById('networkFit');
  if (fitBtn) fitBtn.addEventListener('click', fitNetwork);

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
