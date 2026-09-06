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
    const requisitionsNav = document.getElementById('requisitionsNav');
    const auditNav = document.getElementById('auditNav');
    if (requisitionsNav) requisitionsNav.style.display = 'block';
    if (auditNav) auditNav.style.display = 'block';
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
      successMsg.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #4caf50; color: white; padding: 12px 20px; border-radius: 4px; z-index: 10000; box-shadow: 0 2px 8px rgba(0,0,0,0.2);';
      successMsg.textContent = '✓ Profile updated successfully';
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
