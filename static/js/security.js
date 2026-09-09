/**
 * Security & Access page (admin only).
 *  - Permission matrix, computed server-side from the live permission classes.
 *  - Login activity: who signed in, when, and from where.
 * Base helpers come from base.js.
 */

let matrix = null;
let loginEvents = [];
let loginPage = 1;
const eventsPerPage = 40;
let searchDebounce = null;

setActiveNav('securityNav');

const ROLE_KEYS = ['admin', 'manager', 'staff', 'viewer'];

function showTab(which) {
  const isPerms = which === 'permissions';
  document.getElementById('panelPermissions').classList.toggle('hidden', !isPerms);
  document.getElementById('panelLogins').classList.toggle('hidden', isPerms);
  document.getElementById('tabPermissions').classList.toggle('active', isPerms);
  document.getElementById('tabLogins').classList.toggle('active', !isPerms);
}

/* ============ Permission matrix ============ */

async function loadMatrix() {
  try {
    const res = await fetch(`${API_URL}/access/matrix/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');
    matrix = await res.json();
    renderRoleLegend();
    renderMatrix();
    renderActions();
  } catch (e) {
    console.error(e);
    document.getElementById('matrixBody').innerHTML =
      '<tr><td colspan="6" class="error">Failed to load the permission matrix</td></tr>';
  }
}

function renderRoleLegend() {
  document.getElementById('roleLegend').innerHTML = matrix.roles.map((r) => `
    <div class="role-card role-${r.key}">
      <div class="role-name">${escapeHtml(r.label)}</div>
      <div class="role-summary">${escapeHtml(r.summary)}</div>
    </div>
  `).join('');

  document.getElementById('matrixNotes').innerHTML =
    matrix.notes.map((n) => `<li>${escapeHtml(n)}</li>`).join('');
}

function methodChips(methodMap) {
  return matrix.methods.map((m) => {
    const allowed = methodMap[m];
    const cls = allowed === null ? 'unknown' : (allowed ? 'yes' : 'no');
    return `<span class="chip ${cls}" title="${m}: ${allowed === null ? 'unknown' : (allowed ? 'allowed' : 'denied')}">${m}</span>`;
  }).join('');
}

function renderMatrix() {
  document.getElementById('matrixBody').innerHTML = matrix.resources.map((r) => `
    <tr>
      <td>
        <strong>${escapeHtml(r.label)}</strong>
        <div class="path">${escapeHtml(r.path)}</div>
      </td>
      ${ROLE_KEYS.map((role) => `<td class="chips">${methodChips(r.roles[role])}</td>`).join('')}
      <td class="enforced">${r.enforced_by.map((c) => `<code>${escapeHtml(c)}</code>`).join(' + ')}</td>
    </tr>
  `).join('');
}

function tick(allowed) {
  return allowed
    ? '<span class="mark yes" aria-label="allowed">✓</span>'
    : '<span class="mark no" aria-label="denied">✕</span>';
}

function renderActions() {
  document.getElementById('actionsBody').innerHTML = matrix.actions.map((a) => `
    <tr>
      <td><strong>${escapeHtml(a.label)}</strong></td>
      <td><code class="endpoint">${escapeHtml(a.endpoint)}</code></td>
      ${ROLE_KEYS.map((role) => `<td class="ctr">${tick(a.roles[role])}</td>`).join('')}
      <td class="source"><code>${escapeHtml(a.source)}</code></td>
    </tr>
  `).join('');
}

/* ============ Login activity ============ */

function loginFilters() {
  const params = {};
  const search = document.getElementById('searchInput').value.trim();
  const event = document.getElementById('eventFilter').value;
  const user = document.getElementById('userFilter').value;
  const from = document.getElementById('dateFrom').value;
  const to = document.getElementById('dateTo').value;
  if (search) params.search = search;
  if (event) params.event = event;
  if (user) params.user = user;
  if (from) params.date_from = from;
  if (to) params.date_to = to;
  return params;
}

async function loadLoginSummary() {
  try {
    const res = await fetch(`${API_URL}/login-events/summary/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('statLogins').textContent = data.successful_logins;
    document.getElementById('statFailed').textContent = data.failed_logins;
    document.getElementById('statFailedRecent').textContent = data.failed_recent;
    document.getElementById('statIps').textContent = data.distinct_ips;
    document.getElementById('statEvents').textContent = data.total_events;

    const body = document.getElementById('lastSeenBody');
    if (!data.users.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty">Nobody has signed in yet</td></tr>';
      return;
    }
    body.innerHTML = data.users.map((u) => `
      <tr>
        <td><strong>${escapeHtml(u.name)}</strong><div class="path">${escapeHtml(u.email)}</div></td>
        <td><span class="role-badge role-${u.role}">${escapeHtml(u.role)}</span></td>
        <td class="ctr">${u.logins}</td>
        <td>${u.last_login ? formatDate(u.last_login) : '—'}</td>
        <td><code>${escapeHtml(u.last_ip || '—')}</code></td>
        <td>${escapeHtml(u.last_client || '—')}</td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Failed to load login summary:', e);
  }
}

async function loadLoginEvents() {
  const body = document.getElementById('loginBody');
  body.innerHTML = '<tr><td colspan="6" class="loading">Loading…</td></tr>';
  try {
    const query = new URLSearchParams({ ...loginFilters(), page_size: 500 });
    const res = await fetch(`${API_URL}/login-events/?${query}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');

    const data = await res.json();
    loginEvents = data.results || data;
    loginPage = 1;
    renderLoginEvents();
    renderLoginNote();
  } catch (e) {
    console.error(e);
    body.innerHTML = '<tr><td colspan="6" class="error">Failed to load login activity</td></tr>';
  }
}

function renderLoginNote() {
  const active = loginFilters();
  const note = document.getElementById('loginNote');
  const bits = Object.entries(active).map(([k, v]) => `${k.replace('_', ' ')}: ${v}`);
  note.textContent = bits.length
    ? `${loginEvents.length} event(s) — ${bits.join(', ')}`
    : `${loginEvents.length} event(s)`;
}

const EVENT_CLASS = { login: 'ok', failed: 'bad', logout: 'muted' };

function renderLoginEvents() {
  const body = document.getElementById('loginBody');
  if (!loginEvents.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">No sign-in activity matches this view</td></tr>';
    document.getElementById('loginPagination').style.display = 'none';
    return;
  }

  const start = (loginPage - 1) * eventsPerPage;
  const page = loginEvents.slice(start, start + eventsPerPage);

  body.innerHTML = page.map((e) => {
    const who = e.user_name
      ? `<strong>${escapeHtml(e.user_name)}</strong><div class="path">${escapeHtml(e.email || '')}</div>`
      : `<span class="unknown-user">${escapeHtml(e.email || 'unknown')}</span>
         <div class="path">no matching account</div>`;
    return `
      <tr class="${e.successful ? '' : 'row-failed'}">
        <td>${formatDate(e.timestamp)}</td>
        <td>${who}</td>
        <td><span class="event-badge ${EVENT_CLASS[e.event] || 'muted'}">${escapeHtml(e.event_display)}</span></td>
        <td><code>${escapeHtml(e.ip_address || '—')}</code></td>
        <td title="${escapeHtml(e.user_agent || '')}">${escapeHtml(e.client || '—')}</td>
        <td class="detail">${escapeHtml(e.reason || '')}</td>
      </tr>
    `;
  }).join('');

  renderLoginPagination();
}

function renderLoginPagination() {
  const totalPages = Math.ceil(loginEvents.length / eventsPerPage);
  const el = document.getElementById('loginPagination');
  if (totalPages <= 1) {
    el.style.display = 'none';
    return;
  }
  el.style.display = 'flex';
  el.innerHTML = '';

  const add = (label, page, disabled, active) => {
    const btn = document.createElement('button');
    btn.className = `page-btn${active ? ' active' : ''}`;
    btn.textContent = label;
    btn.disabled = !!disabled;
    btn.onclick = () => { loginPage = page; renderLoginEvents(); };
    el.appendChild(btn);
  };

  add('← Previous', loginPage - 1, loginPage === 1);
  for (let i = 1; i <= totalPages; i += 1) add(String(i), i, false, i === loginPage);
  add('Next →', loginPage + 1, loginPage === totalPages);
}

async function loadUserOptions() {
  try {
    const res = await fetch(`${API_URL}/users/?page_size=200&ordering=name`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById('userFilter');
    (data.results || data).forEach((u) => {
      const opt = document.createElement('option');
      opt.value = u.user_id;
      opt.textContent = u.name;
      select.appendChild(opt);
    });
  } catch (e) {
    console.error('Failed to load users:', e);
  }
}

function resetLoginFilters() {
  ['searchInput', 'eventFilter', 'userFilter', 'dateFrom', 'dateTo']
    .forEach((id) => { document.getElementById(id).value = ''; });
  loadLoginEvents();
}

function bindLoginFilters() {
  document.getElementById('searchInput').addEventListener('input', () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(loadLoginEvents, 300);
  });
  ['eventFilter', 'userFilter', 'dateFrom', 'dateTo'].forEach((id) => {
    document.getElementById(id).addEventListener('change', loadLoginEvents);
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  setActiveNav('securityNav');
  await loadUserProfile();

  if (userRole !== 'admin') {
    document.getElementById('deniedNotice').classList.remove('hidden');
    return;
  }

  document.getElementById('securityBody').classList.remove('hidden');
  bindLoginFilters();
  await loadMatrix();
  await loadUserOptions();
  await loadLoginSummary();
  await loadLoginEvents();
});
