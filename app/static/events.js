// Unionism Network — Events Workbench
// Browse / create / edit / delete events, see which relationship
// characterizations are anchored to each.

const statusEl = document.getElementById('status');
const listEl = document.getElementById('eventList');
const listMeta = document.getElementById('listMeta');
const listSearch = document.getElementById('listSearch');
const filterUsed = document.getElementById('filterUsed');
const newEventBtn = document.getElementById('newEventBtn');

const editorEmpty = document.getElementById('editorEmpty');
const editorContent = document.getElementById('editorContent');
const editorEventName = document.getElementById('editorEventName');
const editorEventId = document.getElementById('editorEventId');
const eventForm = document.getElementById('eventForm');
const dirtyFlag = document.getElementById('dirtyFlag');
const resetBtn = document.getElementById('resetBtn');

const charList = document.getElementById('charList');
const charCountEl = document.getElementById('charCount');

const deleteBtn = document.getElementById('deleteBtn');
const deleteDialog = document.getElementById('deleteDialog');
const deleteWho = document.getElementById('deleteWho');
const deleteCancel = document.getElementById('deleteCancel');
const deleteCancelX = document.getElementById('deleteCancelX');
const deleteConfirm = document.getElementById('deleteConfirm');
const dbStatusEl = document.getElementById('dbStatus');

let events = [];
let lookups = {};
let places = [];
let selected = null;
let creating = false;
let initialSnapshot = {};
let searchTerm = '';

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
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

function populateLookups() {
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

  // Places list
  const placeSel = eventForm.elements['place_id'];
  while (placeSel.options.length > 1) placeSel.remove(1);
  for (const p of places) {
    const o = document.createElement('option');
    o.value = p.place_id;
    o.textContent = `${p.place_name} (${p.place_type_code})`;
    placeSel.appendChild(o);
  }
}

function renderList() {
  const q = searchTerm.trim().toLowerCase();
  const used = filterUsed.checked;
  const filtered = events.filter(e => {
    if (used && (!e.characterization_count || e.characterization_count === 0)) return false;
    if (!q) return true;
    return (e.event_name || '').toLowerCase().includes(q)
        || (e.description || '').toLowerCase().includes(q);
  });
  listMeta.textContent = `Showing ${filtered.length} of ${events.length} events`;
  listEl.innerHTML = '';
  for (const e of filtered) {
    const row = document.createElement('div');
    row.className = 'listRow';
    row.dataset.eventId = e.event_id;
    if (selected && selected.event_id === e.event_id) row.classList.add('selected');
    const dates = [e.start_date, e.end_date].filter(Boolean).join(' – ');
    const meta = [
      `id ${e.event_id}`,
      e.event_type_code,
      dates,
      e.place_name,
    ].filter(Boolean).join(' · ');
    const badges = [];
    if (e.characterization_count > 0) badges.push(`<span class="rowBadge">${e.characterization_count} char</span>`);
    row.innerHTML = `
      <div class="rowName">${escapeHtml(e.event_name || '(unnamed)')}</div>
      <div class="rowMeta">${escapeHtml(meta)} ${badges.join(' ')}</div>
    `;
    row.addEventListener('click', () => selectEvent(e.event_id));
    listEl.appendChild(row);
  }
}

async function loadList() {
  events = await fetchJSON('/api/events');
  renderList();
  dbStatusEl.textContent = `${events.length} events`;
}

function showEmpty() {
  selected = null;
  creating = false;
  editorContent.classList.add('hidden');
  editorEmpty.classList.remove('hidden');
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
}

function showEditor() {
  editorContent.classList.remove('hidden');
  editorEmpty.classList.add('hidden');
}

function fillForm(e) {
  for (const el of eventForm.elements) {
    if (!el.name) continue;
    if (e[el.name] != null) el.value = e[el.name];
    else el.value = '';
  }
  initialSnapshot = snapshot();
  setDirty(false);
}

function snapshot() {
  const o = {};
  for (const el of eventForm.elements) {
    if (!el.name) continue;
    o[el.name] = el.value;
  }
  return o;
}

function bodyForSubmit() {
  const o = snapshot();
  for (const k of Object.keys(o)) {
    if (o[k] === '') delete o[k];
  }
  if (o.place_id != null) o.place_id = Number(o.place_id);
  return o;
}

function setDirty(b) {
  dirtyFlag.textContent = b ? 'Unsaved changes' : '';
}

