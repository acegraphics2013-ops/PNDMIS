var state = {
  page: 1, search: '', category: '', classification: '', status: '', priority: '',
  sort: '-created_at', selected: {}, pending: null, statusOnly: false
};
var CAN_BULK = document.body.getAttribute('data-can-bulk') === '1';

function $(id) { return document.getElementById(id); }
function qs(obj) {
  return Object.keys(obj).filter(function (k) { return obj[k] !== '' && obj[k] !== null; })
    .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]); }).join('&');
}
function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
function refreshIcons() { if (window.lucide && lucide.createIcons) lucide.createIcons(); }
function badgeClass(value) {
  return ({ approved: 'b-ok', verified: 'b-info', submitted: 'b-info', review: 'b-soon',
    pending: 'b-done', returned: 'b-overdue', archived: 'b-done', progress: 'b-info',
    completed: 'b-ok', critical: 'b-overdue', high: 'b-soon', normal: 'b-done' })[value] || 'b-info';
}
function skeleton() {
  var h = '';
  for (var i = 0; i < 5; i++) {
    h += '<tr><td></td><td><div class="skel" style="width:65%"></div></td><td><div class="skel" style="width:24px"></div></td><td><div class="skel" style="width:70px"></div></td><td><div class="skel" style="width:80px"></div></td><td><div class="skel" style="width:70px"></div></td><td><div class="skel" style="width:60px"></div></td><td><div class="skel" style="width:70px"></div></td><td><div class="skel" style="width:70px"></div></td><td><div class="skel" style="width:120px"></div></td></tr>';
  }
  return h;
}

async function load() {
  var tb = $('rows'); if (!tb) return;
  tb.innerHTML = skeleton();
  state.selected = {};
  updateBulkBar();
  try {
    var j = await api('/api/records/?' + qs(state));
    if (!j.results.length) {
      tb.innerHTML = '<tr><td colspan="10"><div class="empty"><h3>No records found</h3><p>Try changing filters or create a new record.</p></div></td></tr>';
    } else {
      tb.innerHTML = j.results.map(function (r) {
        var actions = '<button class="btn ghost sm" type="button" onclick="openView(' + r.id + ')" aria-label="View record ' + r.id + '">View</button>';
        if (r.can_edit) actions += ' <button class="btn ghost sm" type="button" onclick="openEdit(' + r.id + ')" aria-label="Edit record ' + r.id + '">Edit</button>';
        if (r.status === 'archived' && r.can_restore) {
          actions += ' <button class="btn ghost sm" type="button" onclick="restoreRecord(' + r.id + ')" aria-label="Restore record ' + r.id + '">Restore</button>';
        } else if (r.can_archive) {
          actions += ' <button class="btn ghost sm" type="button" onclick="askDelete(' + r.id + ',\'archive\')" aria-label="Archive record ' + r.id + '">Archive</button>';
        }
        if (r.can_delete) actions += ' <button class="btn danger sm" type="button" onclick="askDelete(' + r.id + ',\'delete\')" aria-label="Delete record ' + r.id + '">Delete</button>';
        return '<tr>' +
          (CAN_BULK ? '<td class="check-col"><input type="checkbox" class="row-check" value="' + r.id + '" aria-label="Select record ' + r.id + '"></td>' : '') +
          '<td><b>' + escapeHtml(r.name) + '</b>' + (r.overdue ? ' <span class="badge b-overdue">Overdue</span>' : '') + '</td>' +
          '<td>' + r.id + '</td>' +
          '<td>' + escapeHtml(r.unit) + '</td>' +
          '<td>' + escapeHtml(r.classification) + '</td>' +
          '<td><span class="badge ' + badgeClass(r.status) + '">' + escapeHtml(r.status_display) + '</span></td>' +
          '<td><span class="badge ' + badgeClass(r.priority) + '">' + escapeHtml(r.priority_display) + '</span></td>' +
          '<td>' + escapeHtml(r.due_date || '—') + '</td>' +
          '<td>' + escapeHtml(r.assignee) + '</td>' +
          '<td class="actions">' + actions + '</td></tr>';
      }).join('');
    }
    var totalPages = Math.max(j.pages || 1, 1);
    $('pager').innerHTML = '<span>' + j.total + ' record' + (j.total === 1 ? '' : 's') + ' · page ' + j.page + ' of ' + totalPages + '</span>' +
      '<span class="pager-actions"><button class="btn ghost sm" type="button" ' + (j.page <= 1 ? 'disabled' : '') + ' onclick="go(' + (j.page - 1) + ')">Prev</button>' +
      '<button class="btn ghost sm" type="button" ' + (j.page >= totalPages ? 'disabled' : '') + ' onclick="go(' + (j.page + 1) + ')">Next</button></span>';
    refreshIcons();
    bindChecks();
  } catch (e) {
    tb.innerHTML = '<tr><td colspan="10"><div class="empty"><h3>Could not load records</h3><p>' + escapeHtml(e.message) + '</p><button class="btn ghost sm" type="button" onclick="load()">Retry</button></div></td></tr>';
    toast(e.message, true);
  }
}

