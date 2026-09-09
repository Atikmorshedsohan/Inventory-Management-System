let items = [];
let categories = [];
let rooms = [];
let editingId = null;
let pendingItems = [];
let currentRejection = null;

/**
 * Items Page - Item Management
 * Base functions inherited from base.js
 */

// Set active navigation
setActiveNav('itemsNav');

function renderCategoryOptions() {
  const categoryFilter = document.getElementById('categoryFilter');
  const modalSelect = document.getElementById('itemCategory');
  if (!categoryFilter || !modalSelect) return;
  categoryFilter.innerHTML = '<option value="">All Categories</option>';
  modalSelect.innerHTML = '<option value="">Select a category</option>';
  categories.forEach(cat => {
    const option = document.createElement('option');
    option.value = cat.category_id;
    option.textContent = cat.category_name;
    categoryFilter.appendChild(option.cloneNode(true));
    modalSelect.appendChild(option);
  });
}

async function loadCategories() {
  try {
    const res = await fetch(`${API_URL}/categories/`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (res.status === 401) { logout(); return; }
    const data = await res.json();
    categories = data.results || data || [];
    renderCategoryOptions();
  } catch (e) {
    console.error('Failed to load categories', e);
  }
}

async function loadRooms() {
  try {
    const res = await fetch(`${API_URL}/rooms/`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (res.status === 401) { logout(); return; }
    const data = await res.json();
    rooms = data.results || data || [];
    renderRoomOptions();
  } catch (e) {
    console.error('Failed to load rooms', e);
  }
}

function renderRoomOptions() {
  const select = document.getElementById('itemRoom');
  if (!select) return;
  select.innerHTML = '<option value="">Select a room</option>';
  rooms.forEach(room => {
    const option = document.createElement('option');
    option.value = room.room_id;
    option.textContent = room.room_name;
    select.appendChild(option);
  });
}

function statusBadge(item) {
  const low = typeof item.min_quantity === 'number' && typeof item.quantity === 'number' && item.quantity <= item.min_quantity;
  const cls = low ? 'status-low' : 'status-available';
  const label = low ? 'Low stock' : 'Available';
  return `<span class="status-badge ${cls}">${label}</span>`;
}

function renderItems() {
  const tbody = document.getElementById('itemsTable');
  const search = document.getElementById('searchBox').value.toLowerCase();
  const catFilter = document.getElementById('categoryFilter').value;
  const filtered = items.filter(item => {
    const matchesSearch = !search || item.item_name.toLowerCase().includes(search);
    const matchesCat = !catFilter || (item.category && String(item.category.category_id || item.category_id) === String(catFilter)) || String(item.category_id) === String(catFilter);
    return matchesSearch && matchesCat;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">No items found</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(item => {
    const catName = item.category?.category_name || item.category_name || '—';
    const lastUpdated = item.updated_at || item.updated || item.created_at;
    const isAdmin = userRole === 'admin';
    const disabledActions = isAdmin ? '' : 'style="display:none"';
    return `<tr>
      <td><strong>${item.item_name}</strong></td>
      <td>${catName}</td>
      <td>${item.unit || '—'}</td>
      <td>${item.quantity ?? 0}</td>
      <td>${statusBadge(item)}</td>
      <td>${formatDate(lastUpdated)}</td>
      <td>
        <div class="actions">
          <button class="action-btn" title="Edit" onclick="openEditModal(${item.id || item.item_id})">✏️</button>
          <button class="action-btn delete" ${disabledActions} title="Delete" onclick="deleteItem(${item.id || item.item_id})">🗑️</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

async function loadItems() {
  try {
    const res = await fetch(`${API_URL}/items/`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (res.status === 401) { logout(); return; }
    const data = await res.json();
    items = data.results || data || [];
    renderItems();
  } catch (e) {
    console.error('Failed to load items', e);
    showError('Unable to load items');
  }
}

function openAddModal() {
  editingId = null;
  document.getElementById('modalTitle').textContent = 'Add New Item';
  document.getElementById('submitBtn').textContent = 'Create Item';
  document.getElementById('itemName').value = '';
  document.getElementById('itemCategory').value = '';
  document.getElementById('itemRoom').value = '';
  document.getElementById('itemQuantity').value = 0;
  document.getElementById('itemMinQty').value = 0;
  document.getElementById('itemUnit').value = '';
  document.getElementById('itemModal').classList.add('show');
}

function openEditModal(id) {
  const item = items.find(i => (i.id || i.item_id) === id);
  if (!item) return;
  editingId = id;
  document.getElementById('modalTitle').textContent = 'Edit Item';
  document.getElementById('submitBtn').textContent = 'Update Item';
  document.getElementById('itemName').value = item.item_name || '';
  document.getElementById('itemCategory').value = item.category_id || item.category?.category_id || '';
  document.getElementById('itemRoom').value = item.room_id || item.room?.room_id || '';
  document.getElementById('itemQuantity').value = item.quantity ?? 0;
  document.getElementById('itemMinQty').value = item.min_quantity ?? 0;
  document.getElementById('itemUnit').value = item.unit || '';
  document.getElementById('itemModal').classList.add('show');
}

function closeItemModal() {
  document.getElementById('itemModal').classList.remove('show');
}

async function saveItem(e) {
  e.preventDefault();
  clearError();
  const payload = {
    item_name: document.getElementById('itemName').value.trim(),
    category_id: document.getElementById('itemCategory').value || null,
    room_id: document.getElementById('itemRoom').value || null,
    unit: document.getElementById('itemUnit').value.trim() || null,
    quantity: parseInt(document.getElementById('itemQuantity').value, 10) || 0,
    min_quantity: parseInt(document.getElementById('itemMinQty').value, 10) || 0,
  };

  const headers = {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  };
  if (csrftoken) headers['X-CSRFToken'] = csrftoken;

  try {
    const url = editingId ? `${API_URL}/items/${editingId}/` : `${API_URL}/items/`;
    const method = editingId ? 'PUT' : 'POST';
    const res = await fetch(url, { method, headers, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) {
      const msg = data.detail || data.item_name?.[0] || data.quantity?.[0] || 'Failed to save item';
      throw new Error(msg);
    }
    await loadItems();
    closeItemModal();
  } catch (err) {
    showError(err.message);
  }
}

async function deleteItem(id) {
  if (userRole !== 'admin') return;
  const confirmed = confirm('Delete this item?');
  if (!confirmed) return;

  const headers = { 'Authorization': 'Bearer ' + token };
  if (csrftoken) headers['X-CSRFToken'] = csrftoken;

  try {
    const res = await fetch(`${API_URL}/items/${id}/`, { method: 'DELETE', headers });
    if (res.status === 403) {
      throw new Error('Only admins can delete items');
    }
    if (!res.ok) throw new Error('Failed to delete item');
    await loadItems();
  } catch (e) {
    showError(e.message);
  }
}

function registerEvents() {
  const searchBox = document.getElementById('searchBox');
  const categoryFilter = document.getElementById('categoryFilter');
  if (searchBox) searchBox.addEventListener('input', renderItems);
  if (categoryFilter) categoryFilter.addEventListener('change', renderItems);
}

function setActiveToggle(activeId) {
  document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('active'));
  const el = document.getElementById(activeId);
  if (el) el.classList.add('active');
}

function showListView() {
  document.getElementById('listView').classList.remove('hidden');
  document.getElementById('pendingItemsSection').classList.add('hidden');
  setActiveToggle('listToggleBtn');
}

function showPendingView() {
  document.getElementById('listView').classList.add('hidden');
  document.getElementById('pendingItemsSection').classList.remove('hidden');
  setActiveToggle('pendingToggleBtn');
  loadPendingItems();
}

function initDate() {
  const dateDisplay = document.getElementById('dateDisplay');
  if (dateDisplay) {
    dateDisplay.textContent = new Date().toLocaleDateString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
  }
}

function isApprover() {
  return userRole && ['admin', 'manager'].includes(userRole);
}

function updatePendingBadge() {
  const badge = document.getElementById('pendingCount');
  if (!badge) return;
  const n = pendingItems.length;
  badge.textContent = n;
  badge.classList.toggle('hidden', n === 0);
}

async function loadPendingItems() {
  const tbody = document.getElementById('pendingItemsTable');
  const heading = document.getElementById('pendingHeading');

  // Approvers see every open request; requesters see the ones they raised.
  const url = isApprover()
    ? `${API_URL}/pending-items/pending_approvals/`
    : `${API_URL}/pending-items/?status=pending&page_size=100`;
  if (heading) {
    heading.textContent = isApprover()
      ? '⏳ Pending Item Approvals'
      : '⏳ My Pending Item Requests';
  }

  if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading pending items...</td></tr>';

  try {
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) {
      pendingItems = [];
      updatePendingBadge();
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty">Failed to load pending items</td></tr>';
      return;
    }

    const data = await res.json();
    pendingItems = Array.isArray(data) ? data : (data.results || []);
    updatePendingBadge();
    renderPendingItems();
  } catch (error) {
    console.error('Error loading pending items:', error);
    pendingItems = [];
    updatePendingBadge();
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty">Failed to load pending items</td></tr>';
  }
}

function renderPendingItems() {
  const tbody = document.getElementById('pendingItemsTable');
  const canApprove = isApprover();
  if (!tbody) return;

  if (!pendingItems.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty">${
      canApprove ? 'No item requests are waiting for approval.' : "You haven't requested any items that are still pending."
    }</td></tr>`;
    return;
  }

  tbody.innerHTML = pendingItems.map((item) => {
    const id = item.pending_item_id || item.id;
    return `
    <tr>
      <td>${item.item_name}</td>
      <td>${item.category_name || item.category?.category_name || item.category || '—'}</td>
      <td>${item.quantity} ${item.unit || 'units'}</td>
      <td>${item.room_name || item.room?.room_name || item.room || '—'}</td>
      <td>${item.requested_by_name || item.requested_by?.name || item.requested_by || '—'}</td>
      <td><span class="badge" style="background: #fef3c7; color: #92400e; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Pending</span></td>
      <td>
        ${canApprove ? `
          <button style="padding: 6px 12px; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 4px;" onclick="approveItem(${id})">Approve</button>
          <button style="padding: 6px 12px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;" onclick="openRejectModal('item', ${id})">Reject</button>
        ` : '—'}
      </td>
    </tr>`;
  }).join('');
}

async function approveItem(itemId) {
  try {
    const res = await fetch(`${API_URL}/pending-items/${itemId}/approve/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to approve');
    }

    alert('Item approved successfully');
    await loadPendingItems();
    await loadItems();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

function openRejectModal(type, id) {
  currentRejection = { type, id };
  const modal = document.getElementById('rejectModal');
  if (modal) {
    modal.classList.add('show');
    document.getElementById('rejectionReason').value = '';
  }
}

function closeRejectModal() {
  const modal = document.getElementById('rejectModal');
  if (modal) modal.classList.remove('show');
  currentRejection = null;
}

async function submitReject(event) {
  event.preventDefault();
  if (!currentRejection) return;

  const reason = document.getElementById('rejectionReason').value.trim();
  const { type, id } = currentRejection;
  const endpoint = type === 'transaction' ? 'pending-stock-transactions' : 'pending-items';

  try {
    const res = await fetch(`${API_URL}/${endpoint}/${id}/reject/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ rejection_reason: reason })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to reject');
    }

    alert('Request rejected');
    closeRejectModal();
    await loadPendingItems();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}


(async function init() {
  initDate();
  registerEvents();
  await loadUserProfile();
  await loadCategories();
  await loadRooms();
  await loadItems();
  // Populate the "Pending" tab + its count badge on load (renders into the
  // hidden section; the badge shows there are requests before you switch tabs).
  await loadPendingItems();
})();

// Sidebar toggle logic (Items page)
document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('.container');
  const sidebar = document.querySelector('.sidebar');
  const btn = document.getElementById('sidebarToggle');
  if (!container || !btn) return;

  const collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
  if (collapsed) {
    container.classList.add('sidebar-collapsed');
    if (sidebar) sidebar.classList.add('collapsed');
  }

  btn.addEventListener('click', () => {
    const isCollapsed = container.classList.toggle('sidebar-collapsed');
    if (sidebar) sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebarCollapsed', isCollapsed ? 'true' : 'false');
  });
});
