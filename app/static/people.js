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
const membershipList = document.getElementById('membershipList');
const membershipCountEl = document.getElementById('membershipCount');

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
  membershipList.innerHTML = '<div class="muted">Save the person first to add memberships.</div>';
  membershipCountEl.textContent = '(0)';
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
    renderMemberships(p.memberships || []);
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

// ---- Relationships (expandable, per-event timeline) ----

let expandedRelId = null;       // currently-expanded relationship_id
let allEvents = [];             // cached list for the char-dialog event picker
let pendingCharRelId = null;    // relationship the char dialog is targeting

function renderRelationships(rels) {
  relationshipCountEl.textContent = `(${rels.length})`;
  if (!rels.length) {
    relationshipList.innerHTML = '<div class="muted">No relationships yet.</div>';
    return;
  }
  relationshipList.innerHTML = rels.map(r => {
    const other = r.other_person_name || `id ${r.other_person_id}`;
    const align = r.alignment_status_code || '';
    return `
      <div class="rowItem relItem" data-rel-id="${r.relationship_id}">
        <div class="rowItemMain">
          ↔ <strong>${escapeHtml(other)}</strong>
          <span class="rowItemMeta">
            ${escapeHtml(r.relationship_type_code || '')}
            ${align ? ' · <span class="alignBadge ' + escapeHtml(align) + '">' + escapeHtml(align) + '</span>' : ''}
            ${r.start_date ? ' · ' + escapeHtml(r.start_date) : ''}${r.end_date ? '–' + escapeHtml(r.end_date) : ''}
            ${r.strength != null ? ' · strength ' + r.strength : ''}
          </span>
          <div class="relTimeline hidden" data-timeline-for="${r.relationship_id}"></div>
        </div>
        <div class="rowItemActions">
          <button type="button" class="smallBtn" data-action="add-char" data-rel-id="${r.relationship_id}">+ Char</button>
          <button type="button" class="smallBtn danger" data-action="delete-rel" data-rel-id="${r.relationship_id}">×</button>
        </div>
      </div>
    `;
  }).join('');

  relationshipList.querySelectorAll('.relItem').forEach(item => {
    item.addEventListener('click', (ev) => {
      // Ignore clicks on the action buttons themselves.
      if (ev.target.closest('button')) return;
      const relId = Number(item.dataset.relId);
      toggleTimeline(relId, item);
    });
  });
  relationshipList.querySelectorAll('button[data-action="add-char"]').forEach(b => {
    b.addEventListener('click', (ev) => {
      ev.stopPropagation();
      openCharDialog(Number(b.dataset.relId));
    });
  });
  relationshipList.querySelectorAll('button[data-action="delete-rel"]').forEach(b => {
    b.addEventListener('click', async (ev) => {
      ev.stopPropagation();
      const relId = Number(b.dataset.relId);
      if (!confirm('Delete this relationship and all its characterizations?')) return;
      try {
        await fetchJSON(`/api/relationships/${relId}`, { method: 'DELETE' });
        setStatus(`Deleted relationship ${relId}.`, 'ok');
        if (selectedPerson) await selectPerson(selectedPerson.person_id);
      } catch (e) {
        setStatus(`Delete failed: ${e.message}`, 'err');
      }
    });
  });

  // Re-expand the previously expanded relationship if still present.
  if (expandedRelId) {
    const item = relationshipList.querySelector(`.relItem[data-rel-id="${expandedRelId}"]`);
    if (item) toggleTimeline(expandedRelId, item, /*forceOpen=*/true);
  }
}

