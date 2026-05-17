// Unionism Network — People Workbench
// Single-page CRUD for people: browse, search, create (with live dedupe),
// edit, delete (with cascade confirmation), inline alias add/remove.
// Positions / relationships are read-only here for Phase 1; add forms come later.

const statusEl = document.getElementById('status');
const listEl = document.getElementById('peopleList');
const listMeta = document.getElementById('listMeta');
const listSearch = document.getElementById('listSearch');
const filterCoded = document.getElementById('filterCoded');
const filterConnected = document.getElementById('filterConnected');
const newPersonBtn = document.getElementById('newPersonBtn');

const editorEmpty = document.getElementById('editorEmpty');
const editorContent = document.getElementById('editorContent');
const editorPersonName = document.getElementById('editorPersonName');
const editorPersonId = document.getElementById('editorPersonId');

const bioForm = document.getElementById('bioForm');
const bioDirtyFlag = document.getElementById('bioDirtyFlag');
const resetBioBtn = document.getElementById('resetBioBtn');
const dupeInline = document.getElementById('dupeInline');
const dupeInlineList = document.getElementById('dupeInlineList');

const aliasList = document.getElementById('aliasList');
const aliasCountEl = document.getElementById('aliasCount');
const aliasAddForm = document.getElementById('aliasAddForm');

const positionList = document.getElementById('positionList');
const positionCountEl = document.getElementById('positionCount');
const relationshipList = document.getElementById('relationshipList');
const relationshipCountEl = document.getElementById('relationshipCount');

const deleteBtn = document.getElementById('deleteBtn');
const deleteDialog = document.getElementById('deleteDialog');
const deleteWho = document.getElementById('deleteWho');
const deleteCounts = document.getElementById('deleteCounts');
const deleteCancel = document.getElementById('deleteCancel');
const deleteCancelX = document.getElementById('deleteCancelX');
const deleteConfirm = document.getElementById('deleteConfirm');
const findDupesBtn = document.getElementById('findDupesBtn');
const dbStatusEl = document.getElementById('dbStatus');

let people = [];
let lookups = {};
let selectedPerson = null;  // full record from GET /api/people/{id}
let creating = false;       // true after clicking "+ New person", no id yet
let bioInitial = {};        // snapshot for revert + dirty detection
let listSearchTerm = '';
let forceCreateNext = false;

