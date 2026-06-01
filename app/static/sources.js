// Unionism Network — Sources Workbench
const statusEl      = document.getElementById('status');
const listEl        = document.getElementById('sourceList');
const listMeta      = document.getElementById('listMeta');
const listSearch    = document.getElementById('listSearch');
const filterType    = document.getElementById('filterType');
const newSourceBtn  = document.getElementById('newSourceBtn');
const editorEmpty   = document.getElementById('editorEmpty');
const editorContent = document.getElementById('editorContent');
const editorTitle   = document.getElementById('editorSourceTitle');
const editorId      = document.getElementById('editorSourceId');
const sourceForm    = document.getElementById('sourceForm');
const dirtyFlag     = document.getElementById('dirtyFlag');
const resetBtn      = document.getElementById('resetBtn');
const usageList     = document.getElementById('usageList');
const usageCount    = document.getElementById('usageCount');
const deleteBtn     = document.getElementById('deleteBtn');
const deleteDialog  = document.getElementById('deleteDialog');
const deleteWho     = document.getElementById('deleteWho');
const deleteCancel  = document.getElementById('deleteCancel');
const deleteCancelX = document.getElementById('deleteCancelX');
const deleteConfirm = document.getElementById('deleteConfirm');
const dbStatusEl    = document.getElementById('dbStatus');

let sources = [], lookups = {}, selected = null, creating = false, initialSnapshot = {}, searchTerm = '';

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
  while (filterType.options.length > 1) filterType.remove(1);
  [...new Set(sources.map(s => s.source_type_code).filter(Boolean))].sort().forEach(t => {
    const o = document.createElement('option'); o.value = t; o.textContent = t; filterType.appendChild(o);
  });
}

function sourceSubtitle(s) {
  return [s.source_type_code, s.creator, s.date_created ? s.date_created.slice(0,4) : null, s.archive]
    .filter(Boolean).join(' · ');
}

function renderList() {
  const q = searchTerm.trim().toLowerCase(), ft = filterType.value;
  const filtered = sources.filter(s => {
    if (ft && s.source_type_code !== ft) return false;
    if (!q) return true;
    return (s.title||'').toLowerCase().includes(q)
      || (s.creator||'').toLowerCase().includes(q)
      || (s.archive||'').toLowerCase().includes(q)
      || (s.citation_full||'').toLowerCase().includes(q);
  });
  listMeta.textContent = `Showing ${filtered.length} of ${sources.length} sources`;
  listEl.innerHTML = '';
  for (const s of filtered) {
    const row = document.createElement('div');
    row.className = 'listRow'; row.dataset.sourceId = s.source_id;
    if (selected?.source_id === s.source_id) row.classList.add('selected');
    row.innerHTML = `<div class="rowName">${escapeHtml(s.title)}</div>
      <div class="rowMeta">${escapeHtml(sourceSubtitle(s))}</div>`;
    row.addEventListener('click', () => selectSource(s.source_id));
    listEl.appendChild(row);
  }
}

async function loadList() {
  sources = await fetchJSON('/api/sources');
  populateLookups(); renderList();
  dbStatusEl.textContent = `${sources.length} sources`;
}

function showEmpty() {
  selected = null; creating = false;
  editorContent.classList.add('hidden'); editorEmpty.classList.remove('hidden');
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
}
function showEditor() { editorContent.classList.remove('hidden'); editorEmpty.classList.add('hidden'); }

function fillForm(s) {
  for (const el of sourceForm.elements) {
    if (el.name) el.value = s[el.name] != null ? s[el.name] : '';
  }
  initialSnapshot = snapshot(); setDirty(false);
}
function snapshot() {
  const o = {}; for (const el of sourceForm.elements) { if (el.name) o[el.name] = el.value; } return o;
}
function setDirty(b) { dirtyFlag.textContent = b ? 'Unsaved changes' : ''; }

sourceForm.addEventListener('input', () => {
  const cur = snapshot();
  setDirty(Object.keys(cur).some(k => String(cur[k]) !== String(initialSnapshot[k] ?? '')));
});

