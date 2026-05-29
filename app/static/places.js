// Unionism Network — Places Workbench
const statusEl = document.getElementById('status');
const listEl = document.getElementById('placeList');
const listMeta = document.getElementById('listMeta');
const listSearch = document.getElementById('listSearch');
const filterType = document.getElementById('filterType');
const newPlaceBtn = document.getElementById('newPlaceBtn');
const editorEmpty = document.getElementById('editorEmpty');
const editorContent = document.getElementById('editorContent');
const editorPlaceName = document.getElementById('editorPlaceName');
const editorPlaceId = document.getElementById('editorPlaceId');
const placeForm = document.getElementById('placeForm');
const dirtyFlag = document.getElementById('dirtyFlag');
const resetBtn = document.getElementById('resetBtn');
const deleteBtn = document.getElementById('deleteBtn');
const deleteDialog = document.getElementById('deleteDialog');
const deleteWho = document.getElementById('deleteWho');
const deleteCancel = document.getElementById('deleteCancel');
const deleteCancelX = document.getElementById('deleteCancelX');
const deleteConfirm = document.getElementById('deleteConfirm');
const dbStatusEl = document.getElementById('dbStatus');

let places = [], lookups = {}, selected = null, creating = false, initialSnapshot = {}, searchTerm = '';

function setStatus(msg, kind) {
  statusEl.textContent = msg || '';
  statusEl.classList.remove('ok', 'err');
  if (kind) statusEl.classList.add(kind);
  if (kind === 'ok') setTimeout(() => { if (statusEl.classList.contains('ok')) setStatus(''); }, 3500);
}

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail || detail; } catch (_) {}
    const err = new Error(`${res.status} ${detail}`); err.status = res.status; throw err;
  }
  return res.json();
}

function escapeHtml(s) {
  return String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
}

function populateLookups() {
  document.querySelectorAll('select[data-lookup]').forEach(sel => {
    const items = lookups[sel.getAttribute('data-lookup')] || [];
    while (sel.options.length > 1) sel.remove(1);
    for (const it of items) {
      const o = document.createElement('option');
      o.value = it.code; o.textContent = `${it.label} (${it.code})`; sel.appendChild(o);
    }
  });
  const parentSel = placeForm.elements['parent_place_id'];
  while (parentSel.options.length > 1) parentSel.remove(1);
  for (const p of places) {
    const o = document.createElement('option');
    o.value = p.place_id; o.textContent = `${p.place_name} (${p.place_type_code})`; parentSel.appendChild(o);
  }
  while (filterType.options.length > 1) filterType.remove(1);
  [...new Set(places.map(p => p.place_type_code).filter(Boolean))].sort().forEach(t => {
    const o = document.createElement('option'); o.value = t; o.textContent = t; filterType.appendChild(o);
  });
}

function renderList() {
  const q = searchTerm.trim().toLowerCase(), ft = filterType.value;
  const filtered = places.filter(p => {
    if (ft && p.place_type_code !== ft) return false;
    if (!q) return true;
    return (p.place_name||'').toLowerCase().includes(q) || (p.modern_state||'').toLowerCase().includes(q);
  });
  listMeta.textContent = `Showing ${filtered.length} of ${places.length} places`;
  listEl.innerHTML = '';
  for (const p of filtered) {
    const row = document.createElement('div');
    row.className = 'listRow'; row.dataset.placeId = p.place_id;
    if (selected?.place_id === p.place_id) row.classList.add('selected');
    const coords = p.latitude != null && p.longitude != null ? `${Number(p.latitude).toFixed(3)}, ${Number(p.longitude).toFixed(3)}` : null;
    row.innerHTML = `<div class="rowName">${escapeHtml(p.place_name)}</div>
      <div class="rowMeta">${escapeHtml([p.place_type_code, p.modern_state, coords].filter(Boolean).join(' · '))}</div>`;
    row.addEventListener('click', () => selectPlace(p.place_id));
    listEl.appendChild(row);
  }
}

async function loadList() {
  places = await fetchJSON('/api/places');
  populateLookups(); renderList();
  dbStatusEl.textContent = `${places.length} places`;
}

