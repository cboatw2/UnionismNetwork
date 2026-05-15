const countEl = document.getElementById('count');
const detailsEl = document.getElementById('details');

const svg = d3.select('#viz');
let selectedPersonId = null;
let people = [];
let sim = null;
let nodeSel = null;
let currentSize = { width: 0, height: 0 };

function escapeHtml(str) {
  return String(str ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function svgSize() {
  const rect = document.getElementById('viz').getBoundingClientRect();
  return { width: Math.max(200, rect.width), height: Math.max(200, rect.height) };
}

function renderDetails() {
  if (selectedPersonId == null) {
    detailsEl.innerHTML = '<div class="muted">Click a node.</div>';
    return;
  }

  const p = people.find(x => x.person_id === selectedPersonId);
  if (!p) {
    detailsEl.innerHTML = '<div class="muted">Person not found.</div>';
    return;
  }

  detailsEl.innerHTML = `
    <div class="kv">
      <div class="k">person_id</div><div>${escapeHtml(p.person_id)}</div>
      <div class="k">display</div><div>${escapeHtml(p.display_name || '(none)')}</div>
      <div class="k">full</div><div>${escapeHtml(p.full_name || '(none)')}</div>
      <div class="k">region</div><div>${escapeHtml(p.home_region_sc_code || '(none)')}</div>
    </div>
  `;
}

function updateSelectionStyles() {
  if (!nodeSel) return;
  nodeSel
    .attr('r', d => (d.person_id === selectedPersonId ? 9 : 5))
    .attr('fill', d => (d.person_id === selectedPersonId ? '#4f7cff' : '#e8e8ea'));
}

function initViz() {
  const { width, height } = svgSize();
  currentSize = { width, height };
  svg.attr('viewBox', `0 0 ${width} ${height}`);
  svg.selectAll('*').remove();

  const nodes = people.map(p => ({ ...p }));

  const g = svg.append('g');
  nodeSel = g
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', 5)
    .attr('fill', '#e8e8ea')
    .attr('stroke', '#2a2f3a')
    .attr('stroke-width', 1)
    .on('click', (evt, d) => {
      evt.stopPropagation();
      selectedPersonId = d.person_id;
      renderDetails();
      updateSelectionStyles();
    });

  nodeSel.append('title').text(d => d.display_name || d.full_name || String(d.person_id));

  const margin = 10;

  sim = d3.forceSimulation(nodes)
    .force('charge', d3.forceManyBody().strength(-16))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
    .force('collide', d3.forceCollide(8))
    .on('tick', () => {
      // Clamp to viewport so all nodes remain visible without any zooming.
      for (const d of nodes) {
        d.x = Math.max(margin, Math.min(currentSize.width - margin, d.x));
        d.y = Math.max(margin, Math.min(currentSize.height - margin, d.y));
      }
      nodeSel
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);
    });

  svg.on('click', () => {
    selectedPersonId = null;
    renderDetails();
    updateSelectionStyles();
  });

  updateSelectionStyles();

  // Keep sim from being garbage-collected too early in some browsers.
  window.__peopleSim = sim;
}

function resizeViz() {
  if (!sim) return;
  const { width, height } = svgSize();
  currentSize = { width, height };
  svg.attr('viewBox', `0 0 ${width} ${height}`);
  sim.force('center', d3.forceCenter(width / 2, height / 2));
  sim.force('x', d3.forceX(width / 2).strength(0.04));
  sim.force('y', d3.forceY(height / 2).strength(0.04));
  sim.alpha(0.25).restart();
}

async function loadPeople() {
  const res = await fetch('/api/meta');
  if (!res.ok) throw new Error(`Failed to load /api/meta (${res.status})`);
  const meta = await res.json();
  people = (meta.people || []).map(p => ({
    person_id: p.person_id,
    full_name: p.full_name,
    display_name: p.display_name,
    home_region_sc_code: p.home_region_sc_code,
  }));

  countEl.textContent = `${people.length} people`;
  renderDetails();
  initViz();
}

window.addEventListener('resize', () => {
  if (people.length) resizeViz();
});

loadPeople().catch(err => {
  console.error(err);
  countEl.textContent = 'Failed to load.';
  detailsEl.innerHTML = `<div class="muted">${escapeHtml(err.message)}</div>`;
});