function setStatus(msg, kind) {
  statusEl.textContent = msg || '';
  statusEl.classList.remove('ok', 'err');
  if (kind) statusEl.classList.add(kind);
  if (kind === 'ok') {
    setTimeout(() => { if (statusEl.classList.contains('ok')) setStatus(''); }, 3500);
  }
}

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let body = null, detail = res.statusText;
    try {
      body = await res.json();
      detail = (body && body.detail && body.detail.message) || body.detail || detail;
    } catch (_) {}
    const err = new Error(`${res.status} ${detail}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return res.json();
}

function escapeHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

// ---- Lookups ----

function populateLookupSelects() {
  document.querySelectorAll('select[data-lookup]').forEach(sel => {
    const key = sel.getAttribute('data-lookup');
    const items = lookups[key] || [];
    const cur = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    for (const it of items) {
      const o = document.createElement('option');
      o.value = it.code;
      o.textContent = `${it.label} (${it.code})`;
      sel.appendChild(o);
    }
    if (cur) sel.value = cur;
  });
}

// ---- People list ----

function lifeSpan(p) {
  const b = p.birth_year, d = p.death_year;
  if (!b && !d) return '';
  return `(${b || '?'}–${d || '?'})`;
}

function renderList() {
  const q = listSearchTerm.trim().toLowerCase();
  const wantCoded = filterCoded.checked;
  const wantConnected = filterConnected.checked;

  const filtered = people.filter(p => {
    if (wantCoded && (!p.position_count || p.position_count === 0)) return false;
    if (wantConnected && (!p.relationship_count || p.relationship_count === 0)) return false;
    if (!q) return true;
    const hay = [p.full_name, p.display_name, p.occupation].filter(Boolean).join(' ').toLowerCase();
    return hay.includes(q);
  });

  listMeta.textContent = `Showing ${filtered.length} of ${people.length} people`;
  listEl.innerHTML = '';

  for (const p of filtered) {
    const row = document.createElement('div');
    row.className = 'listRow';
    row.dataset.personId = p.person_id;
    if (selectedPerson && selectedPerson.person_id === p.person_id) row.classList.add('selected');
    const name = p.display_name || p.full_name || '(unnamed)';
    const meta = [
      `id ${p.person_id}`,
      lifeSpan(p),
      p.occupation,
      p.home_region_sc_code,
    ].filter(Boolean).join(' · ');
    const badges = [];
    if (p.position_count > 0) badges.push(`<span class="rowBadge">${p.position_count} pos</span>`);
    if (p.relationship_count > 0) badges.push(`<span class="rowBadge">${p.relationship_count} rel</span>`);
    if (p.alias_count > 0) badges.push(`<span class="rowBadge">${p.alias_count} alias</span>`);
    row.innerHTML = `
      <div class="rowName">${escapeHtml(name)}</div>
      <div class="rowMeta">${escapeHtml(meta)} ${badges.join(' ')}</div>
    `;
    row.addEventListener('click', () => selectPerson(p.person_id));
    listEl.appendChild(row);
  }
}

async function loadList() {
  people = await fetchJSON('/api/people');
  renderList();
  dbStatusEl.textContent = `${people.length} people loaded`;
}

// ---- Editor: bio ----

function showEmpty() {
  selectedPerson = null;
  creating = false;
  editorContent.classList.add('hidden');
  editorEmpty.classList.remove('hidden');
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
}

function showEditor() {
  editorContent.classList.remove('hidden');
  editorEmpty.classList.add('hidden');
}

function fillBioForm(p) {
  for (const el of bioForm.elements) {
    if (!el.name) continue;
    if (el.type === 'checkbox') {
      el.checked = Boolean(p[el.name]);
    } else if (p[el.name] != null) {
      el.value = p[el.name];
    } else {
      el.value = '';
    }
  }
  bioInitial = snapshotBio();
  setDirty(false);
}

function snapshotBio() {
  const obj = {};
  for (const el of bioForm.elements) {
    if (!el.name) continue;
    if (el.type === 'checkbox') {
      obj[el.name] = el.checked ? 1 : 0;
    } else {
      obj[el.name] = el.value;
    }
  }
  return obj;
}

function bioBodyForSubmit() {
  const obj = snapshotBio();
  for (const k of Object.keys(obj)) {
    if (obj[k] === '') delete obj[k];
  }
  for (const numField of ['birth_year', 'death_year']) {
    if (obj[numField] != null) {
      const n = Number(obj[numField]);
      if (!Number.isNaN(n)) obj[numField] = n;
    }
  }
  return obj;
}

function setDirty(isDirty) {
  bioDirtyFlag.textContent = isDirty ? 'Unsaved changes' : '';
}

bioForm.addEventListener('input', () => {
  const cur = snapshotBio();
  const dirty = Object.keys(cur).some(k => String(cur[k]) !== String(bioInitial[k] ?? ''));
  setDirty(dirty);
  if (creating) scheduleDupeCheck();
  forceCreateNext = false; // any edit resets the force-create state
});

resetBioBtn.addEventListener('click', () => {
  if (creating) {
    bioForm.reset();
    bioInitial = snapshotBio();
    setDirty(false);
    dupeInline.classList.add('hidden');
  } else if (selectedPerson) {
    fillBioForm(selectedPerson);
  }
});

// ---- Live dedupe (only while creating) ----

let dupeTimer = null;
function scheduleDupeCheck() {
  clearTimeout(dupeTimer);
  dupeTimer = setTimeout(runDupeCheck, 300);
}

async function runDupeCheck() {
  const body = bioBodyForSubmit();
  if (!body.full_name && !body.display_name) {
    dupeInline.classList.add('hidden');
    return;
  }
  try {
    const res = await fetchJSON('/api/people/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    renderInlineDupes(res.candidates || []);
  } catch (_) {
    /* silent */
  }
}

function renderInlineDupes(cands) {
  if (!cands.length) {
    dupeInline.classList.add('hidden');
    dupeInlineList.innerHTML = '';
    return;
  }
  dupeInline.classList.remove('hidden');
  dupeInlineList.innerHTML = cands.map(c => {
    const name = c.display_name || c.full_name || '(unnamed)';
    const years = lifeSpan(c);
    const match = c.match_kind === 'alias'
      ? `via alias "${escapeHtml(c.matched_on || '')}"`
      : `via ${escapeHtml(c.matched_on || 'name')}`;
    return `
      <div class="dupeCandRow">
        <span>${escapeHtml(name)} ${escapeHtml(years)} <span class="muted">— ${match}, id ${c.person_id}</span></span>
        <button type="button" class="smallBtn" data-pick="${c.person_id}">Use this one</button>
      </div>
    `;
  }).join('');
  dupeInlineList.querySelectorAll('button[data-pick]').forEach(b => {
    b.addEventListener('click', () => selectPerson(Number(b.dataset.pick)));
  });
}

// ---- Bio save ----

bioForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const body = bioBodyForSubmit();
  if (!body.full_name && !body.display_name) {
    setStatus('Full name or display name is required.', 'err');
    return;
  }
  try {
    if (creating) {
      let res;
      try {
        const url = forceCreateNext ? '/api/people?force=true' : '/api/people';
        res = await fetchJSON(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
      } catch (e) {
        if (e.status === 409) {
          const cands = (e.body && e.body.detail && e.body.detail.candidates) || [];
          renderInlineDupes(cands);
          setStatus('Possible duplicates above. Pick one, edit the name, or click Save again to create anyway.', 'err');
          forceCreateNext = true;
          return;
        }
        throw e;
      }
      forceCreateNext = false;
      setStatus(`Created person ${res.person_id}: ${res.display_name || res.full_name}`, 'ok');
      await loadList();
      await selectPerson(res.person_id);
    } else if (selectedPerson) {
      const res = await fetchJSON(`/api/people/${selectedPerson.person_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus(`Saved person ${res.person_id}.`, 'ok');
      await loadList();
      await selectPerson(res.person_id);
    }
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
  }
});