async function toggleTimeline(relId, itemEl, forceOpen) {
  const tl = itemEl.querySelector(`.relTimeline[data-timeline-for="${relId}"]`);
  if (!tl) return;
  if (!forceOpen && !tl.classList.contains('hidden') && expandedRelId === relId) {
    tl.classList.add('hidden');
    itemEl.classList.remove('expanded');
    expandedRelId = null;
    return;
  }
  // Collapse any other open one
  relationshipList.querySelectorAll('.relTimeline').forEach(el => el.classList.add('hidden'));
  relationshipList.querySelectorAll('.relItem').forEach(el => el.classList.remove('expanded'));

  try {
    const r = await fetchJSON(`/api/relationships/${relId}`);
    const chars = r.characterizations || [];
    if (!chars.length) {
      tl.innerHTML = '<div class="muted">No characterizations yet. Click "+ Char" to add one tied to an event.</div>';
    } else {
      tl.innerHTML = chars.map(c => {
        const dates = [c.date_start, c.date_end].filter(Boolean).join('–');
        const align = c.alignment_status_code || '';
        return `
          <div class="charRow" data-char-id="${c.relationship_characterization_id}">
            <span>
              <strong>${escapeHtml(c.event_name || '(no event)')}</strong>
              ${dates ? ' · ' + escapeHtml(dates) : ''} ·
              ${escapeHtml(c.issue_category_code || '')} ·
              <span class="alignBadge ${escapeHtml(align)}">${escapeHtml(align)}</span>
              ${c.justification_note ? ' — <span class="muted">' + escapeHtml(c.justification_note.slice(0,80)) + '</span>' : ''}
            </span>
            <button type="button" class="smallBtn danger" data-action="delete-char" data-char-id="${c.relationship_characterization_id}">×</button>
          </div>
        `;
      }).join('');
      tl.querySelectorAll('button[data-action="delete-char"]').forEach(b => {
        b.addEventListener('click', async (ev) => {
          ev.stopPropagation();
          const cid = Number(b.dataset.charId);
          if (!confirm('Delete this characterization?')) return;
          try {
            await fetchJSON(`/api/characterizations/${cid}`, { method: 'DELETE' });
            setStatus(`Deleted characterization ${cid}.`, 'ok');
            if (selectedPerson) await selectPerson(selectedPerson.person_id);
          } catch (e) {
            setStatus(`Delete failed: ${e.message}`, 'err');
          }
        });
      });
    }
    tl.classList.remove('hidden');
    itemEl.classList.add('expanded');
    expandedRelId = relId;
  } catch (e) {
    setStatus(`Could not load characterizations: ${e.message}`, 'err');
  }
}

// ---- Relationship add form (with other-person autocomplete) ----

const relAddForm = document.getElementById('relAddForm');
const relOtherSearch = document.getElementById('relOtherSearch');
const relOtherId = document.getElementById('relOtherId');
const relOtherAuto = document.getElementById('relOtherAuto');

function renderAuto(matches) {
  if (!matches.length) {
    relOtherAuto.classList.remove('open');
    relOtherAuto.innerHTML = '';
    return;
  }
  relOtherAuto.classList.add('open');
  relOtherAuto.innerHTML = matches.slice(0, 20).map(p => {
    const name = p.display_name || p.full_name || '(unnamed)';
    return `<div class="acItem" data-id="${p.person_id}">${escapeHtml(name)} <span class="muted">(id ${p.person_id})</span></div>`;
  }).join('');
  relOtherAuto.querySelectorAll('.acItem').forEach(it => {
    it.addEventListener('mousedown', (ev) => {
      ev.preventDefault();
      const pid = Number(it.dataset.id);
      const found = people.find(p => p.person_id === pid);
      relOtherId.value = pid;
      relOtherSearch.value = found ? (found.display_name || found.full_name) : `id ${pid}`;
      relOtherAuto.classList.remove('open');
    });
  });
}

if (relOtherSearch) {
  relOtherSearch.addEventListener('input', () => {
    const q = relOtherSearch.value.trim().toLowerCase();
    relOtherId.value = '';
    if (!q || q.length < 2) { renderAuto([]); return; }
    const me = selectedPerson ? selectedPerson.person_id : null;
    const hits = people.filter(p => {
      if (p.person_id === me) return false;
      const hay = (p.full_name || '') + ' ' + (p.display_name || '');
      return hay.toLowerCase().includes(q);
    });
    renderAuto(hits);
  });
  relOtherSearch.addEventListener('blur', () => {
    setTimeout(() => relOtherAuto.classList.remove('open'), 150);
  });
}

