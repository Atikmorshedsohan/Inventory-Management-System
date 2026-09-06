let transactions = [];
let items = [];
let categories = [];
let rooms = [];
let pendingTransactions = [];
let currentRejection = null;

/**
 * Stock Page - Specific functionality
 * Base functions inherited from base.js
 */

// Set active navigation
setActiveNav('stockNav');

function applyStockPermissions() {
  // Only staff/admin/manager can perform stock IN/OUT
  // Viewers cannot access these functions
  if (userRole === 'viewer') {
    const actionButtons = document.querySelectorAll('.action-btns button');
    actionButtons.forEach((btn) => {
      btn.style.display = 'none';
    });
    // Show permission alert
    const alert = document.getElementById('permissionAlert');
    if (alert) alert.style.display = 'block';
  }
}

async function loadRooms() {
  try {
    const res = await fetch(`${API_URL}/rooms/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    rooms = data.results || data;

    // Populate room selectors in both modals
    [document.getElementById('transRoom'), document.getElementById('newItemRoom')].forEach(select => {
      if (select) {
        select.innerHTML = '<option value="">-- Choose a room --</option>';
        rooms.forEach((room) => {
          const opt = document.createElement('option');
          opt.value = room.room_id;
          opt.textContent = room.room_name;
          select.appendChild(opt);
        });
      }
    });
  } catch (error) {
    console.error('Error loading rooms:', error);
  }
}

async function loadCategories() {
  try {
    const res = await fetch(`${API_URL}/categories/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    categories = data.results || data;

    const select = document.getElementById('newItemCategory');
    select.innerHTML = '<option value="">Select category</option>';
    categories.forEach((cat) => {
      const opt = document.createElement('option');
      opt.value = cat.category_id;
      opt.textContent = cat.category_name;
      select.appendChild(opt);
    });
  } catch (error) {
    console.error('Error loading categories:', error);
  }
}

async function loadItems() {
  try {
    const res = await fetch(`${API_URL}/items/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    items = data.results || data;

    const select = document.getElementById('transItem');
    select.innerHTML = '<option value="">Select an item</option>';
    items.forEach((item) => {
      const opt = document.createElement('option');
      opt.value = item.id || item.item_id;
      opt.textContent = `${item.item_name} (${item.quantity} available)`;
      select.appendChild(opt);
    });
  } catch (error) {
    console.error('Error loading items:', error);
  }
}

async function loadTransactions() {
  try {
    const res = await fetch(`${API_URL}/stock-transactions/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    transactions = data.results || data;

    updateStats();
    renderTransactions();
  } catch (error) {
    console.error('Error loading transactions:', error);
    document.getElementById('transactionsTable').innerHTML = '<tr><td colspan="6" class="error">Failed to load transactions</td></tr>';
  }
}

function updateStats() {
  const inCount = transactions
    .filter((t) => t.type === 'IN')
    .reduce((sum, t) => sum + (t.quantity || 0), 0);
  const outCount = transactions
    .filter((t) => t.type === 'OUT')
    .reduce((sum, t) => sum + (t.quantity || 0), 0);

  document.getElementById('totalIn').textContent = `${inCount} items`;
  document.getElementById('totalOut').textContent = `${outCount} items`;
  document.getElementById('totalMovements').textContent = `${transactions.length} records`;
}

function renderTransactions() {
  const tbody = document.getElementById('transactionsTable');
  if (transactions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">No transactions found</td></tr>';
    return;
  }

  tbody.innerHTML = transactions
    .map((trans) => {
      const item = items.find((i) => (i.id || i.item_id) === trans.item);
      const itemName = item ? item.item_name : `Item #${trans.item}`;
      const badgeClass = trans.type === 'IN' ? 'badge-in' : 'badge-out';
      const userName = trans.user_name || 'System';

      return `<tr>
        <td><span class="badge ${badgeClass}">${trans.type}</span></td>
        <td><strong>${itemName}</strong></td>
        <td>${trans.quantity}</td>
        <td>${formatDate(trans.timestamp)}</td>
        <td>${userName}</td>
        <td>${trans.notes || '—'}</td>
      </tr>`;
    })
    .join('');
}

function openStockModal(type) {
  document.getElementById('transType').value = type;
  document.getElementById('modalTitle').textContent = type === 'IN' ? 'Stock IN' : 'Stock OUT';
  document.getElementById('modalIcon').textContent = type === 'IN' ? '⬇️' : '⬆️';
  document.getElementById('transRoom').value = '';
  document.getElementById('transItem').value = '';
  document.getElementById('transQuantity').value = '';
  document.getElementById('transNotes').value = '';
  document.getElementById('stockModal').classList.add('show');
}

function closeStockModal() {
  document.getElementById('stockModal').classList.remove('show');
}

function openAddItemModal() {
  document.getElementById('newItemRoom').value = '';
  document.getElementById('newItemName').value = '';
  document.getElementById('newItemCategory').value = '';
  document.getElementById('newItemUnit').value = '';
  document.getElementById('newItemQuantity').value = 0;
  document.getElementById('newItemMinQuantity').value = 0;
  document.getElementById('newItemDescription').value = '';
  document.getElementById('addItemModal').classList.add('show');
}

function closeAddItemModal() {
  document.getElementById('addItemModal').classList.remove('show');
}

async function saveTransaction(event) {
  event.preventDefault();
  const data = {
    item: parseInt(document.getElementById('transItem').value, 10),
    room: parseInt(document.getElementById('transRoom').value, 10) || null,
    type: document.getElementById('transType').value,
    quantity: parseInt(document.getElementById('transQuantity').value, 10),
    notes: document.getElementById('transNotes').value
  };

  try {
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    };

    if (csrftoken) {
      headers['X-CSRFToken'] = csrftoken;
    }

    const isAdmin = userRole === 'admin';
    const endpoint = isAdmin ? 'stock-transactions' : 'pending-stock-transactions';
    const res = await fetch(`${API_URL}/${endpoint}/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data)
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || 'Failed to submit transaction for approval');
    }

    await loadTransactions();
    await loadItems();
    closeStockModal();
    alert(isAdmin ? 'Transaction recorded successfully' : 'Transaction submitted for admin approval');
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

async function saveNewItem(event) {
  event.preventDefault();
  const payload = {
    item_name: document.getElementById('newItemName').value.trim(),
    room: document.getElementById('newItemRoom').value || null,
    category: document.getElementById('newItemCategory').value || null,
    unit: document.getElementById('newItemUnit').value.trim() || null,
    quantity: parseInt(document.getElementById('newItemQuantity').value, 10) || 0,
    min_quantity: parseInt(document.getElementById('newItemMinQuantity').value, 10) || 0,
    description: document.getElementById('newItemDescription').value.trim() || null
  };
  try {
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    };

    if (csrftoken) {
      headers['X-CSRFToken'] = csrftoken;
    }

    // Send to pending items endpoint
    const res = await fetch(`${API_URL}/pending-items/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errorData = await res.json();
      const msg = errorData.detail || 'Failed to submit item for approval';
      throw new Error(msg);
    }

    await loadItems();
    closeAddItemModal();
    alert('Item submitted for admin approval');
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

async function loadPendingTransactions() {
  try {
    const res = await fetch(`${API_URL}/pending-stock-transactions/pending_approvals/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return; // No access or endpoint not available

    const data = await res.json();
    pendingTransactions = data.results || data || [];
    renderPendingTransactions();
  } catch (error) {
    console.error('Error loading pending transactions:', error);
  }
}

function renderPendingTransactions() {
  const section = document.getElementById('pendingTransSection');
  const tbody = document.getElementById('pendingTransTable');

  if (!section) return;

  if (!Array.isArray(pendingTransactions) || pendingTransactions.length === 0) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  tbody.innerHTML = pendingTransactions.map((trans) => `
    <tr>
      <td><span class="badge ${trans.type === 'IN' ? 'badge-in' : 'badge-out'}">${trans.type}</span></td>
      <td>${trans.item_name}</td>
      <td>${trans.quantity}</td>
      <td>${trans.room_name || '—'}</td>
      <td>${trans.requested_by_name}</td>
      <td><span class="badge" style="background: #fef3c7; color: #92400e;">Pending</span></td>
      <td>
        <button class="btn-approve" style="padding: 6px 12px; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 4px;" onclick="approveTrans(${trans.pending_id})">Approve</button>
        <button class="btn-reject" style="padding: 6px 12px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;" onclick="openRejectModal('transaction', ${trans.pending_id})">Reject</button>
      </td>
    </tr>
  `).join('');
}

async function approveTrans(transId) {
  try {
    const res = await fetch(`${API_URL}/pending-stock-transactions/${transId}/approve/`, {
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

    alert('Transaction approved successfully');
    await loadPendingTransactions();
    await loadTransactions();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

function openRejectModal(type, id) {
  currentRejection = { type, id };
  document.getElementById('rejectModal').classList.add('show');
  document.getElementById('rejectReason').value = '';
}

function closeRejectModal() {
  document.getElementById('rejectModal').classList.remove('show');
  currentRejection = null;
}

async function submitReject(event) {
  event.preventDefault();
  if (!currentRejection) return;

  const reason = document.getElementById('rejectReason').value.trim();
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
    
    if (type === 'transaction') {
      await loadPendingTransactions();
    } else {
      await loadPendingItems();
    }
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

async function init() {
  setActiveNav('stockNav');
  await loadUserProfile();
  applyStockPermissions();
  await loadRooms();
  await loadCategories();
  await loadItems();
  await loadTransactions();
  
  // Load pending transactions if admin - check after profile is loaded
  if (userRole === 'admin') {
    console.log('Loading pending transactions for role:', userRole);
    if (typeof loadPendingTransactions === 'function') {
      await loadPendingTransactions();
    } else {
      console.error('Pending transactions loader is not available.');
    }
  } else {
    console.log('Not loading pending transactions. Current role:', userRole);
    const section = document.getElementById('pendingTransSection');
    if (section) section.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', init);
