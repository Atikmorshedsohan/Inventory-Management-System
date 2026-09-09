let transactions = [];
let items = [];
let categories = [];
let rooms = [];
let pendingTransactions = [];
let currentRejection = null;
let importBatches = [];

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
    const res = await fetch(`${API_URL}/rooms/?page_size=1000`, {
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
    const res = await fetch(`${API_URL}/categories/?page_size=1000`, {
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
    const res = await fetch(`${API_URL}/items/?page_size=2000`, {
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
    const res = await fetch(`${API_URL}/stock-transactions/?page_size=2000&ordering=-timestamp`, {
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

/* ============ Bulk Stock Import ============ */

function openBulkImportModal() {
  document.getElementById('importFile').value = '';
  const result = document.getElementById('importResult');
  result.classList.add('hidden');
  result.innerHTML = '';
  document.getElementById('importSubmitBtn').disabled = false;
  document.getElementById('bulkImportModal').classList.add('show');
}

function closeBulkImportModal() {
  document.getElementById('bulkImportModal').classList.remove('show');
}

async function downloadImportTemplate() {
  try {
    const res = await fetch(`${API_URL}/stock/bulk-import/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Could not fetch template');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'stock_import_template.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

function renderImportResult(batch) {
  const result = document.getElementById('importResult');
  const rows = batch.report || [];
  const errors = rows.filter((r) => r.status === 'error');
  const ok = rows.filter((r) => r.status === 'ok');

  result.classList.remove('hidden');
  result.innerHTML = `
    <div>
      <span class="sum-ok">${batch.success_count} imported</span> &nbsp;/&nbsp;
      <span class="sum-bad">${batch.error_count} failed</span>
      &nbsp;of ${batch.total_rows} row(s).
    </div>
    ${errors.length ? `<ul>${errors.map((r) => `<li class="row-err">Row ${r.row}: ${r.message}</li>`).join('')}</ul>` : ''}
    ${ok.length ? `<div class="report-toggle" onclick="this.nextElementSibling.hidden = !this.nextElementSibling.hidden">Show ${ok.length} successful row(s)</div>
      <ul hidden>${ok.map((r) => `<li class="row-ok">Row ${r.row}: ${r.item} — ${r.message}</li>`).join('')}</ul>` : ''}
  `;
}

async function submitBulkImport() {
  const fileInput = document.getElementById('importFile');
  const file = fileInput.files[0];
  if (!file) {
    alert('Choose a CSV file first.');
    return;
  }
  const btn = document.getElementById('importSubmitBtn');
  btn.disabled = true;
  btn.textContent = 'Importing…';

  try {
    const form = new FormData();
    form.append('file', file);
    const headers = { Authorization: `Bearer ${token}` };
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    const res = await fetch(`${API_URL}/stock/bulk-import/`, {
      method: 'POST',
      headers,
      body: form
    });
    const data = await res.json();
    if (res.status === 400 && data.detail && !data.report) {
      throw new Error(data.detail);
    }
    renderImportResult(data);
    await loadItems();
    await loadTransactions();
    await loadImportBatches();
    if (typeof loadNotificationBadge === 'function') loadNotificationBadge();
  } catch (e) {
    alert(`Error: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Import';
  }
}

async function loadImportBatches() {
  const tbody = document.getElementById('importsTable');
  if (!tbody) return;
  try {
    const res = await fetch(`${API_URL}/stock-import-batches/?page_size=200`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="7" class="empty">—</td></tr>'; return; }
    const data = await res.json();
    importBatches = data.results || data;
    if (!importBatches.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">No imports yet</td></tr>';
      return;
    }
    tbody.innerHTML = importBatches.map((b, i) => `
      <tr>
        <td><strong>${b.filename || 'upload.csv'}</strong></td>
        <td>${b.total_rows}</td>
        <td style="color:var(--success);font-weight:600;">${b.success_count}</td>
        <td style="color:${b.error_count ? 'var(--danger)' : 'inherit'};font-weight:600;">${b.error_count}</td>
        <td>${formatDate(b.created_at)}</td>
        <td>${b.uploaded_by_name || 'System'}</td>
        <td>${b.error_count ? `<button class="btn-reject" style="padding:4px 10px;background:#64748b;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;" onclick="showBatchErrors(${i})">Errors</button>` : ''}</td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Error loading import batches:', e);
  }
}

function showBatchErrors(index) {
  const batch = importBatches[index];
  const errs = (batch && batch.report ? batch.report : []).filter((r) => r.status === 'error');
  alert(errs.length ? errs.map((r) => `Row ${r.row}: ${r.message}`).join('\n') : 'No errors recorded.');
}

/* ============ Move Item (transfer between rooms) ============ */

function openTransferModal() {
  const itemSel = document.getElementById('transferItem');
  const roomSel = document.getElementById('transferToRoom');

  itemSel.innerHTML = '<option value="">-- Choose an item --</option>';
  items.forEach((it) => {
    const id = it.id || it.item_id;
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = `${it.item_name} (${it.quantity} in ${it.room?.room_name || 'Unassigned'})`;
    itemSel.appendChild(opt);
  });

  roomSel.innerHTML = '<option value="">-- Choose a room --</option>';
  rooms.forEach((r) => {
    const opt = document.createElement('option');
    opt.value = r.room_id;
    opt.textContent = r.room_name;
    roomSel.appendChild(opt);
  });

  document.getElementById('transferQty').value = '';
  document.getElementById('transferRemarks').value = '';
  document.getElementById('transferCurrent').textContent = 'Current room and quantity will show here.';
  document.getElementById('transferModal').classList.add('show');
}

function closeTransferModal() {
  document.getElementById('transferModal').classList.remove('show');
}

function selectedTransferItem() {
  const id = parseInt(document.getElementById('transferItem').value, 10);
  return items.find((it) => (it.id || it.item_id) === id);
}

function onTransferItemChange() {
  const it = selectedTransferItem();
  const hint = document.getElementById('transferCurrent');
  const qty = document.getElementById('transferQty');
  if (!it) {
    hint.textContent = 'Current room and quantity will show here.';
    qty.removeAttribute('max');
    return;
  }
  hint.textContent = `Currently ${it.quantity} unit(s) in ${it.room?.room_name || 'Unassigned'}. `
    + `Leave quantity blank to move all ${it.quantity}.`;
  qty.max = it.quantity;
  qty.placeholder = `Full quantity (${it.quantity})`;
}

async function submitTransfer(event) {
  event.preventDefault();
  const it = selectedTransferItem();
  const toRoom = parseInt(document.getElementById('transferToRoom').value, 10);
  const qtyRaw = document.getElementById('transferQty').value.trim();

  if (!it || !toRoom) {
    alert('Pick an item and a destination room.');
    return;
  }

  const payload = {
    item: it.id || it.item_id,
    to_room: toRoom,
    remarks: document.getElementById('transferRemarks').value.trim()
  };
  if (qtyRaw) payload.quantity = parseInt(qtyRaw, 10);

  try {
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;

    const res = await fetch(`${API_URL}/stock/transfer/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Transfer failed');

    closeTransferModal();
    await loadItems();
    await loadTransactions();
    await loadTransfers();
    if (typeof loadNotificationBadge === 'function') loadNotificationBadge();
    alert(
      `Moved ${data.quantity} × ${data.item_name} from ${data.from_room_name || 'Unassigned'} `
      + `to ${data.to_room_name}. `
      + `Source: ${data.source_qty_before}→${data.source_qty_after}, `
      + `Destination: ${data.dest_qty_before}→${data.dest_qty_after}.`
    );
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

async function loadTransfers() {
  const tbody = document.getElementById('transfersTable');
  if (!tbody) return;
  try {
    const res = await fetch(`${API_URL}/room-item-history/?ordering=-moved_at&page_size=500`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="8" class="empty">—</td></tr>'; return; }
    const data = await res.json();
    const moves = data.results || data;
    if (!moves.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty">No transfers recorded</td></tr>';
      return;
    }
    tbody.innerHTML = moves.map((m) => {
      const snap = (a, b) => (a === null || a === undefined) ? '—' : `${a} → ${b}`;
      const typeBadge = `<span class="badge ${m.transfer_type === 'partial' ? 'badge-out' : 'badge-in'}">${m.transfer_type || 'full'}</span>`;
      return `<tr>
        <td><strong>${m.item_name || 'Item #' + m.item}</strong> ${typeBadge}</td>
        <td>${m.from_room_name || 'Unassigned'}</td>
        <td>${m.to_room_name || 'Unassigned'}</td>
        <td>${m.quantity ?? '—'}</td>
        <td>${snap(m.source_qty_before, m.source_qty_after)}</td>
        <td>${snap(m.dest_qty_before, m.dest_qty_after)}</td>
        <td>${formatDate(m.moved_at)}</td>
        <td>${m.user_name || 'System'}</td>
      </tr>`;
    }).join('');
  } catch (e) {
    console.error('Error loading transfers:', e);
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
  await loadTransfers();
  await loadImportBatches();

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
