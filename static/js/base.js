/**
 * Base JavaScript - Common functions shared across all pages
 */

// ============ Constants & Global Variables ============
const API_URL = '/api';
const token = localStorage.getItem('access') || sessionStorage.getItem('access');
let userRole = 'viewer';
let csrftoken = null;

// Redirect to login if no token
if (!token) {
  window.location.href = '/';
}

// ============ Utility Functions ============

/**
 * Get CSRF token from cookies
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Initialize CSRF token
csrftoken = getCookie('csrftoken');

/**
 * Format date to readable format
 */
function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * Display error message
 */
function showError(msg) {
  const err = document.getElementById('error');
  if (err) {
    err.textContent = msg;
    err.classList.remove('hidden');
  }
}


/**
 * Clear error message
 */
function clearError() {
  const err = document.getElementById('error');
  if (err) {
    err.textContent = '';
    err.classList.add('hidden');
  }
}


/**
 * Logout user
 */
function logout() {
  // Best-effort: record the sign-out for the security log, then clear tokens
  // regardless of whether that call succeeded. keepalive lets it survive the
  // navigation that follows.
  if (token) {
    try {
      fetch(`${API_URL}/auth/logout/`, {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + token },
        keepalive: true
      }).catch(() => {});
    } catch (e) { /* never block sign-out */ }
  }

  localStorage.removeItem('access');
  localStorage.removeItem('refresh');
  sessionStorage.removeItem('access');
  sessionStorage.removeItem('refresh');
  window.location.href = '/';
}

// ============ User Profile Functions ============

/**
 * Apply user information to UI
 */
function applyUserUI(user) {
  currentUserData = user;
  const name = user.name || 'User';
  const role = user.role || 'staff';
  const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);
  
  const userNameEl = document.getElementById('userName');
  const userRoleEl = document.getElementById('userRole');
  const avatarEl = document.getElementById('avatar');
  
  if (userNameEl) userNameEl.textContent = name;
  if (userRoleEl) userRoleEl.textContent = roleLabel;
  if (avatarEl) avatarEl.textContent = name.charAt(0).toUpperCase();
  
  userRole = role;
  
  // Reconciliation is an admin/manager tool.
  const reconciliationNav = document.getElementById('reconciliationNav');
  if (reconciliationNav) {
    reconciliationNav.style.display = (userRole === 'admin' || userRole === 'manager') ? '' : 'none';
  }

  // Role management and the security page are admin-only.
  ['usersNav', 'securityNav'].forEach((id) => {
    const nav = document.getElementById(id);
    if (nav) nav.style.display = userRole === 'admin' ? '' : 'none';
  });

  // Hide restricted pages for viewers only
  if (userRole === 'viewer') {
    const addBtn = document.getElementById('addBtn');
    if (addBtn) addBtn.style.display = 'none';

    // Hide requisitions and audit log navigation for viewers
    const requisitionsNav = document.getElementById('requisitionsNav');
    const auditNav = document.getElementById('auditNav');
    if (requisitionsNav) requisitionsNav.style.display = 'none';
    if (auditNav) auditNav.style.display = 'none';
  } else if (userRole === 'staff') {
    const auditNav = document.getElementById('auditNav');
    if (auditNav) auditNav.style.display = 'none';
  } else {
    // Show requisitions and audit log navigation for non-viewers (admin, manager, staff)
    // Empty string restores the stylesheet's display value (flex) rather than forcing block.
    const requisitionsNav = document.getElementById('requisitionsNav');
    const auditNav = document.getElementById('auditNav');
    if (requisitionsNav) requisitionsNav.style.display = '';
    if (auditNav) auditNav.style.display = '';
  }
  
  // Update profile modal if it exists
  const profileNameEl = document.getElementById('profileName');
  const profileEmailEl = document.getElementById('profileEmail');
  const profileRoleEl = document.getElementById('profileRole');
  const profileDeptEl = document.getElementById('profileDept');
  const profilePhoneEl = document.getElementById('profilePhone');
  
  if (profileNameEl) profileNameEl.textContent = name;
  if (profileEmailEl) profileEmailEl.textContent = user.email || '—';
  if (profileRoleEl) profileRoleEl.textContent = roleLabel;
  if (profileDeptEl) profileDeptEl.textContent = user.department || '—';
  if (profilePhoneEl) profilePhoneEl.textContent = user.phone_number || '—';
}

/**
 * Load user profile and apply to UI
 */
