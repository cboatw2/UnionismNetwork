// Unionism Network — Organizations Workbench
const statusEl = document.getElementById('status');
const listEl = document.getElementById('orgList');
const listMeta = document.getElementById('listMeta');
const listSearch = document.getElementById('listSearch');
const filterType = document.getElementById('filterType');
const newOrgBtn = document.getElementById('newOrgBtn');
const editorEmpty = document.getElementById('editorEmpty');
const editorContent = document.getElementById('editorContent');
const editorOrgName = document.getElementById('editorOrgName');
const editorOrgId = document.getElementById('editorOrgId');
const orgForm = document.getElementById('orgForm');
const dirtyFlag = document.getElementById('dirtyFlag');
const resetBtn = document.getElementById('resetBtn');
const memberList = document.getElementById('memberList');
const memberCount = document.getElementById('memberCount');
const deleteBtn = document.getElementById('deleteBtn');
const deleteDialog = document.getElementById('deleteDialog');
const deleteWho = document.getElementById('deleteWho');
const deleteCancel = document.getElementById('deleteCancel');
const deleteCancelX = document.getElementById('deleteCancelX');
const deleteConfirm = document.getElementById('deleteConfirm');
const dbStatusEl = document.getElementById('dbStatus');

let orgs = [], lookups = {}, places = [], selected = null, creating = false, initialSnapshot = {}, searchTerm = '';

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
  const placeSel = orgForm.elements['place_id'];
  while (placeSel.options.length > 1) placeSel.remove(1);
  for (const p of places) {
    const o = document.createElement('option');
    o.value = p.place_id; o.textContent = `${p.place_name} (${p.place_type_code})`; placeSel.appendChild(o);
  }
  while (filterType.options.length > 1) filterType.remove(1);
  [...new Set(orgs.map(o => o.org_type_code).filter(Boolean))].sort().forEach(t => {
    const o = document.createElement('option'); o.value = t; o.textContent = t; filterType.appendChild(o);
  });
}

function renderList() {
  const q = searchTerm.trim().toLowerCase(), ft = filterType.value;
  const filtered = orgs.filter(o => {
    if (ft && o.org_type_code !== ft) return false;
    if (!q) return true;
    return (o.name||'').toLowerCase().includes(q) || (o.place_name||'').toLowerCase().includes(q);
  });
  listMeta.textContent = `Showing ${filtered.length} of ${orgs.length} organizations`;
  listEl.innerHTML = '';
  for (const o of filtered) {
    const row = document.createElement('div');
    row.className = 'listRow'; row.dataset.orgId = o.organization_id;
    if (selected?.organization_id === o.organization_id) row.classList.add('selected');
    const dates = [o.start_date, o.end_date].filter(Boolean).join(' – ');
    const badges = o.member_count > 0 ? `<span class="rowBadge">${o.member_count} member${o.member_count !== 1 ? 's' : ''}</span>` : '';
    row.innerHTML = `<div class="rowName">${escapeHtml(o.name)}</div>
      <div class="rowMeta">${escapeHtml([o.org_type_code, o.place_name, dates].filter(Boolean).join(' · '))} ${badges}</div>`;
    row.addEventListener('click', () => selectOrg(o.organization_id));
    listEl.appendChild(row);
  }
}

async function loadList() {
  orgs = await fetchJSON('/api/organizations');
  populateLookups(); renderList();
  dbStatusEl.textContent = `${orgs.length} organizations`;
}

function showEmpty() {
  selected = null; creating = false;
  editorContent.classList.add('hidden'); editorEmpty.classList.remove('hidden');
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
}
function showEditor() { editorContent.classList.remove('hidden'); editorEmpty.classList.add('hidden'); }

function fillForm(o) {
  for (const el of orgForm.elements) { if (el.name) el.value = o[el.name] != null ? o[el.name] : ''; }
  initialSnapshot = snapshot(); setDirty(false);
}
function snapshot() {
  const o = {}; for (const el of orgForm.elements) { if (el.name) o[el.name] = el.value; } return o;
}
function bodyForSubmit() {
  const body = {};
  for (const [k, v] of Object.entries(snapshot())) {
    if (v === '') continue;
    body[k] = k === 'place_id' ? Number(v) : v;
  }
  return body;
}
function setDirty(b) { dirtyFlag.textContent = b ? 'Unsaved changes' : ''; }