function showEmpty() {
  selected = null; creating = false;
  editorContent.classList.add('hidden'); editorEmpty.classList.remove('hidden');
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
}
function showEditor() { editorContent.classList.remove('hidden'); editorEmpty.classList.add('hidden'); }

function fillForm(p) {
  for (const el of placeForm.elements) { if (el.name) el.value = p[el.name] != null ? p[el.name] : ''; }
  initialSnapshot = snapshot(); setDirty(false);
}
function snapshot() {
  const o = {}; for (const el of placeForm.elements) { if (el.name) o[el.name] = el.value; } return o;
}
function bodyForSubmit() {
  const body = {};
  for (const [k, v] of Object.entries(snapshot())) {
    if (v === '') continue;
    body[k] = ['parent_place_id','latitude','longitude'].includes(k) ? Number(v) : v;
  }
  return body;
}
function setDirty(b) { dirtyFlag.textContent = b ? 'Unsaved changes' : ''; }

placeForm.addEventListener('input', () => {
  const cur = snapshot();
  setDirty(Object.keys(cur).some(k => String(cur[k]) !== String(initialSnapshot[k] ?? '')));
});
resetBtn.addEventListener('click', () => {
  if (creating) { placeForm.reset(); initialSnapshot = snapshot(); setDirty(false); }
  else if (selected) fillForm(selected);
});

placeForm.addEventListener('submit', async ev => {
  ev.preventDefault();
  const body = bodyForSubmit();
  if (!body.place_name) { setStatus('Place name is required.', 'err'); return; }
  if (!body.place_type_code) { setStatus('Place type is required.', 'err'); return; }
  try {
    const res = creating
      ? await fetchJSON('/api/places', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
      : await fetchJSON(`/api/places/${selected.place_id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    setStatus(`${creating ? 'Created' : 'Saved'} place ${res.place_id}: ${res.place_name}`, 'ok');
    await loadList(); await selectPlace(res.place_id);
  } catch (e) { setStatus(`Save failed: ${e.message}`, 'err'); }
});

newPlaceBtn.addEventListener('click', () => {
  creating = true; selected = null;
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
  editorPlaceName.textContent = 'New place'; editorPlaceId.textContent = '(unsaved)';
  placeForm.reset(); initialSnapshot = snapshot(); setDirty(false);
  showEditor(); placeForm.querySelector('input[name="place_name"]').focus();
});

async function selectPlace(placeId) {
  try {
    const p = await fetchJSON(`/api/places/${placeId}`);
    creating = false; selected = p;
    editorPlaceName.textContent = p.place_name; editorPlaceId.textContent = `id ${p.place_id}`;
    fillForm(p);
    document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
    const row = listEl.querySelector(`.listRow[data-place-id="${placeId}"]`);
    if (row) { row.classList.add('selected'); row.scrollIntoView({ block:'nearest' }); }
    showEditor();
  } catch (e) { setStatus(`Load failed: ${e.message}`, 'err'); }
}

deleteBtn.addEventListener('click', () => {
  if (!selected) return;
  deleteWho.textContent = `${selected.place_name} (id ${selected.place_id})`;
  deleteDialog.classList.remove('hidden');
});
function closeDeleteDialog() { deleteDialog.classList.add('hidden'); }
deleteCancel.addEventListener('click', closeDeleteDialog);
deleteCancelX.addEventListener('click', closeDeleteDialog);
deleteConfirm.addEventListener('click', async () => {
  if (!selected) return;
  const id = selected.place_id;
  try {
    await fetchJSON(`/api/places/${id}`, { method:'DELETE' });
    closeDeleteDialog(); setStatus(`Deleted place ${id}.`, 'ok');
    showEmpty(); await loadList();
  } catch (e) { setStatus(`Delete failed: ${e.message}`, 'err'); closeDeleteDialog(); }
});

listSearch.addEventListener('input', () => { searchTerm = listSearch.value; renderList(); });
filterType.addEventListener('change', renderList);

(async function init() {
  try {
    [lookups, places] = await Promise.all([fetchJSON('/api/lookups'), fetchJSON('/api/places')]);
    populateLookups(); renderList();
    setStatus(`Ready. ${places.length} places loaded.`, 'ok');
  } catch (e) { setStatus(`Init failed: ${e.message}`, 'err'); }
})();