if (relAddForm) {
  relAddForm.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!selectedPerson) return;
    const otherId = Number(relOtherId.value || 0);
    if (!otherId) { setStatus('Pick the other person from the suggestions.', 'err'); return; }

    const fd = new FormData(relAddForm);
    const body = {
      person_a_id: selectedPerson.person_id,
      person_b_id: otherId,
      relationship_type_code: fd.get('relationship_type_code'),
      alignment_status_code: fd.get('alignment_status_code') || null,
      start_date: fd.get('start_date') || null,
      end_date: fd.get('end_date') || null,
      strength: fd.get('strength') ? Number(fd.get('strength')) : null,
      source_id: fd.get('source_id') ? Number(fd.get('source_id')) : null,
      notes: fd.get('notes') || null,
    };
    if (!body.relationship_type_code) { setStatus('Pick a relationship type.', 'err'); return; }
    try {
      const res = await fetchJSON('/api/relationships', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus(`Created relationship ${res.relationship.relationship_id}.`, 'ok');
      relAddForm.reset();
      relOtherId.value = '';
      const detailsEl = relAddForm.closest('details');
      if (detailsEl) detailsEl.open = false;
      await selectPerson(selectedPerson.person_id);
      await loadList();
    } catch (e) {
      setStatus(`Create failed: ${e.message}`, 'err');
    }
  });
}

// ---- Characterization dialog ----

const charDialog = document.getElementById('charDialog');
const charDialogWho = document.getElementById('charDialogWho');
const charEventSelect = document.getElementById('charEventSelect');
const charForm = document.getElementById('charForm');
const charCancel = document.getElementById('charCancel');
const charCancelX = document.getElementById('charCancelX');

async function ensureEventsLoaded() {
  if (allEvents.length) return;
  try {
    allEvents = await fetchJSON('/api/events');
  } catch (_) {
    allEvents = [];
  }
}

async function openCharDialog(relId) {
  pendingCharRelId = relId;
  await ensureEventsLoaded();
  // Populate event select
  while (charEventSelect.options.length > 1) charEventSelect.remove(1);
  for (const e of allEvents) {
    const o = document.createElement('option');
    o.value = e.event_id;
    const dates = [e.start_date, e.end_date].filter(Boolean).join('–');
    o.textContent = `${e.event_name}${dates ? ' (' + dates + ')' : ''}`;
    charEventSelect.appendChild(o);
  }
  // Populate other lookup-driven selects inside the dialog
  charDialog.querySelectorAll('select[data-lookup]').forEach(sel => {
    const key = sel.getAttribute('data-lookup');
    const items = lookups[key] || [];
    while (sel.options.length > 1) sel.remove(1);
    for (const it of items) {
      const o = document.createElement('option');
      o.value = it.code;
      o.textContent = `${it.label} (${it.code})`;
      sel.appendChild(o);
    }
  });
  // Identify the pair
  let label = `relationship ${relId}`;
  if (selectedPerson) {
    const rel = (selectedPerson.relationships || []).find(r => r.relationship_id === relId);
    if (rel) {
      const other = rel.other_person_name || `id ${rel.other_person_id}`;
      label = `${selectedPerson.display_name || selectedPerson.full_name} ↔ ${other}`;
    }
  }
  charDialogWho.textContent = label;
  charForm.reset();
  charDialog.classList.remove('hidden');
}

function closeCharDialog() {
  charDialog.classList.add('hidden');
  pendingCharRelId = null;
}
if (charCancel) charCancel.addEventListener('click', closeCharDialog);
if (charCancelX) charCancelX.addEventListener('click', closeCharDialog);