orgForm.addEventListener('input', () => {
  const cur = snapshot();
  setDirty(Object.keys(cur).some(k => String(cur[k]) !== String(initialSnapshot[k] ?? '')));
});
resetBtn.addEventListener('click', () => {
  if (creating) { orgForm.reset(); initialSnapshot = snapshot(); setDirty(false); }
  else if (selected) fillForm(selected);
});

orgForm.addEventListener('submit', async ev => {
  ev.preventDefault();
  const body = bodyForSubmit();
  if (!body.name) { setStatus('Name is required.', 'err'); return; }
  if (!body.org_type_code) { setStatus('Type is required.', 'err'); return; }
  try {
    const res = creating
      ? await fetchJSON('/api/organizations', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) })
      : await fetchJSON(`/api/organizations/${selected.organization_id}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    setStatus(`${creating ? 'Created' : 'Saved'} organization ${res.organization_id}.`, 'ok');
    await loadList(); await selectOrg(res.organization_id);
  } catch (e) { setStatus(`Save failed: ${e.message}`, 'err'); }
});

newOrgBtn.addEventListener('click', () => {
  creating = true; selected = null;
  document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
  editorOrgName.textContent = 'New organization'; editorOrgId.textContent = '(unsaved)';
  orgForm.reset(); initialSnapshot = snapshot(); setDirty(false);
  memberList.innerHTML = '<div class="muted">Save the organization first.</div>';
  memberCount.textContent = '(0)';
  showEditor(); orgForm.querySelector('input[name="name"]').focus();
});

async function selectOrg(orgId) {
  try {
    const o = await fetchJSON(`/api/organizations/${orgId}`);
    creating = false; selected = o;
    editorOrgName.textContent = o.name; editorOrgId.textContent = `id ${o.organization_id}`;
    fillForm(o); renderMembers(o.members || []);
    document.querySelectorAll('.listRow.selected').forEach(r => r.classList.remove('selected'));
    const row = listEl.querySelector(`.listRow[data-org-id="${orgId}"]`);
    if (row) { row.classList.add('selected'); row.scrollIntoView({ block:'nearest' }); }
    showEditor();
  } catch (e) { setStatus(`Load failed: ${e.message}`, 'err'); }
}

function renderMembers(members) {
  memberCount.textContent = `(${members.length})`;
  memberList.innerHTML = members.length ? members.map(m => {
    const dates = [m.date_start, m.date_end].filter(Boolean).join(' – ');
    return `<div class="rowItem">
      <div class="rowItemMain">
        <strong>${escapeHtml(m.person_name || '?')}</strong>
        <span class="rowItemMeta">${escapeHtml([m.role, dates].filter(Boolean).join(' · '))}</span>
      </div>
      <a href="/people?person=${m.person_id}" class="smallBtn">Open</a>
    </div>`;
  }).join('') : '<div class="muted">No members yet.</div>';
}

deleteBtn.addEventListener('click', () => {
  if (!selected) return;
  deleteWho.textContent = `${selected.name} (id ${selected.organization_id})`;
  deleteDialog.classList.remove('hidden');
});
function closeDeleteDialog() { deleteDialog.classList.add('hidden'); }
deleteCancel.addEventListener('click', closeDeleteDialog);
deleteCancelX.addEventListener('click', closeDeleteDialog);
deleteConfirm.addEventListener('click', async () => {
  if (!selected) return;
  const id = selected.organization_id;
  try {
    await fetchJSON(`/api/organizations/${id}`, { method:'DELETE' });
    closeDeleteDialog(); setStatus(`Deleted organization ${id}.`, 'ok');
    showEmpty(); await loadList();
  } catch (e) { setStatus(`Delete failed: ${e.message}`, 'err'); closeDeleteDialog(); }
});

listSearch.addEventListener('input', () => { searchTerm = listSearch.value; renderList(); });
filterType.addEventListener('change', renderList);

(async function init() {
  try {
    [lookups, places, orgs] = await Promise.all([
      fetchJSON('/api/lookups'), fetchJSON('/api/places'), fetchJSON('/api/organizations'),
    ]);
    populateLookups(); renderList();
    setStatus(`Ready. ${orgs.length} organizations loaded.`, 'ok');
  } catch (e) { setStatus(`Init failed: ${e.message}`, 'err'); }
})();