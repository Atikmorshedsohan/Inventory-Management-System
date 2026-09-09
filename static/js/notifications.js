/**
 * Notifications Page
 * Lists the current user's notifications with read/unread controls.
 * Base helpers (API_URL, token, csrftoken, escapeHtml, formatDate, logout,
 * loadNotificationBadge) come from base.js.
 */

let notifications = [];
let currentFilter = 'all';

const LEVEL_ICON = { info: 'ℹ️', success: '✅', warning: '⚠️', danger: '⛔' };
const CATEGORY_LABEL = {
  reorder: 'Reorder alert',
  transfer: 'Item transfer',
  import: 'Bulk import',
  general: 'Update',
};
const EMPTY_TEXT = {
  all: 'No notifications yet. Alerts about your requests, transfers and stock levels will show up here.',
  unread: "You're all caught up — no unread notifications.",
  reorder: 'No reorder alerts. Every item is above its minimum level.',
  transfer: 'No item-transfer notifications yet.',
  import: 'No bulk-import notifications yet.',
  general: 'No approval or status updates yet.',
};

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const then = new Date(dateStr).getTime();
  const secs = Math.round((Date.now() - then) / 1000);
  if (secs < 60) return 'just now';
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs === 1 ? '' : 's'} ago`;
  const days = Math.round(hrs / 24);
  if (days < 7) return `${days} day${days === 1 ? '' : 's'} ago`;
  return formatDate(dateStr);
}

async function loadNotifications() {
  const list = document.getElementById('notifList');
  list.innerHTML = '<li class="notif-status">Loading…</li>';

  currentFilter = document.getElementById('filterSelect').value;
  let query = '?page_size=200&ordering=-created_at';
  if (currentFilter === 'unread') query += '&is_read=false';
  else if (currentFilter !== 'all') query += `&category=${encodeURIComponent(currentFilter)}`;

  try {
    const res = await fetch(`${API_URL}/notifications/${query}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    notifications = data.results || data || [];
    render();
  } catch (e) {
    console.error('Failed to load notifications:', e);
    list.innerHTML = '<li class="notif-status error">Could not load notifications. Try Refresh.</li>';
    updateSummary(null);
  }
}

function updateSummary(unread) {
  const summary = document.getElementById('notifSummary');
  const markAllBtn = document.getElementById('markAllBtn');
  if (unread === null) {
    if (summary) summary.textContent = '';
    if (markAllBtn) markAllBtn.hidden = true;
    return;
  }
  if (summary) {
    summary.textContent = unread
      ? `${unread} unread`
      : (notifications.length ? 'All read' : '');
  }
  if (markAllBtn) markAllBtn.hidden = unread === 0;
}

function render() {
  const list = document.getElementById('notifList');
  const unread = notifications.filter((n) => !n.is_read).length;
  updateSummary(unread);

  if (!notifications.length) {
    list.innerHTML = `<li class="notif-empty">${escapeHtml(EMPTY_TEXT[currentFilter] || EMPTY_TEXT.all)}</li>`;
    return;
  }

  list.innerHTML = notifications.map((n) => {
    const cat = CATEGORY_LABEL[n.category] || n.category || 'Update';
    const created = escapeHtml(formatDate(n.created_at));
    const rel = escapeHtml(timeAgo(n.created_at));
    const clickable = n.link ? ' is-link' : '';
    return `
    <li class="notif-item lvl-${escapeHtml(n.level || 'info')}${n.is_read ? '' : ' unread'}${clickable}"
        data-id="${n.notification_id}"
        data-link="${escapeHtml(n.link || '')}"
        role="${n.link ? 'link' : 'listitem'}"${n.link ? ' tabindex="0"' : ''}>
      <div class="notif-icon" aria-hidden="true">${LEVEL_ICON[n.level] || 'ℹ️'}</div>
      <div class="notif-body">
        <div class="notif-title">${escapeHtml(n.title || '')}</div>
        ${n.message ? `<div class="notif-msg">${escapeHtml(n.message)}</div>` : ''}
        <div class="notif-meta">
          <span class="tag tag-${escapeHtml(n.category || 'general')}">${escapeHtml(cat)}</span>
          <span title="${created}">${rel}</span>
          ${n.link ? '<span class="notif-open">Open →</span>' : ''}
        </div>
      </div>
      ${n.is_read ? '' : `<button class="btn btn-ghost btn-sm notif-mark" data-id="${n.notification_id}">Mark read</button>`}
    </li>`;
  }).join('');
}

async function markRead(id, { reload = true } = {}) {
  try {
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;
    await fetch(`${API_URL}/notifications/${id}/mark_read/`, { method: 'POST', headers });
    if (typeof loadNotificationBadge === 'function') loadNotificationBadge();
    if (reload) await loadNotifications();
  } catch (e) {
    console.error('mark read failed:', e);
  }
}

async function markAllRead() {
  try {
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;
    await fetch(`${API_URL}/notifications/mark_all_read/`, { method: 'POST', headers });
    await loadNotifications();
    if (typeof loadNotificationBadge === 'function') loadNotificationBadge();
  } catch (e) {
    console.error('mark all read failed:', e);
  }
}

// One delegated handler for the whole list: "Mark read" button, or open the
// linked page (marking it read on the way out).
function onListClick(e) {
  const btn = e.target.closest('.notif-mark');
  if (btn) {
    e.stopPropagation();
    markRead(Number(btn.dataset.id));
    return;
  }
  const row = e.target.closest('.notif-item.is-link');
  if (row) {
    const id = Number(row.dataset.id);
    const link = row.dataset.link;
    if (!row.classList.contains('unread')) { window.location.href = link; return; }
    markRead(id, { reload: false }).finally(() => { window.location.href = link; });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (typeof loadUserProfile === 'function') loadUserProfile();
  document.getElementById('filterSelect').addEventListener('change', loadNotifications);
  document.getElementById('notifList').addEventListener('click', onListClick);
  document.getElementById('notifList').addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.closest('.notif-item.is-link')) {
      e.preventDefault();
      onListClick(e);
    }
  });
  loadNotifications();
});