eventForm.addEventListener('input', () => {
  const cur = snapshot();
  const dirty = Object.keys(cur).some(k => String(cur[k]) !== String(initialSnapshot[k] ?? ''));
  setDirty(dirty);
});

resetBtn.addEventListener('click', () => {
  if (creating) {
    eventForm.reset();
    initialSnapshot = snapshot();
    setDirty(false);
  } else if (selected) {
    fillForm(selected);
  }
});

eventForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const body = bodyForSubmit();
  if (!body.event_name) { setStatus('Event name is required.', 'err'); return; }
  if (!body.event_type_code) { setStatus('Event type is required.', 'err'); return; }
  try {
    let res;
    if (creating) {
      res = await fetchJSON('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus(`Created event ${res.event_id}: ${res.event_name}`, 'ok');
    } else {
      res = await fetchJSON(`/api/events/${selected.event_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus(`Saved event ${res.event_id}.`, 'ok');
    }
    await loadList();
    await selectEvent(res.event_id);
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
  }
});

newEventBtn.addEventListener('click', () => {
  creating = true;
  selected = null;
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
  editorEventName.textContent = 'New event';
  editorEventId.textContent = '(unsaved)';
  eventForm.reset();
  initialSnapshot = snapshot();
  setDirty(false);
  charList.innerHTML = '<div class="muted">Save the event first.</div>';
  charCountEl.textContent = '(0)';
  showEditor();
  eventForm.querySelector('input[name="event_name"]').focus();
});

async function selectEvent(eventId) {
  try {
    const e = await fetchJSON(`/api/events/${eventId}`);
    creating = false;
    selected = e;
    editorEventName.textContent = e.event_name || '(unnamed)';
    editorEventId.textContent = `id ${e.event_id}`;
    fillForm(e);
    renderChars(e.characterizations || []);
    document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
    const row = listEl.querySelector(`.listRow[data-event-id="${eventId}"]`);
    if (row) { row.classList.add('selected'); row.scrollIntoView({ block: 'nearest' }); }
    showEditor();
  } catch (e) {
    setStatus(`Load failed: ${e.message}`, 'err');
  }
}

function renderChars(chars) {
  charCountEl.textContent = `(${chars.length})`;
  if (!chars.length) {
    charList.innerHTML = '<div class="muted">No relationship characterizations anchored to this event.</div>';
    return;
  }
  charList.innerHTML = chars.map(c => {
    const pair = `${c.person_low_name || '?'} ↔ ${c.person_high_name || '?'}`;
    const dates = [c.date_start, c.date_end].filter(Boolean).join(' – ');
    return `
      <div class="rowItem">
        <div class="rowItemMain">
          <strong>${escapeHtml(pair)}</strong>
          <span class="rowItemMeta">
            ${escapeHtml(c.issue_category_code || '')} ·
            ${escapeHtml(c.alignment_status_code || '')}
            ${dates ? ' · ' + escapeHtml(dates) : ''}
          </span>
        </div>
        <a href="/people?person=${c.person_low_id}" class="smallBtn">Open person</a>
      </div>
    `;
  }).join('');
}

deleteBtn.addEventListener('click', () => {
  if (!selected) return;
  deleteWho.textContent = `${selected.event_name} (id ${selected.event_id})`;
  deleteDialog.classList.remove('hidden');
});
function closeDeleteDialog() { deleteDialog.classList.add('hidden'); }
deleteCancel.addEventListener('click', closeDeleteDialog);
deleteCancelX.addEventListener('click', closeDeleteDialog);
deleteConfirm.addEventListener('click', async () => {
  if (!selected) return;
  const id = selected.event_id;
  try {
    await fetchJSON(`/api/events/${id}`, { method: 'DELETE' });
    closeDeleteDialog();
    setStatus(`Deleted event ${id}.`, 'ok');
    showEmpty();
    await loadList();
  } catch (e) {
    setStatus(`Delete failed: ${e.message}`, 'err');
  }
});

listSearch.addEventListener('input', () => { searchTerm = listSearch.value; renderList(); });
filterUsed.addEventListener('change', renderList);

(async function init() {
  try {
    [lookups, places] = await Promise.all([
      fetchJSON('/api/lookups'),
      fetchJSON('/api/places'),
    ]);
    populateLookups();
    await loadList();
    setStatus(`Ready. ${events.length} events loaded.`, 'ok');
  } catch (e) {
    setStatus(`Init failed: ${e.message}`, 'err');
  }
})();
