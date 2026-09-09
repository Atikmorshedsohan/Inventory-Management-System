/**
 * Audit Log Viewer
 * Filtering (user / action type / date range) is done server-side via
 * /api/audit-logs/; paging over the returned set is done here.
 * Base helpers come from base.js.
 */

let allLogs = [];
let currentPage = 1;
const logsPerPage = 50;
let searchDebounce = null;

setActiveNav('auditNav');

const ACTION_LABELS = {
  stock: 'Stock movement',
  transfer: 'Transfer',
  reconcile: 'Reconciliation',
  role: 'Role change',
  approve: 'Approval',
  reject: 'Rejection',
  issue: 'Issued',
  return: 'Returned',
  create: 'Created',
  comment: 'Comment',
  auth: 'Account',
  update: 'Updated',
  delete: 'Deleted',
  other: 'Other'
};

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

/** Translate the period dropdown into concrete from/to dates. */
function periodToRange(period) {
  const today = new Date();
  const iso = (d) => d.toISOString().split('T')[0];
  if (period === 'today') return { date_from: iso(today), date_to: iso(today) };
  if (period === 'week') {
    const from = new Date(today);
    from.setDate(from.getDate() - 6);
    return { date_from: iso(from), date_to: iso(today) };
  }
  if (period === 'month') {
    return { date_from: iso(new Date(today.getFullYear(), today.getMonth(), 1)), date_to: iso(today) };
  }
  if (period === 'custom') {
    const from = document.getElementById('dateFrom').value;
    const to = document.getElementById('dateTo').value;
    const range = {};
    if (from) range.date_from = from;
    if (to) range.date_to = to;
    return range;
  }
  return {};
}

function currentFilters() {
  const params = { ...periodToRange(document.getElementById('periodFilter').value) };
  const search = document.getElementById('searchInput').value.trim();
  const user = document.getElementById('userFilter').value;
  const actionType = document.getElementById('actionTypeFilter').value;
  if (search) params.search = search;
  if (user) params.user = user;
  if (actionType) params.action_type = actionType;
  return params;
}

function filterQuery(extra = {}) {
  return new URLSearchParams({ ...currentFilters(), ...extra }).toString();
}

