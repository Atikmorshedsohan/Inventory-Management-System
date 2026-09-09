/**
 * Users & Roles page.
 * Admins change roles inline; everyone else gets a read-only directory.
 * Base helpers (API_URL, token, userRole, currentUserData, formatDate,
 * renderActivityLog, fetchUserActivity, escapeHtml) come from base.js.
 */

let users = [];
let roleChoices = [];

setActiveNav('usersNav');

function isAdmin() {
  return userRole === 'admin';
}

async function loadRoleChoices() {
  try {
    const res = await fetch(`${API_URL}/users/roles/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;
    roleChoices = await res.json();

    const filter = document.getElementById('roleFilter');
    filter.innerHTML = '<option value="">All roles</option>';
    roleChoices.forEach((r) => {
      const opt = document.createElement('option');
      opt.value = r.value;
      opt.textContent = r.label;
      filter.appendChild(opt);
    });
  } catch (e) {
    console.error('Failed to load roles:', e);
  }
}

async function loadUsers() {
  const body = document.getElementById('usersBody');
  body.innerHTML = '<tr><td colspan="6" class="loading">Loading users…</td></tr>';
  try {
    const res = await fetch(`${API_URL}/users/?page_size=500&ordering=name`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');

    const data = await res.json();
    users = data.results || data;
    renderSummary();
    renderUsers();
  } catch (e) {
    console.error(e);
    body.innerHTML = '<tr><td colspan="6" class="error">Failed to load users</td></tr>';
  }
}

function renderSummary() {
  const counts = { admin: 0, manager: 0, staff: 0, viewer: 0 };
  users.forEach((u) => {
    if (Object.prototype.hasOwnProperty.call(counts, u.role)) counts[u.role] += 1;
  });
  document.getElementById('statTotal').textContent = users.length;
  document.getElementById('statAdmin').textContent = counts.admin;
  document.getElementById('statManager').textContent = counts.manager;
  document.getElementById('statStaff').textContent = counts.staff;
  document.getElementById('statViewer').textContent = counts.viewer;
}

function visibleUsers() {
  const q = document.getElementById('searchInput').value.trim().toLowerCase();
  const role = document.getElementById('roleFilter').value;
  return users.filter((u) => {
    if (role && u.role !== role) return false;
    if (!q) return true;
    return [u.name, u.email, u.department].some(
      (v) => (v || '').toLowerCase().includes(q)
    );
  });
}

function roleCell(user, isSelf) {
  const badge = `<span class="role-badge role-${user.role}">${escapeHtml(user.role_display || user.role)}</span>`;

  // Nobody edits their own role; non-admins get the badge only.
  if (!isAdmin() || isSelf) {
    return badge + (isSelf ? '<div class="role-note">Ask another admin to change this</div>' : '');
  }

  const options = roleChoices
    .map((r) => `<option value="${r.value}" ${r.value === user.role ? 'selected' : ''}>${escapeHtml(r.label)}</option>`)
    .join('');
  return `
    <select class="role-select" data-user="${user.user_id}" data-current="${user.role}"
            onchange="onRoleChange(this)">
      ${options}
    </select>
  `;
}

function renderUsers() {
  const body = document.getElementById('usersBody');
  const rows = visibleUsers();

  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">No users match this view</td></tr>';
    return;
  }

  const myId = currentUserData?.user_id;
  body.innerHTML = rows.map((u) => {
    const isSelf = u.user_id === myId;
    return `
      <tr class="${u.is_active === false ? 'row-inactive' : ''}">
        <td>
          <strong>${escapeHtml(u.name)}</strong>
          ${isSelf ? '<span class="you-badge">You</span>' : ''}
          ${u.is_active === false ? '<span class="you-badge inactive">Inactive</span>' : ''}
        </td>
        <td>${escapeHtml(u.email)}</td>
        <td>${escapeHtml(u.department || '—')}</td>
        <td>${roleCell(u, isSelf)}</td>
        <td>${u.created_at ? formatDate(u.created_at) : '—'}</td>
        <td>
          <button class="btn btn-secondary btn-sm"
                  onclick="openActivityModal(${u.user_id}, '${escapeHtml(u.name).replace(/'/g, "\\'")}')">
            View
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function onRoleChange(select) {
  const userId = parseInt(select.dataset.user, 10);
  const previous = select.dataset.current;
  const next = select.value;
  const user = users.find((u) => u.user_id === userId);

  if (next === previous) return;

  const label = roleChoices.find((r) => r.value === next)?.label || next;
  if (!confirm(`Change ${user?.name || 'this user'}'s role to ${label}?`)) {
    select.value = previous;
    return;
  }

  select.disabled = true;
  try {
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    const res = await fetch(`${API_URL}/users/${userId}/set_role/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ role: next })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not change the role');

    if (user) {
      user.role = data.role;
      user.role_display = data.role_display;
    }
    select.dataset.current = data.role;
    renderSummary();
    showToast(`${data.name} is now ${data.role_display}`);
  } catch (e) {
    select.value = previous;
    alert(`Error: ${e.message}`);
  } finally {
    select.disabled = false;
  }
}

function showToast(message) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

async function openActivityModal(userId, name) {
  document.getElementById('activityTitle').textContent = `Activity — ${name}`;
  document.getElementById('activityMeta').textContent = '';
  const list = document.getElementById('userActivityList');
  list.innerHTML = '<li class="act-empty">Loading…</li>';
  document.getElementById('activityModal').classList.add('show');

  try {
    const data = await fetchUserActivity(userId, 25);
    renderActivityLog(list, data.results, `${name} has no recorded activity yet`);
    const shown = data.results.length;
    document.getElementById('activityMeta').textContent =
      data.total > shown ? `Showing the latest ${shown} of ${data.total}` : `${data.total} record(s)`;
  } catch (e) {
    list.innerHTML = '<li class="act-empty">Could not load activity</li>';
  }
}

function closeActivityModal() {
  document.getElementById('activityModal').classList.remove('show');
}

document.addEventListener('DOMContentLoaded', async () => {
  setActiveNav('usersNav');
  await loadUserProfile();          // populates userRole + currentUserData

  if (!isAdmin()) {
    document.getElementById('permissionNotice').classList.remove('hidden');
  }

  document.getElementById('searchInput').addEventListener('input', renderUsers);
  document.getElementById('roleFilter').addEventListener('change', renderUsers);

  await loadRoleChoices();
  await loadUsers();
});
