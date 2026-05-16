// Unionism Network — data entry page
// Loads lookups, people, and sources; submits to the new POST endpoints.

const statusEl = document.getElementById('entryStatus');

let lookups = {};
let people = [];
let sources = [];
let events = [];

function setStatus(msg, kind) {
  statusEl.textContent = msg || '';
  statusEl.classList.remove('ok', 'err');
  if (kind) statusEl.classList.add(kind);
}

function clearStatusSoon() {
  // Only auto-clear successful or neutral status. Errors stay visible until
  // the next status replaces them.
  setTimeout(() => {
    if (!statusEl.classList.contains('err')) {
      setStatus('');
    }
  }, 4000);
}

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    let body = null;
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

function populateSelect(sel, items, { valueKey, labelKey, placeholder = '' } = {}) {
  sel.innerHTML = '';
  const opt0 = document.createElement('option');
  opt0.value = '';
  opt0.textContent = placeholder;
  sel.appendChild(opt0);
  for (const it of items) {
    const o = document.createElement('option');
    o.value = it[valueKey];
    o.textContent = it[labelKey] != null ? `${it[labelKey]}` : String(it[valueKey]);
    sel.appendChild(o);
  }
}

function fillLookupSelects() {
  document.querySelectorAll('select[data-lookup]').forEach(sel => {
    const key = sel.getAttribute('data-lookup');
    const items = lookups[key] || [];
    // Preserve the first existing <option> (placeholder).
    const placeholder = sel.options.length ? sel.options[0].textContent : '';
    populateSelect(sel, items.map(i => ({ code: i.code, label: `${i.label} (${i.code})` })), {
      valueKey: 'code',
      labelKey: 'label',
      placeholder,
    });
  });
}

function fillPeopleSelects() {
  const opts = people.map(p => ({
    person_id: p.person_id,
    label: `${p.display_name || p.full_name || '(unnamed)'} — id ${p.person_id}`,
  }));
  for (const id of ['personPicker', 'positionPerson', 'aliasPerson', 'relPersonA', 'relPersonB']) {
    const sel = document.getElementById(id);
    if (!sel) continue;
    populateSelect(sel, opts, {
      valueKey: 'person_id',
      labelKey: 'label',
      placeholder: id === 'personPicker' ? '— Create new —' : '',
    });
  }
}

function fillSourceSelects() {
  const opts = sources.map(s => ({
    source_id: s.source_id,
    label: `${s.title} — id ${s.source_id}${s.creator ? ` (${s.creator})` : ''}`,
  }));
  for (const id of ['positionSource', 'aliasSource', 'relSource', 'relCharSource']) {
    const sel = document.getElementById(id);
    if (!sel) continue;
    populateSelect(sel, opts, { valueKey: 'source_id', labelKey: 'label', placeholder: '' });
  }
}

async function reloadAll() {
  [lookups, people, sources, events] = await Promise.all([
    fetchJSON('/api/lookups'),
    fetchJSON('/api/people'),
    fetchJSON('/api/sources'),
    fetchJSON('/api/events'),
  ]);
  fillLookupSelects();
  fillPeopleSelects();
  fillSourceSelects();
  fillEventSelect();
  renderRecentSources();
}

function fillEventSelect() {
  const opts = events.map(e => ({
    event_id: e.event_id,
    label: `${e.event_name}${e.start_date ? ' — ' + e.start_date.slice(0, 4) : ''} (id ${e.event_id})`,
  }));
  for (const id of ['positionEvent', 'relEvent']) {
    const sel = document.getElementById(id);
    if (!sel) continue;
    populateSelect(sel, opts, { valueKey: 'event_id', labelKey: 'label', placeholder: '— none —' });
  }
}

function renderRecentSources() {
  const el = document.getElementById('recentSources');
  if (!el) return;
  el.innerHTML = sources.slice(0, 20)
    .map(s => `<div class="row">[${s.source_id}] <strong>${escapeHtml(s.title)}</strong> — ${escapeHtml(s.source_type_code || '')}${s.creator ? ` · ${escapeHtml(s.creator)}` : ''}</div>`)
    .join('') || '<div class="muted">No sources yet.</div>';
}

function escapeHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