async function loadUserProfile() {
  try {
    const res = await fetch(`${API_URL}/auth/me/`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (res.status === 401) {
      logout();
      return;
    }
    const user = await res.json();
    applyUserUI(user);
  } catch (e) {
    console.error('Failed to load user profile:', e);
  }
}

// ============ Activity log rendering (shared) ============

const ACTION_TYPE_LABELS = {
  stock: 'Stock',
  transfer: 'Transfer',
  reconcile: 'Reconcile',
  role: 'Role',
  approve: 'Approved',
  reject: 'Rejected',
  issue: 'Issued',
  return: 'Returned',
  create: 'Created',
  comment: 'Comment',
  auth: 'Account',
  update: 'Updated',
  delete: 'Deleted',
  other: 'Other'
};

/**
 * Escape text before putting it into innerHTML.
 */
function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

/**
 * Render audit entries into a <ul>. Shared by the profile modal and the
 * Users page so both look the same.
 */
function renderActivityLog(listEl, entries, emptyText = 'No recorded activity yet') {
  if (!listEl) return;
  if (!entries || !entries.length) {
    listEl.innerHTML = `<li class="act-empty">${escapeHtml(emptyText)}</li>`;
    return;
  }
  listEl.innerHTML = entries.map((entry) => {
    const type = entry.action_type || 'other';
    return `
      <li class="act-item">
        <span class="act-badge act-${type}">${ACTION_TYPE_LABELS[type] || type}</span>
        <span class="act-text">${escapeHtml(entry.action)}</span>
        <span class="act-time">${formatDate(entry.timestamp)}</span>
      </li>
    `;
  }).join('');
}

/**
 * Fetch one user's recent audit entries.
 */
async function fetchUserActivity(userId, limit = 8) {
  const res = await fetch(`${API_URL}/users/${userId}/activity/?limit=${limit}`, {
    headers: { Authorization: 'Bearer ' + token }
  });
  if (!res.ok) throw new Error('Could not load activity');
  return res.json();
}

// ============ Notification badge ============

/**
 * Refresh the header bell's unread count.
 */
async function loadNotificationBadge() {
  const badge = document.getElementById('notifBadge');
  if (!badge || !token) return;
  try {
    const res = await fetch(`${API_URL}/notifications/unread_count/`, {
      headers: { Authorization: 'Bearer ' + token }
    });
    if (!res.ok) return;
    const { count } = await res.json();
    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  } catch (e) {
    /* silent - the bell just stays as-is */
  }
}

// ============ Navigation & Sidebar ============

/**
 * Set active navigation item based on current page
 */
function setActiveNav(pageId) {
  // Remove active class from all nav items
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.remove('active');
  });
  
  // Add active class to current page nav
  const activeNav = document.getElementById(pageId);
  if (activeNav) {
    activeNav.classList.add('active');
  }
}

/**
 * Setup sidebar toggle functionality
 */
function setupSidebarToggle() {
  const sidebarToggle = document.getElementById('sidebarToggle');
  const container = document.querySelector('.container');
  const sidebar = document.querySelector('.sidebar');
  
  if (!sidebarToggle) return;
  
  // Load saved state
  const collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
  if (collapsed) {
    container.classList.add('sidebar-collapsed');
    if (sidebar) sidebar.classList.add('collapsed');
  }
  
  // Toggle event
  sidebarToggle.addEventListener('click', () => {
    const isCollapsed = container.classList.toggle('sidebar-collapsed');
    if (sidebar) sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebarCollapsed', isCollapsed ? 'true' : 'false');
  });
}

// ============ Date Display ============

/**
 * Update date display in header
 */
function updateDate() {
  const dateDisplay = document.getElementById('dateDisplay');
  if (!dateDisplay) return;
  
  const now = new Date();
  const options = {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  };
  dateDisplay.textContent = now.toLocaleDateString('en-US', options);
}

// ============ Profile Editing ============

/**
 * Store current user data for editing
 */
let currentUserData = null;

/**
 * Enable profile edit mode
 */
function enableProfileEdit() {
  // Populate edit form with current data
  document.getElementById('editName').value = document.getElementById('profileName').textContent || '';
  document.getElementById('editEmail').value = document.getElementById('profileEmail').textContent || '';
  document.getElementById('editDept').value = document.getElementById('profileDept').textContent || '';
  document.getElementById('editPhone').value = document.getElementById('profilePhone').textContent || '';

  // Switch to edit mode
  document.getElementById('profileViewMode').style.display = 'none';
  document.getElementById('profileEditMode').style.display = 'block';
}