if (charForm) {
  charForm.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!pendingCharRelId) return;
    const fd = new FormData(charForm);
    const body = {
      event_id: fd.get('event_id') ? Number(fd.get('event_id')) : null,
      date_start: fd.get('date_start') || null,
      date_end: fd.get('date_end') || null,
      issue_category_code: fd.get('issue_category_code'),
      scale_level_code: fd.get('scale_level_code') || null,
      alignment_status_code: fd.get('alignment_status_code'),
      strength: fd.get('strength') ? Number(fd.get('strength')) : null,
      claim_type_code: fd.get('claim_type_code'),
      confidence_score: Number(fd.get('confidence_score')),
      evidence_type_code: fd.get('evidence_type_code'),
      counterevidence_present: fd.get('counterevidence_present') ? 1 : 0,
      source_id: Number(fd.get('source_id')),
      justification_note: fd.get('justification_note'),
      notes: fd.get('notes') || null,
    };
    try {
      await fetchJSON(`/api/relationships/${pendingCharRelId}/characterizations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus('Characterization added.', 'ok');
      const relId = pendingCharRelId;
      closeCharDialog();
      // Refresh and re-expand
      expandedRelId = relId;
      if (selectedPerson) await selectPerson(selectedPerson.person_id);
    } catch (e) {
      setStatus(`Save failed: ${e.message}`, 'err');
    }
  });
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


// ============================================================================
// Memberships (organizations: civic, religious, political clubs)
// ============================================================================

let allOrgs = [];
let allPlaces = [];

async function ensureOrgsLoaded(force=false) {
  if (!force && allOrgs.length) return;
  try { allOrgs = await fetchJSON('/api/organizations'); }
  catch (_) { allOrgs = []; }
}

async function ensurePlacesLoaded(force=false) {
  if (!force && allPlaces.length) return;
  try { allPlaces = await fetchJSON('/api/places'); }
  catch (_) { allPlaces = []; }
  // Populate any place selects that have already been rendered.
  for (const selId of ['membershipPlace', 'orgDialogPlace']) {
    const sel = document.getElementById(selId);
    if (!sel) continue;
    // Preserve current selection and the first "(none)" option.
    const currentVal = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    for (const p of allPlaces) {
      const o = document.createElement('option');
      o.value = p.place_id;
      o.textContent = `${p.place_name}${p.place_type_code ? ' (' + p.place_type_code + ')' : ''}`;
      sel.appendChild(o);
    }
    if (currentVal) sel.value = currentVal;
  }
}

function renderMemberships(rows) {
  membershipCountEl.textContent = `(${rows.length})`;
  if (!rows.length) {
    membershipList.innerHTML = '<div class="muted">No memberships yet.</div>';
    return;
  }
  membershipList.innerHTML = rows.map(m => {
    const dates = [m.date_start, m.date_end].filter(Boolean).join('–');
    return `
      <div class="rowItem">
        <div class="rowItemMain">
          <strong>${escapeHtml(m.organization_name || '(unnamed)')}</strong>
          <span class="rowItemMeta">
            ${escapeHtml(m.org_type_code || '')}
            ${m.role ? ' · ' + escapeHtml(m.role) : ''}
            ${dates ? ' · ' + escapeHtml(dates) : ''}
            ${m.place_name ? ' · 📍 ' + escapeHtml(m.place_name) : ''}
          </span>
          ${m.notes ? `<div class="rowItemMeta">${escapeHtml(m.notes)}</div>` : ''}
        </div>
        <div class="rowItemActions">
          <button type="button" class="smallBtn danger" data-action="delete-membership" data-id="${m.person_org_id}">×</button>
        </div>
      </div>
    `;
  }).join('');

  membershipList.querySelectorAll('button[data-action="delete-membership"]').forEach(b => {
    b.addEventListener('click', async () => {
      const id = Number(b.dataset.id);
      if (!confirm('Remove this membership?')) return;
      try {
        await fetchJSON(`/api/memberships/${id}`, { method: 'DELETE' });
        setStatus(`Membership ${id} removed.`, 'ok');
        if (selectedPerson) await selectPerson(selectedPerson.person_id);
      } catch (e) {
        setStatus(`Delete failed: ${e.message}`, 'err');
      }
    });
  });
}

// --- Org autocomplete inside the "+ Add membership" form ---

const membershipAddForm = document.getElementById('membershipAddForm');
const orgSearch = document.getElementById('orgSearch');
const orgIdInput = document.getElementById('orgId');
const orgAuto = document.getElementById('orgAuto');

function renderOrgAuto(matches) {
  if (!matches.length) {
    orgAuto.classList.remove('open');
    orgAuto.innerHTML = '';
    return;
  }
  orgAuto.classList.add('open');
  orgAuto.innerHTML = matches.slice(0, 20).map(o => `
    <div class="acItem" data-id="${o.organization_id}">
      ${escapeHtml(o.name)}
      <span class="muted">(${escapeHtml(o.org_type_code || '—')}; ${o.member_count || 0} members)</span>
    </div>
  `).join('');
  orgAuto.querySelectorAll('.acItem').forEach(it => {
    it.addEventListener('mousedown', ev => {
      ev.preventDefault();
      const oid = Number(it.dataset.id);
      const found = allOrgs.find(o => o.organization_id === oid);
      orgIdInput.value = oid;
      orgSearch.value = found ? found.name : `id ${oid}`;
      orgAuto.classList.remove('open');
    });
  });
}

if (orgSearch) {
  orgSearch.addEventListener('focus', () => { ensureOrgsLoaded(); ensurePlacesLoaded(); });
  orgSearch.addEventListener('input', () => {
    const q = orgSearch.value.trim().toLowerCase();
    orgIdInput.value = '';
    if (!q) { renderOrgAuto([]); return; }
    const hits = allOrgs.filter(o => (o.name || '').toLowerCase().includes(q));
    renderOrgAuto(hits);
  });
  orgSearch.addEventListener('blur', () => {
    setTimeout(() => orgAuto.classList.remove('open'), 150);
  });
}

if (membershipAddForm) {
  membershipAddForm.addEventListener('submit', async ev => {
    ev.preventDefault();
    if (!selectedPerson) return;
    const oid = Number(orgIdInput.value || 0);
    if (!oid) { setStatus('Pick an organization (or create a new one).', 'err'); return; }
    const fd = new FormData(membershipAddForm);
    const body = {
      organization_id: oid,
      role: fd.get('role') || null,
      date_start: fd.get('date_start') || null,
      date_end: fd.get('date_end') || null,
      source_id: fd.get('source_id') ? Number(fd.get('source_id')) : null,
      notes: fd.get('notes') || null,
      place_id: fd.get('place_id') ? Number(fd.get('place_id')) : null,
    };
    try {
      await fetchJSON(`/api/people/${selectedPerson.person_id}/memberships`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus('Membership added.', 'ok');
      membershipAddForm.reset();
      orgIdInput.value = '';
      const det = membershipAddForm.closest('details');
      if (det) det.open = false;
      await selectPerson(selectedPerson.person_id);
    } catch (e) {
      setStatus(`Save failed: ${e.message}`, 'err');
    }
  });
}

// --- "+ New organization…" inline dialog ---

const newOrgBtn = document.getElementById('newOrgBtn');
const orgDialog = document.getElementById('orgDialog');
const orgCreateForm = document.getElementById('orgCreateForm');
const orgCancel = document.getElementById('orgCancel');
const orgCancelX = document.getElementById('orgCancelX');

function openOrgDialog() {
  ensurePlacesLoaded();
  // Populate org_type select from lookups (only first time / each open is fine)
  orgDialog.querySelectorAll('select[data-lookup]').forEach(sel => {
    const key = sel.getAttribute('data-lookup');
    const items = lookups[key] || [];
    while (sel.options.length > 1) sel.remove(1);
    for (const it of items) {
      const o = document.createElement('option');
      o.value = it.code;
      o.textContent = `${it.label} (${it.code})`;
      sel.appendChild(o);
    }
  });
  orgCreateForm.reset();
  orgDialog.classList.remove('hidden');
  setTimeout(() => orgCreateForm.querySelector('input[name="name"]').focus(), 50);
}
function closeOrgDialog() { orgDialog.classList.add('hidden'); }
if (newOrgBtn) newOrgBtn.addEventListener('click', openOrgDialog);
if (orgCancel) orgCancel.addEventListener('click', closeOrgDialog);
if (orgCancelX) orgCancelX.addEventListener('click', closeOrgDialog);

if (orgCreateForm) {
  orgCreateForm.addEventListener('submit', async ev => {
    ev.preventDefault();
    const fd = new FormData(orgCreateForm);
    const body = {
      name: (fd.get('name') || '').toString().trim(),
      org_type_code: fd.get('org_type_code') || null,
      place_id: fd.get('place_id') ? Number(fd.get('place_id')) : null,
      start_date: fd.get('start_date') || null,
      end_date: fd.get('end_date') || null,
      notes: fd.get('notes') || null,
    };
    if (!body.name) { setStatus('Name is required.', 'err'); return; }
    try {
      const created = await fetchJSON('/api/organizations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus(`Created organization "${created.name}" (id ${created.organization_id}).`, 'ok');
      await ensureOrgsLoaded(true);
      // Auto-pick it in the membership form.
      orgIdInput.value = created.organization_id;
      orgSearch.value = created.name;
      closeOrgDialog();
      // Make sure the membership add panel is open.
      const det = membershipAddForm.closest('details');
      if (det) det.open = true;
    } catch (e) {
      setStatus(`Create failed: ${e.message}`, 'err');
    }
  });
}