// --- Tabs ---
function switchTab(name) {
  document.querySelectorAll('.tabBtn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.entryPanel').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== name));
}
document.querySelectorAll('.tabBtn').forEach(b => {
  b.addEventListener('click', () => switchTab(b.dataset.tab));
});

// --- Form serialization ---
function formData(form) {
  const fd = new FormData(form);
  const obj = {};
  for (const [k, v] of fd.entries()) {
    obj[k] = v;
  }
  // Coerce checkboxes (unchecked are absent).
  form.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    obj[cb.name] = cb.checked ? 1 : 0;
  });
  // Drop empty strings to let server treat as NULL.
  for (const k of Object.keys(obj)) {
    if (obj[k] === '') delete obj[k];
  }
  // Convert numeric fields.
  for (const numField of [
    'birth_year', 'death_year', 'person_id', 'source_id', 'event_id',
    'person_a_id', 'person_b_id', 'strength',
    'char_event_id', 'char_source_id', 'char_strength', 'char_confidence_score',
    'confidence_score',
    'ideology_score', 'stance_on_union', 'stance_on_states_rights',
    'stance_on_slavery', 'stance_on_secession',
  ]) {
    if (obj[numField] != null && obj[numField] !== '') {
      const n = Number(obj[numField]);
      if (!Number.isNaN(n)) obj[numField] = n;
    }
  }
  return obj;
}

// --- Person form ---
const personForm = document.getElementById('personForm');
const personPicker = document.getElementById('personPicker');

personPicker.addEventListener('change', async () => {
  const id = personPicker.value;
  if (!id) {
    personForm.reset();
    return;
  }
  try {
    const p = await fetchJSON(`/api/people/${id}`);
    for (const el of personForm.elements) {
      if (!el.name) continue;
      if (el.type === 'checkbox') {
        el.checked = Boolean(p[el.name]);
      } else if (p[el.name] != null) {
        el.value = p[el.name];
      } else {
        el.value = '';
      }
    }
  } catch (e) {
    setStatus(`Load failed: ${e.message}`, 'err');
  }
});

personForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const body = formData(personForm);
  const id = personPicker.value;
  try {
    if (id) {
      const res = await fetchJSON(`/api/people/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus(`Updated person ${res.person_id}: ${res.display_name || res.full_name}`, 'ok');
      await reloadAll();
      personPicker.value = String(id);
      clearStatusSoon();
      return;
    }

    // Creating new: try once; on 409 show dedupe dialog.
    try {
      const res = await fetchJSON('/api/people', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setStatus(`Created person ${res.person_id}: ${res.display_name || res.full_name}`, 'ok');
      personForm.reset();
      await reloadAll();
      clearStatusSoon();
    } catch (e) {
      if (e.status === 409 && e.body && e.body.detail && e.body.detail.candidates) {
        openDupeDialog(e.body.detail.candidates, body);
        return;
      }
      throw e;
    }
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
    clearStatusSoon();
  }
});

// --- Duplicate-check dialog ---
const dupeDialog = document.getElementById('dupeDialog');
const dupeCandidatesEl = document.getElementById('dupeCandidates');
let pendingPersonBody = null;

function openDupeDialog(candidates, submittedBody) {
  pendingPersonBody = submittedBody;
  dupeCandidatesEl.innerHTML = '';
  for (const c of candidates) {
    const card = document.createElement('div');
    card.className = 'dupeCard';
    const name = c.display_name || c.full_name || '(unnamed)';
    const years = (c.birth_year || c.death_year)
      ? `${c.birth_year ?? '?'}–${c.death_year ?? '?'}`
      : '';
    const conflictBadge = c.year_conflict ? '<span class="badge warn">year conflict</span>' : '';
    const matchBadge = c.match_kind === 'alias'
      ? `<span class="badge">alias: ${escapeHtml(c.matched_on)}</span>`
      : `<span class="badge">name match</span>`;
    card.innerHTML = `
      <div>
        <div class="name">${escapeHtml(name)} <span class="meta">— id ${c.person_id}</span></div>
        <div class="meta">
          ${years ? escapeHtml(years) + ' · ' : ''}
          ${c.occupation ? escapeHtml(c.occupation) + ' · ' : ''}
          ${c.home_region_sc_code ? escapeHtml(c.home_region_sc_code) : ''}
          ${matchBadge} ${conflictBadge}
        </div>
      </div>
      <button type="button" class="primaryBtn" data-person-id="${c.person_id}">Merge into this</button>
    `;
    card.querySelector('button').addEventListener('click', () => mergeIntoPerson(c.person_id));
    dupeCandidatesEl.appendChild(card);
  }
  dupeDialog.classList.remove('hidden');
}

function closeDupeDialog() {
  dupeDialog.classList.add('hidden');
  pendingPersonBody = null;
}

async function mergeIntoPerson(personId) {
  if (!pendingPersonBody) return;
  try {
    const res = await fetchJSON(`/api/people/${personId}/merge`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pendingPersonBody),
    });
    const fields = (res._merge_fields || []).join(', ');
    if (res._merge_status === 'no_changes') {
      setStatus(`Person ${res.person_id} already had all the info you entered. No changes made.`, 'ok');
    } else {
      setStatus(`Merged into person ${res.person_id}${fields ? ` — filled: ${fields}` : ''}`, 'ok');
    }
    closeDupeDialog();
    personForm.reset();
    await reloadAll();
    // Leave the picker on the merged person so the user can review/extend.
    personPicker.value = String(res.person_id);
    personPicker.dispatchEvent(new Event('change'));
    clearStatusSoon();
  } catch (e) {
    setStatus(`Merge failed: ${e.message}`, 'err');
  }
}

async function createPersonAnyway() {
  if (!pendingPersonBody) return;
  try {
    const res = await fetchJSON('/api/people?force=true', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pendingPersonBody),
    });
    setStatus(`Created person ${res.person_id}: ${res.display_name || res.full_name}`, 'ok');
    closeDupeDialog();
    personForm.reset();
    await reloadAll();
    clearStatusSoon();
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
  }
}

document.getElementById('dupeClose').addEventListener('click', closeDupeDialog);
document.getElementById('dupeCancel').addEventListener('click', closeDupeDialog);
document.getElementById('dupeCreateAnyway').addEventListener('click', createPersonAnyway);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !dupeDialog.classList.contains('hidden')) closeDupeDialog();
});

// --- Source form ---
const sourceForm = document.getElementById('sourceForm');
sourceForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const body = formData(sourceForm);
  try {
    const res = await fetchJSON('/api/sources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    setStatus(`Created source ${res.source_id}: ${res.title}`, 'ok');
    sourceForm.reset();
    await reloadAll();
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
  }
  clearStatusSoon();
});

// --- Position form ---
const positionForm = document.getElementById('positionForm');
positionForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const body = formData(positionForm);
  try {
    const res = await fetchJSON('/api/positions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    setStatus(`Created position ${res.position_id} for person ${res.person_id}`, 'ok');
    positionForm.reset();
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
  }
  clearStatusSoon();
});

// --- Alias form ---
const aliasForm = document.getElementById('aliasForm');
aliasForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const body = formData(aliasForm);
  try {
    const res = await fetchJSON('/api/aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    setStatus(`Added alias ${res.alias_id} for person ${res.person_id}`, 'ok');
    aliasForm.reset();
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
  }
  clearStatusSoon();
});

// --- Relationship form ---
const relationshipForm = document.getElementById('relationshipForm');
relationshipForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const body = formData(relationshipForm);
  if (body.person_a_id != null && body.person_b_id != null && body.person_a_id === body.person_b_id) {
    setStatus('Person A and Person B must be different.', 'err');
    return;
  }
  try {
    const res = await fetchJSON('/api/relationships', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const rel = res.relationship || {};
    const extra = res.characterization_id ? ` + characterization ${res.characterization_id}` : '';
    setStatus(`Created relationship ${rel.relationship_id} (${rel.person_low_id}↔${rel.person_high_id})${extra}`, 'ok');
    relationshipForm.reset();
  } catch (e) {
    setStatus(`Save failed: ${e.message}`, 'err');
  }
  clearStatusSoon();
});

// --- Init ---
(async function init() {
  try {
    await reloadAll();
    setStatus(`Ready. ${people.length} people, ${sources.length} sources loaded.`, 'ok');
    clearStatusSoon();
  } catch (e) {
    setStatus(`Init failed: ${e.message}`, 'err');
  }
})();