// ---- Selection ----

newPersonBtn.addEventListener('click', () => {
  creating = true;
  selectedPerson = null;
  forceCreateNext = false;
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
  editorPersonName.textContent = 'New person';
  editorPersonId.textContent = '(unsaved)';
  bioForm.reset();
  bioInitial = snapshotBio();
  setDirty(false);
  dupeInline.classList.add('hidden');
  aliasList.innerHTML = '<div class="muted">Save the person first to add aliases.</div>';
  aliasCountEl.textContent = '(0)';
  positionList.innerHTML = '<div class="muted">Save the person first to add positions.</div>';
  positionCountEl.textContent = '(0)';
  relationshipList.innerHTML = '<div class="muted">Save the person first to add relationships.</div>';
  relationshipCountEl.textContent = '(0)';
  showEditor();
  bioForm.querySelector('input[name="full_name"]').focus();
});

async function selectPerson(personId) {
  try {
    const p = await fetchJSON(`/api/people/${personId}`);
    creating = false;
    forceCreateNext = false;
    selectedPerson = p;
    editorPersonName.textContent = p.display_name || p.full_name || '(unnamed)';
    editorPersonId.textContent = `id ${p.person_id}`;
    fillBioForm(p);
    dupeInline.classList.add('hidden');
    renderAliases(p.aliases || []);
    renderPositions(p.positions || []);
    renderRelationships(p.relationships || []);
    document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
    const row = listEl.querySelector(`.listRow[data-person-id="${personId}"]`);
    if (row) {
      row.classList.add('selected');
      row.scrollIntoView({ block: 'nearest' });
    }
    showEditor();
  } catch (e) {
    setStatus(`Load failed: ${e.message}`, 'err');
  }
}

// ---- Aliases ----

function renderAliases(aliases) {
  aliasCountEl.textContent = `(${aliases.length})`;
  if (!aliases.length) {
    aliasList.innerHTML = '<div class="muted">No aliases yet.</div>';
    return;
  }
  aliasList.innerHTML = aliases.map(a => `
    <div class="rowItem" data-alias-id="${a.alias_id}">
      <div class="rowItemMain">${escapeHtml(a.alias_name)} <span class="rowItemMeta">id ${a.alias_id}</span></div>
    </div>
  `).join('');
}

aliasAddForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  if (!selectedPerson) return;
  const fd = new FormData(aliasAddForm);
  const alias_name = String(fd.get('alias_name') || '').trim();
  if (!alias_name) return;
  try {
    await fetchJSON('/api/aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person_id: selectedPerson.person_id, alias_name }),
    });
    aliasAddForm.reset();
    setStatus('Alias added.', 'ok');
    await selectPerson(selectedPerson.person_id);
    await loadList();
  } catch (e) {
    setStatus(`Add alias failed: ${e.message}`, 'err');
  }
});

// ---- Positions (read-only Phase 1) ----