/**
 * Disable profile edit mode
 */
function disableProfileEdit() {
  document.getElementById('profileViewMode').style.display = 'block';
  document.getElementById('profileEditMode').style.display = 'none';
  document.getElementById('profileEditError').style.display = 'none';
}

/**
 * Save profile changes
 */
async function saveProfileChanges(event) {
  event.preventDefault();

  const name = document.getElementById('editName').value;
  const email = document.getElementById('editEmail').value;
  const department = document.getElementById('editDept').value;
  const phone = document.getElementById('editPhone').value;

  if (!name || !email) {
    document.getElementById('profileEditError').textContent = 'Name and Email are required';
    document.getElementById('profileEditError').style.display = 'block';
    return;
  }

  try {
    const response = await fetch(`${API_URL}/auth/me/`, {
      method: 'PATCH',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name,
        email,
        department,
        phone_number: phone
      })
    });

    if (response.ok) {
      const updatedUser = await response.json();
      
      // Update the UI with new data
      document.getElementById('profileName').textContent = updatedUser.name || '—';
      document.getElementById('profileEmail').textContent = updatedUser.email || '—';
      document.getElementById('profileDept').textContent = updatedUser.department || '—';
      document.getElementById('profilePhone').textContent = updatedUser.phone_number || '—';

      // Update user in top section
      const userNameEl = document.getElementById('userName');
      if (userNameEl) userNameEl.textContent = updatedUser.name;

      // Close edit mode
      disableProfileEdit();
      
      // Show success message
      const successMsg = document.createElement('div');
      successMsg.className = 'toast';
      successMsg.textContent = 'Profile updated successfully';
      document.body.appendChild(successMsg);
      
      setTimeout(() => successMsg.remove(), 3000);
    } else {
      const error = await response.json();
      document.getElementById('profileEditError').textContent = error.detail || 'Failed to update profile';
      document.getElementById('profileEditError').style.display = 'block';
    }
  } catch (error) {
    console.error('Error updating profile:', error);
    document.getElementById('profileEditError').textContent = 'Error updating profile: ' + error.message;
    document.getElementById('profileEditError').style.display = 'block';
  }
}

// ============ Modal Functions ============

/**
 * Open profile modal
 */
function openProfileModal() {
  const modal = document.getElementById('profileModal');
  if (modal) modal.classList.add('show');
  loadProfileActivity();
}

/**
 * Fill the "Recent Activity" block in the profile modal.
 */
async function loadProfileActivity() {
  const list = document.getElementById('profileActivityList');
  if (!list) return;

  const userId = currentUserData?.user_id;
  if (!userId) {
    list.innerHTML = '<li class="act-empty">Sign-in details still loading&hellip;</li>';
    return;
  }

  list.innerHTML = '<li class="act-empty">Loading&hellip;</li>';
  try {
    const data = await fetchUserActivity(userId, 8);
    renderActivityLog(list, data.results, 'You have no recorded activity yet');

    // Admins and managers can open the full, filterable trail.
    const more = document.getElementById('profileActivityMore');
    if (more) {
      const canSeeAudit = userRole === 'admin' || userRole === 'manager';
      more.classList.toggle('hidden', !(canSeeAudit && data.total > 8));
      more.href = `/audit/?user=${userId}`;
      more.textContent = `View all ${data.total}`;
    }
  } catch (e) {
    console.error('Failed to load profile activity:', e);
    list.innerHTML = '<li class="act-empty">Could not load activity</li>';
  }
}

/**
 * Close profile modal
 */
function closeProfileModal() {
  const modal = document.getElementById('profileModal');
  if (modal) modal.classList.remove('show');
  // Reset to view mode
  disableProfileEdit();
}

// ============ Initialization ============

/**
 * Initialize common functionality on page load
 */
document.addEventListener('DOMContentLoaded', () => {
  setupSidebarToggle();
  updateDate();
  loadUserProfile();

  // Notification badge: initial load + light polling
  loadNotificationBadge();
  setInterval(loadNotificationBadge, 60000);

  // Attach profile edit form handler
  const profileEditForm = document.getElementById('profileEditForm');
  if (profileEditForm) {
    profileEditForm.addEventListener('submit', saveProfileChanges);
  }
  
  // Close modals on outside click
  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('show');
      }
    });
  });
});