async function loadAuditLogs() {
  const loading = document.getElementById('loadingState');
  loading.style.display = 'block';
  document.getElementById('tableContainer').style.display = 'none';
  document.getElementById('emptyState').style.display = 'none';

  try {
    const res = await fetch(`${API_URL}/audit-logs/?${filterQuery({ page_size: 1000, ordering: '-timestamp' })}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');

    const data = await res.json();
    allLogs = data.results || data;
    currentPage = 1;

    renderSummary();
    renderFilterNote();
    renderLogs();
    loadActionTypes();
  } catch (e) {
    console.error('Error loading audit logs:', e);
    document.getElementById('emptyState').style.display = 'block';
  } finally {
    loading.style.display = 'none';
  }
}

function renderSummary() {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekStart = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const since = (start) => allLogs.filter((l) => new Date(l.timestamp) >= start).length;

  document.getElementById('statTotal').textContent = allLogs.length;
  document.getElementById('statToday').textContent = since(todayStart);
  document.getElementById('statWeek').textContent = since(weekStart);
  document.getElementById('statMonth').textContent = since(monthStart);
}

function renderFilterNote() {
  const note = document.getElementById('filterNote');
  if (!note) return;
  const active = currentFilters();
  const bits = [];
  if (active.user) {
    const sel = document.getElementById('userFilter');
    bits.push(`user: ${sel.options[sel.selectedIndex].textContent}`);
  }
  if (active.action_type) bits.push(`type: ${ACTION_LABELS[active.action_type] || active.action_type}`);
  if (active.date_from || active.date_to) {
    bits.push(`dates: ${active.date_from || 'any'} → ${active.date_to || 'any'}`);
  }
  if (active.search) bits.push(`search: "${active.search}"`);
  note.textContent = bits.length
    ? `Showing ${allLogs.length} record(s) — ${bits.join(', ')}`
    : `Showing all ${allLogs.length} record(s)`;
}

/** Populate the action-type dropdown with server-side counts. */
async function loadActionTypes() {
  const select = document.getElementById('actionTypeFilter');
  if (!select) return;
  const chosen = select.value;
  try {
    // Count against everything except the action-type filter itself, so the
    // dropdown still shows what you could switch to.
    const params = currentFilters();
    delete params.action_type;
    const res = await fetch(`${API_URL}/audit-logs/action_types/?${new URLSearchParams(params)}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    select.innerHTML = `<option value="">All Action Types (${data.total})</option>`;
    data.action_types
      .filter((t) => t.count > 0)
      .forEach((t) => {
        const opt = document.createElement('option');
        opt.value = t.key;
        opt.textContent = `${t.label} (${t.count})`;
        select.appendChild(opt);
      });
    select.value = chosen;
  } catch (e) {
    console.error('Failed to load action types:', e);
  }
}

async function loadUsers() {
  try {
    const res = await fetch(`${API_URL}/users/?page_size=200`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById('userFilter');
    (data.results || data).forEach((user) => {
      const option = document.createElement('option');
      option.value = user.user_id;
      option.textContent = user.name;
      select.appendChild(option);
    });
  } catch (e) {
    console.error('Failed to load users:', e);
  }
}

function renderLogs() {
  if (allLogs.length === 0) {
    document.getElementById('tableContainer').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
    document.getElementById('pagination').style.display = 'none';
    return;
  }

  document.getElementById('tableContainer').style.display = 'block';
  document.getElementById('emptyState').style.display = 'none';

  const start = (currentPage - 1) * logsPerPage;
  const pageLogs = allLogs.slice(start, start + logsPerPage);

  document.getElementById('logsBody').innerHTML = pageLogs
    .map((log) => {
      const type = log.action_type || 'other';
      return `
          <tr>
            <td>#${log.log_id}</td>
            <td>${escapeHtml(log.user_name || 'System')}</td>
            <td>
              <span class="action-type action-${type}">${ACTION_LABELS[type] || type}</span>
              <div class="action-text">${escapeHtml(log.action)}</div>
            </td>
            <td>${new Date(log.timestamp).toLocaleString()}</td>
          </tr>
        `;
    })
    .join('');

  renderPagination();
}

function renderPagination() {
  const totalPages = Math.ceil(allLogs.length / logsPerPage);
  const pagination = document.getElementById('pagination');

  if (totalPages <= 1) {
    pagination.style.display = 'none';
    return;
  }

  pagination.style.display = 'flex';
  pagination.innerHTML = '';

  const addBtn = (label, page, disabled, active) => {
    const btn = document.createElement('button');
    btn.className = `page-btn${active ? ' active' : ''}`;
    btn.textContent = label;
    btn.disabled = !!disabled;
    btn.onclick = () => {
      currentPage = page;
      renderLogs();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    pagination.appendChild(btn);
  };

  addBtn('← Previous', currentPage - 1, currentPage === 1);

  const maxButtons = 5;
  let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
  const endPage = Math.min(totalPages, startPage + maxButtons - 1);
  startPage = Math.max(1, endPage - maxButtons + 1);

  for (let i = startPage; i <= endPage; i += 1) {
    addBtn(String(i), i, false, i === currentPage);
  }

  addBtn('Next →', currentPage + 1, currentPage === totalPages);
}

async function exportAuditCsv() {
  try {
    const res = await fetch(`${API_URL}/audit-logs/export/?${filterQuery()}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `CSE_Audit_Log_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

function resetFilters() {
  document.getElementById('searchInput').value = '';
  document.getElementById('userFilter').value = '';
  document.getElementById('actionTypeFilter').value = '';
  document.getElementById('periodFilter').value = 'all';
  document.getElementById('dateFrom').value = '';
  document.getElementById('dateTo').value = '';
  document.getElementById('customRange').classList.add('hidden');
  loadAuditLogs();
}

function onPeriodChange() {
  const isCustom = document.getElementById('periodFilter').value === 'custom';
  document.getElementById('customRange').classList.toggle('hidden', !isCustom);
  // Wait for both dates before refetching a custom range.
  if (!isCustom) loadAuditLogs();
}

function bindFilters() {
  document.getElementById('searchInput').addEventListener('input', () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(loadAuditLogs, 300);
  });
  document.getElementById('userFilter').addEventListener('change', loadAuditLogs);
  document.getElementById('actionTypeFilter').addEventListener('change', loadAuditLogs);
  document.getElementById('periodFilter').addEventListener('change', onPeriodChange);
  document.getElementById('dateFrom').addEventListener('change', loadAuditLogs);
  document.getElementById('dateTo').addEventListener('change', loadAuditLogs);
}

/** Let other pages deep-link here, e.g. /audit/?user=3&action_type=stock */
function applyUrlFilters() {
  const params = new URLSearchParams(window.location.search);
  const set = (id, key) => {
    const value = params.get(key);
    const el = document.getElementById(id);
    if (value && el) el.value = value;
  };
  set('userFilter', 'user');
  set('actionTypeFilter', 'action_type');
  set('searchInput', 'search');

  if (params.get('date_from') || params.get('date_to')) {
    document.getElementById('periodFilter').value = 'custom';
    document.getElementById('customRange').classList.remove('hidden');
    set('dateFrom', 'date_from');
    set('dateTo', 'date_to');
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  setActiveNav('auditNav');
  loadUserProfile();
  bindFilters();
  await loadUsers();
  applyUrlFilters();
  loadAuditLogs();
});