resetBtn.addEventListener('click', () => {
  if (creating) { sourceForm.reset(); initialSnapshot = snapshot(); setDirty(false); }
  else if (selected) fillForm(selected);
});

sourceForm.addEventListener('submit', async ev => {
  ev.preventDefault();
  const body = {};
  for (const [k, v] of Object.entries(snapshot())) {
    body[k] = v === '' ? null : v;
  }
  if (!body.title) { setStatus('Title is required.', 'err'); return; }
  if (!body.source_type_code) { setStatus('Type is required.', 'err'); return; }
  try {
    const res = creating
      ? await fetchJSON('/api/sources', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
      : await fetchJSON(`/api/sources/${selected.source_id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    setStatus(`${creating ? 'Created' : 'Saved'} source ${res.source_id}.`, 'ok');
    await loadList(); await selectSource(res.source_id);
  } catch (e) { setStatus(`Save failed: ${e.message}`, 'err'); }
});

newSourceBtn.addEventListener('click', () => {
  creating = true; selected = null;
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
  editorTitle.textContent = 'New source'; editorId.textContent = '(unsaved)';
  sourceForm.reset(); initialSnapshot = snapshot(); setDirty(false);
  usageList.innerHTML = ''; usageCount.textContent = '(0)';
  showEditor(); sourceForm.querySelector('input[name="title"]').focus();
});

async function selectSource(sourceId) {
  try {
    const s = await fetchJSON(`/api/sources/${sourceId}`);
    creating = false; selected = s;
    editorTitle.textContent = s.title; editorId.textContent = `id ${s.source_id}`;
    fillForm(s); renderUsages(s.usages || []);
    document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
    const row = listEl.querySelector(`.listRow[data-source-id="${sourceId}"]`);
    if (row) { row.classList.add('selected'); row.scrollIntoView({ block:'nearest' }); }
    showEditor();
  } catch (e) { setStatus(`Load failed: ${e.message}`, 'err'); }
}

function renderUsages(usages) {
  usageCount.textContent = `(${usages.length})`;
  if (!usages.length) {
    usageList.innerHTML = '<div class="muted">No recorded usages yet.</div>';
    return;
  }
  usageList.innerHTML = usages.map(u => `
    <div class="rowItem">
      <div class="rowItemMain">
        <strong>${escapeHtml(u.person_name || '?')}</strong>
        <span class="rowItemMeta">${escapeHtml(u.usage_type)} · ${escapeHtml(u.detail || '')}</span>
      </div>
      <a href="/people?person=${u.person_id}" class="smallBtn">Open</a>
    </div>
  `).join('');
}

deleteBtn.addEventListener('click', () => {
  if (!selected) return;
  deleteWho.textContent = `"${selected.title}" (id ${selected.source_id})`;
  deleteDialog.classList.remove('hidden');
});
function closeDeleteDialog() { deleteDialog.classList.add('hidden'); }
deleteCancel.addEventListener('click', closeDeleteDialog);
deleteCancelX.addEventListener('click', closeDeleteDialog);
deleteConfirm.addEventListener('click', async () => {
  if (!selected) return;
  const id = selected.source_id;
  try {
    await fetchJSON(`/api/sources/${id}`, { method:'DELETE' });
    closeDeleteDialog(); setStatus(`Deleted source ${id}.`, 'ok');
    showEmpty(); await loadList();
  } catch (e) {
    closeDeleteDialog();
    setStatus(`Delete failed: ${e.message}`, 'err');
  }
});

listSearch.addEventListener('input', () => { searchTerm = listSearch.value; renderList(); });
filterType.addEventListener('change', renderList);

(async function init() {
  try {
    [lookups, sources] = await Promise.all([
      fetchJSON('/api/lookups'),
      fetchJSON('/api/sources'),
    ]);
    populateLookups(); renderList();
    setStatus(`Ready. ${sources.length} sources loaded.`, 'ok');
  } catch (e) {
    setStatus(`Init failed: ${e.message}`, 'err');
  }
})();