function bindChecks() {
  document.querySelectorAll('.row-check').forEach(function (box) {
    box.addEventListener('change', function () {
      if (box.checked) state.selected[box.value] = true; else delete state.selected[box.value];
      updateBulkBar();
    });
  });
  var all = $('check-all');
  if (all) {
    all.checked = false;
    all.onchange = function () {
      document.querySelectorAll('.row-check').forEach(function (box) {
        box.checked = all.checked;
        if (all.checked) state.selected[box.value] = true; else delete state.selected[box.value];
      });
      updateBulkBar();
    };
  }
}
function selectedIds() { return Object.keys(state.selected); }
function updateBulkBar() {
  var ids = selectedIds();
  var bar = $('bulk-bar');
  if (bar) bar.hidden = ids.length === 0;
  var count = $('bulk-count'); if (count) count.textContent = ids.length;
}
function clearSelection() {
  state.selected = {};
  document.querySelectorAll('.row-check').forEach(function (b) { b.checked = false; });
  var all = $('check-all'); if (all) all.checked = false;
  updateBulkBar();
}
function go(page) { state.page = page; load(); }
var searchTimer;
function debounceSearch(value) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(function () { state.search = value; state.page = 1; load(); }, 300);
}
function readFilters() {
  state.category = $('f-cat') ? $('f-cat').value : '';
  state.classification = $('f-class') ? $('f-class').value : '';
  state.status = $('f-status') ? $('f-status').value : '';
  state.priority = $('f-prio') ? $('f-prio').value : '';
}
function onFilter() { readFilters(); state.page = 1; load(); }
function resetFilters() {
  ['f-cat', 'f-class', 'f-status', 'f-prio', 'q'].forEach(function (id) { if ($(id)) $(id).value = ''; });
  state.search = state.category = state.classification = state.status = state.priority = '';
  state.page = 1; load();
}
function onSort(field) {
  var key = ({ name: 'name', status: 'status', priority: 'priority', date: 'due_date' })[field] || field;
  state.sort = state.sort === key ? '-' + key : key;
  load();
}
function openModal() { $('modal').classList.add('open'); setTimeout(function () { var f = $('f-name'); if (f && !f.disabled) f.focus(); }, 50); }
function closeModal() {
  ['modal', 'view-modal', 'del-modal'].forEach(function (id) { var el = $(id); if (el) el.classList.remove('open'); });
  if (window.lucide && lucide.createIcons) lucide.createIcons();
}
function openAdd() {
  state.statusOnly = false;
  $('m-title').textContent = 'Add record';
  $('record-form').reset();
  $('f-id').value = '';
  $('f-due').value = '';
  $('f-prio').value = 'normal';
  $('f-status2').value = 'pending';
  $('e-name').hidden = true;
  $('form-errors').hidden = true;
  enableFields(true);
  openModal();
}
function enableFields(enabled) {
  ['f-cat2', 'f-class2', 'f-assignee', 'f-due', 'f-prio', 'f-status2', 'f-desc'].forEach(function (id) {
    if ($(id)) $(id).disabled = !enabled;
  });
  var name = $('f-name'); if (name) name.disabled = !enabled;
}
async function openView(id) {
  var body = $('view-body');
  body.innerHTML = '<div class="empty"><span class="spin"></span> Loading…</div>';
  $('view-modal').classList.add('open');
  try {
    var j = await api('/api/records/' + id + '/');
    var r = j.record;
    var history = (j.history || []).map(function (h) {
      return '<tr><td>' + escapeHtml((h.occurred_at || '').replace('T', ' ').slice(0, 16)) + '</td><td>' + escapeHtml(h.actor__username) + '</td><td>' + escapeHtml(h.event) + '</td></tr>';
    }).join('');
    body.innerHTML = '<dl class="detail-list">' +
      '<div><dt>Record</dt><dd>' + escapeHtml(r.name) + '</dd></div>' +
      '<div><dt>ID</dt><dd>#' + r.id + '</dd></div>' +
      '<div><dt>Unit</dt><dd>' + escapeHtml(r.unit) + '</dd></div>' +
      '<div><dt>Classification</dt><dd>' + escapeHtml(r.classification) + '</dd></div>' +
      '<div><dt>Status</dt><dd><span class="badge ' + badgeClass(r.status) + '">' + escapeHtml(r.status_display) + '</span></dd></div>' +
      '<div><dt>Priority</dt><dd><span class="badge ' + badgeClass(r.priority) + '">' + escapeHtml(r.priority_display) + '</span></dd></div>' +
      '<div><dt>Due date</dt><dd>' + escapeHtml(r.due_date || '—') + '</dd></div>' +
      '<div><dt>Assigned to</dt><dd>' + escapeHtml(r.assignee) + '</dd></div>' +
      '<div><dt>Created by</dt><dd>' + escapeHtml(r.created_by) + '</dd></div>' +
      '<div><dt>Created</dt><dd>' + escapeHtml((r.created || '').replace('T', ' ').slice(0, 16)) + '</dd></div>' +
      '<div class="wide"><dt>Description</dt><dd>' + (r.description ? escapeHtml(r.description) : '<span class="meta">No description</span>') + '</dd></div>' +
      '</dl>' +
      '<h4>Record history</h4>' + (history ? '<div class="twrap"><table><thead><tr><th>When</th><th>Actor</th><th>Event</th></tr></thead><tbody>' + history + '</tbody></table></div>' : '<p class="meta">No history recorded for this record.</p>');
    refreshIcons();
  } catch (e) {
    body.innerHTML = '<div class="empty"><h3>Unable to load record</h3><p>' + escapeHtml(e.message) + '</p></div>';
  }
}
async function openEdit(id) {
  try {
    var j = await api('/api/records/' + id + '/');
    var r = j.record;
    state.statusOnly = !!r.status_only;
    $('m-title').textContent = 'Edit record #' + r.id;
    $('f-id').value = r.id;
    $('f-name').value = r.name;
    $('f-desc').value = r.description;
    $('f-due').value = r.due_date || '';
    $('f-prio').value = r.priority;
    $('f-status2').value = r.status;
    $('f-cat2').value = r.category_id || '';
    $('f-class2').value = r.classification_id || '';
    $('f-assignee').value = r.assignee_id || '';
    $('e-name').hidden = true;
    $('form-errors').hidden = true;
    enableFields(!state.statusOnly);
    openModal();
  } catch (e) { toast(e.message, true); }
}
function askDelete(id, mode) {
  state.pending = { type: 'single', id: id, mode: mode };
  $('d-title').textContent = mode === 'delete' ? 'Delete record permanently?' : 'Archive record?';
  $('del-text').textContent = mode === 'delete'
    ? 'This permanently deletes the record and cannot be undone. The action is audited.'
    : 'The record will be archived and can be restored later.';
  $('del-confirm').innerHTML = mode === 'delete' ? '<i data-lucide="trash-2"></i> Delete' : '<i data-lucide="archive"></i> Archive';
  $('del-modal').classList.add('open');
  refreshIcons();
}
function bulkAction(action) {
  if (!selectedIds().length) return;
  if (action === 'delete' || action === 'archive') {
    state.pending = { type: 'bulk', mode: action };
    $('d-title').textContent = action === 'delete' ? 'Delete selected records?' : 'Archive selected records?';
    $('del-text').textContent = action === 'delete'
      ? 'Permanent deletion is restricted to supervisors and is audited. This cannot be undone.'
      : 'Selected records will be archived and can be restored later.';
    $('del-confirm').innerHTML = action === 'delete' ? '<i data-lucide="trash-2"></i> Delete' : '<i data-lucide="archive"></i> Archive';
    $('del-modal').classList.add('open');
    refreshIcons();
    return;
  }
  executeBulk(action);
}
async function executeBulk(action) {
  var ids = selectedIds();
  if (!ids.length) return;
  try {
    await api('/api/records/bulk/', { method: 'POST', body: JSON.stringify({ action: action, ids: ids }) });
    closeModal();
    toast('Bulk ' + action + ' completed');
    load();
  } catch (e) { toast(e.message, true); }
}
async function doDelete() {
  var pending = state.pending;
  if (!pending) return;
  if (pending.type === 'bulk') {
    state.pending = null;
    $('del-modal').classList.remove('open');
    return executeBulk(pending.mode);
  }
  try {
    if (pending.mode === 'delete') {
      await api('/api/records/' + pending.id + '/', { method: 'DELETE' });
      toast('Record deleted');
    } else {
      await api('/api/records/' + pending.id + '/archive/', { method: 'POST' });
      toast('Record archived');
    }
    state.pending = null;
    closeModal();
    load();
  } catch (e) { toast(e.message, true); }
}
async function restoreRecord(id) {
  try {
    await api('/api/records/' + id + '/restore/', { method: 'POST' });
    toast('Record restored');
    load();
  } catch (e) { toast(e.message, true); }
}
function showFormErrors(err) {
  var box = $('form-errors');
  var lines = [];
  if (err && err.errors) {
    Object.keys(err.errors).forEach(function (field) {
      var entries = err.errors[field] || [];
      entries.forEach(function (entry) {
        lines.push((field === '__all__' ? '' : field.replace(/_/g, ' ') + ': ') + (entry.message || entry));
      });
    });
  }
  if (!lines.length) lines = [err.message || 'The record could not be saved.'];
  box.innerHTML = lines.map(function (line) { return '<div>' + escapeHtml(line) + '</div>'; }).join('');
  box.hidden = false;
}
async function saveForm(ev) {
  ev.preventDefault();
  var name = $('f-name').value.trim();
  var valid = name.length >= 3 || state.statusOnly;
  $('e-name').hidden = valid;
  if (!valid) { $('f-name').focus(); toast('Record name must be at least 3 characters', true); return; }
  if (!state.statusOnly && !$('f-due').value) { toast('Due date is required', true); $('f-due').focus(); return; }
  var id = $('f-id').value;
  var body;
  if (state.statusOnly) {
    body = { status: $('f-status2').value };
  } else {
    body = {
      title: name,
      description: $('f-desc').value,
      unit: $('f-cat2').value || null,
      category: $('f-class2').value || null,
      assignee: $('f-assignee').value || null,
      due_date: $('f-due').value,
      priority: $('f-prio').value,
      status: $('f-status2').value
    };
  }
  var buttons = document.querySelectorAll('#record-form .btn');
  buttons.forEach(function (b) { b.disabled = true; });
  $('form-errors').hidden = true;
  try {
    if (id) {
      await api('/api/records/' + id + '/', { method: 'PUT', body: JSON.stringify(body) });
      toast('Record updated');
    } else {
      await api('/api/records/', { method: 'POST', body: JSON.stringify(body) });
      toast('Record created');
    }
    closeModal();
    load();
  } catch (e) {
    showFormErrors(e);
    toast(e.message, true);
  } finally {
    buttons.forEach(function (b) { b.disabled = false; });
  }
}

document.addEventListener('DOMContentLoaded', function () {
  try {
    var u = new URLSearchParams(window.location.search);
    var search = u.get('search') || '';
    if (search) {
      state.search = search;
      if ($('q')) $('q').value = search;
      if ($('top-search')) $('top-search').value = search;
    }
  } catch (e) {}
  var q = $('q'); if (q) q.addEventListener('input', function () { debounceSearch(this.value); });
  ['f-cat', 'f-class', 'f-status', 'f-prio'].forEach(function (id) {
    if ($(id)) $(id).addEventListener('change', onFilter);
  });
  document.querySelectorAll('.sortable').forEach(function (th) {
    th.addEventListener('click', function () { onSort(th.getAttribute('data-sort')); });
  });
  document.querySelectorAll('.modal').forEach(function (m) {
    m.addEventListener('click', function (e) { if (e.target === m) closeModal(); });
  });
  var form = $('record-form');
  if (form) form.addEventListener('submit', function () {
    var buttons = form.querySelectorAll('.btn');
    buttons.forEach(function (b) { b.disabled = true; });
  });
  if (window.lucide && lucide.createIcons) lucide.createIcons();
  load();
});