function renderPositions(positions) {
  positionCountEl.textContent = `(${positions.length})`;
  if (!positions.length) {
    positionList.innerHTML = '<div class="muted">No positions yet.</div>';
    return;
  }
  positionList.innerHTML = positions.map(po => `
    <div class="rowItem">
      <div class="rowItemMain">
        <strong>${escapeHtml(po.position_label_code || '')}</strong>
        on ${escapeHtml(po.issue_category_code || '')}
        <span class="rowItemMeta">
          ${escapeHtml(po.date_start || '')}${po.date_end ? '–' + escapeHtml(po.date_end) : ''}
          · scale ${escapeHtml(po.scale_level_code || '')}
          · src ${po.source_id || ''}
        </span>
      </div>
    </div>
  `).join('');
}

// ---- Relationships (read-only Phase 1) ----

function renderRelationships(rels) {
  relationshipCountEl.textContent = `(${rels.length})`;
  if (!rels.length) {
    relationshipList.innerHTML = '<div class="muted">No relationships yet.</div>';
    return;
  }
  relationshipList.innerHTML = rels.map(r => {
    const other = r.other_person_name || `id ${r.other_person_id}`;
    return `
      <div class="rowItem">
        <div class="rowItemMain">
          ↔ <strong>${escapeHtml(other)}</strong>
          <span class="rowItemMeta">
            ${escapeHtml(r.relationship_type_code || '')}
            ${r.alignment_status_code ? ' · ' + escapeHtml(r.alignment_status_code) : ''}
            ${r.start_date ? ' · ' + escapeHtml(r.start_date) : ''}${r.end_date ? '–' + escapeHtml(r.end_date) : ''}
            ${r.strength != null ? ' · strength ' + r.strength : ''}
          </span>
        </div>
      </div>
    `;
  }).join('');
}

// ---- Delete person ----

deleteBtn.addEventListener('click', async () => {
  if (!selectedPerson) return;
  try {
    const counts = await fetchJSON(`/api/people/${selectedPerson.person_id}/dependents`);
    deleteWho.textContent = `${selectedPerson.display_name || selectedPerson.full_name} (id ${selectedPerson.person_id})`;
    deleteCounts.innerHTML = [
      `${counts.aliases} alias(es)`,
      `${counts.positions} position(s)`,
      `${counts.relationships} relationship(s)`,
      `${counts.organization_memberships} organization membership(s)`,
      `${counts.residences} residence(s)`,
    ].map(s => `<li>${s}</li>`).join('');
    deleteDialog.classList.remove('hidden');
  } catch (e) {
    setStatus(`Could not fetch dependents: ${e.message}`, 'err');
  }
});

function closeDeleteDialog() { deleteDialog.classList.add('hidden'); }
deleteCancel.addEventListener('click', closeDeleteDialog);
deleteCancelX.addEventListener('click', closeDeleteDialog);

deleteConfirm.addEventListener('click', async () => {
  if (!selectedPerson) return;
  const pid = selectedPerson.person_id;
  try {
    await fetchJSON(`/api/people/${pid}`, { method: 'DELETE' });
    closeDeleteDialog();
    setStatus(`Deleted person ${pid}.`, 'ok');
    showEmpty();
    await loadList();
  } catch (e) {
    setStatus(`Delete failed: ${e.message}`, 'err');
  }
});

// ---- Find duplicates manually ----

findDupesBtn.addEventListener('click', async () => {
  if (!selectedPerson) return;
  try {
    const res = await fetchJSON('/api/people/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: selectedPerson.full_name,
        display_name: selectedPerson.display_name,
        birth_year: selectedPerson.birth_year,
        death_year: selectedPerson.death_year,
      }),
    });
    const cands = (res.candidates || []).filter(c => c.person_id !== selectedPerson.person_id);
    if (!cands.length) {
      setStatus('No duplicates found.', 'ok');
      dupeInline.classList.add('hidden');
      return;
    }
    renderInlineDupes(cands);
    dupeInline.classList.remove('hidden');
    setStatus(`Found ${cands.length} possible duplicate(s).`, 'ok');
  } catch (e) {
    setStatus(`Match failed: ${e.message}`, 'err');
  }
});

// ---- Search / filters ----

listSearch.addEventListener('input', () => {
  listSearchTerm = listSearch.value;
  renderList();
});
filterCoded.addEventListener('change', renderList);
filterConnected.addEventListener('change', renderList);

// ---- Init ----

(async function init() {
  try {
    lookups = await fetchJSON('/api/lookups');
    populateLookupSelects();
    await loadList();
    setStatus(`Ready. ${people.length} people loaded.`, 'ok');
  } catch (e) {
    setStatus(`Init failed: ${e.message}`, 'err');
  }
})();
