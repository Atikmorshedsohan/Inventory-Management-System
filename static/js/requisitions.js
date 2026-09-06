let allRequisitions = [];
let allItems = [];
let currentUser = null;

/**
 * Requisitions Page - Specific functionality
 * Base functions inherited from base.js
 */

// Helper: build auth headers using base.js if available
function authHeaders(extra = {}) {
  const hasGetAuth = typeof getAuthHeaders === 'function';
  if (hasGetAuth) return getAuthHeaders(extra);
  const headers = { ...extra };
  if (typeof token !== 'undefined' && token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function fetchCurrentUser() {
  try {
    const response = await fetch(`${API_URL}/auth/me/`, {
      headers: authHeaders()
    });

    if (response.status === 401) {
      logout();
      return;
    }

    if (response.ok) {
      currentUser = await response.json();
      console.log('✓ User profile loaded:', currentUser);
    } else {
      console.error('Failed to fetch user profile:', response.status);
      logout();
    }
  } catch (error) {
    console.error('Error fetching user:', error);
  }
}

async function fetchItems() {
  try {
    const response = await fetch(`${API_URL}/items/`, {
      headers: authHeaders()
    });

    if (response.ok) {
      const data = await response.json();
      allItems = Array.isArray(data) ? data : data.results || data;
      updateItemSelects();
    } else {
      console.error('Failed to fetch items:', response.status);
    }
  } catch (error) {
    console.error('Error fetching items:', error);
  }
}

function updateItemSelects() {
  const selects = document.querySelectorAll('.item-select');
  selects.forEach((select) => {
    const currentValue = select.value;
    select.innerHTML = '<option value="">Select item...</option>';
    allItems.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.item_id;
      option.textContent = `${item.item_name} (Available: ${item.quantity})`;
      option.dataset.available = item.quantity;
      select.appendChild(option);
    });
    select.value = currentValue;
  });
}

async function fetchRequisitions() {
  try {
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('requisitionsTable').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';

    const response = await fetch(`${API_URL}/requisitions/`, {
      headers: authHeaders()
    });

    if (response.ok) {
      const data = await response.json();
      allRequisitions = Array.isArray(data) ? data : data.results || [];
      renderRequisitions();
      renderSummary();
    } else {
      showError('Failed to load requisitions');
    }
  } catch (error) {
    console.error('Error fetching requisitions:', error);
    showError('Error loading requisitions');
  } finally {
    document.getElementById('loadingState').style.display = 'none';
  }
}

function renderRequisitions() {
  const tbody = document.getElementById('requisitionsBody');
  const statusFilter = document.getElementById('statusFilter').value;
  const searchText = document.getElementById('searchInput').value.toLowerCase();

  if (!Array.isArray(allRequisitions)) {
    allRequisitions = [];
  }

  const filtered = allRequisitions.filter((req) => {
    const matchesStatus = !statusFilter || req.status === statusFilter;
    const matchesSearch = !searchText || req.purpose.toLowerCase().includes(searchText);
    return matchesStatus && matchesSearch;
  });

  if (filtered.length === 0) {
    document.getElementById('requisitionsTable').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
    return;
  }

  document.getElementById('requisitionsTable').style.display = 'table';
  document.getElementById('emptyState').style.display = 'none';

  tbody.innerHTML = filtered
    .map((req) => `
                <tr>
                    <td>#${req.req_id}</td>
                    <td>${req.user_name}</td>
                    <td>${req.purpose.substring(0, 50)}${req.purpose.length > 50 ? '...' : ''}</td>
                    <td><span class="status-badge status-${req.status}">${req.status.toUpperCase()}</span></td>
                    <td>${req.items.length} items</td>
                    <td>${new Date(req.created_at).toLocaleString()}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-secondary btn-sm" onclick="viewDetails(${req.req_id})">View</button>
                            ${req.status === 'pending' && currentUser?.role === 'admin' ? `
                                <button class="btn btn-success btn-sm" onclick="approveRequisition(${req.req_id})">Approve</button>
                                <button class="btn btn-danger btn-sm" onclick="rejectRequisition(${req.req_id})">Reject</button>
                            ` : ''}
                            ${req.status === 'approved' && currentUser?.role === 'admin' ? `
                                <button class="btn btn-primary btn-sm" onclick="issueRequisition(${req.req_id})">Issue</button>
                            ` : ''}
                            ${req.status === 'issued' && ['admin', 'manager', 'staff'].includes(currentUser?.role) ? `
                              <button class="btn btn-secondary btn-sm" onclick="returnRequisition(${req.req_id})">Return</button>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `)
    .join('');
}

function renderSummary() {
  const counts = { pending: 0, approved: 0, rejected: 0, issued: 0 };
  allRequisitions.forEach((r) => {
    if (Object.prototype.hasOwnProperty.call(counts, r.status)) counts[r.status] += 1;
  });
  document.getElementById('statPending').textContent = counts.pending;
  document.getElementById('statApproved').textContent = counts.approved;
  document.getElementById('statRejected').textContent = counts.rejected;
  document.getElementById('statIssued').textContent = counts.issued;
}

function viewDetails(reqId) {
  const req = allRequisitions.find((r) => r.req_id === reqId);
  if (!req) return;

  const itemsList = req.items
    .map((item) => {
      const catalogItem = allItems.find((i) => i.item_id === item.item || i.id === item.item);
      const available = catalogItem?.quantity ?? '—';
      return `
        <tr>
          <td>${item.item_name}</td>
          <td>${item.quantity}</td>
          <td>${available}</td>
        </tr>
      `;
    })
    .join('');

    const returnInfo = getReturnInfo(req);
    document.getElementById('detailsContent').innerHTML = `
                <div class="details-view">
                    <div class="details-row">
                        <div class="details-label">Requisition ID:</div>
                        <div class="details-value">#${req.req_id}</div>
                    </div>
                    <div class="details-row">
                        <div class="details-label">Requested By:</div>
                        <div class="details-value">${req.user_name}</div>
                    </div>
                    <div class="details-row">
                        <div class="details-label">Status:</div>
                        <div class="details-value"><span class="status-badge status-${req.status}">${req.status.toUpperCase()}</span></div>
                    </div>
                    <div class="details-row">
                        <div class="details-label">Purpose:</div>
                        <div class="details-value">${req.purpose}</div>
                    </div>
                    <div class="details-row">
                      <div class="details-label">Department:</div>
                      <div class="details-value">${req.department || '—'}</div>
                    </div>
                    <div class="details-row">
                      <div class="details-label">Mobile Number:</div>
                      <div class="details-value">${req.phone_number || '—'}</div>
                    </div>
                    <div class="details-row">
                      <div class="details-label">Return Duration:</div>
                      <div class="details-value">${req.return_duration_days || 7} days</div>
                    </div>
                    <div class="details-row">
                      <div class="details-label">Expected Return:</div>
                      <div class="details-value">${returnInfo.expected}</div>
                    </div>
                    <div class="details-row">
                      <div class="details-label">Return Status:</div>
                      <div class="details-value">${returnInfo.statusHtml}</div>
                    </div>
                    <div class="details-row">
                        <div class="details-label">Created At:</div>
                        <div class="details-value">${new Date(req.created_at).toLocaleString()}</div>
                    </div>
                </div>
                <h3 style="margin: 20px 0 10px 0;">Requested Items</h3>
                <div class="details-view">
                  <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                      <tr>
                        <th style="text-align: left; padding: 8px 0; border-bottom: 1px solid #e0e0e0;">Item</th>
                        <th style="text-align: left; padding: 8px 0; border-bottom: 1px solid #e0e0e0;">Quantity</th>
                        <th style="text-align: left; padding: 8px 0; border-bottom: 1px solid #e0e0e0;">Available</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${itemsList}
                    </tbody>
                  </table>
                </div>
            `;

  document.getElementById('viewDetailsModal').classList.add('active');
}

function openNewRequisitionModal() {
  document.getElementById('newRequisitionModal').classList.add('active');
  document.getElementById('requisitionForm').reset();
  document.getElementById('modalError').style.display = 'none';

  document.getElementById('itemsList').innerHTML = `
                <div class="item-row">
                    <select class="item-select" required>
                        <option value="">Select item...</option>
                    </select>
                    <input type="number" class="item-quantity" min="1" placeholder="Quantity" required>
                    <button type="button" class="btn btn-danger btn-sm" onclick="removeItemRow(this)">✕</button>
                </div>
            `;
  updateItemSelects();
}

function closeNewRequisitionModal() {
  document.getElementById('newRequisitionModal').classList.remove('active');
}

function closeViewDetailsModal() {
  document.getElementById('viewDetailsModal').classList.remove('active');
}

function addItemRow() {
  const itemsList = document.getElementById('itemsList');
  const newRow = document.createElement('div');
  newRow.className = 'item-row';
  newRow.innerHTML = `
                <select class="item-select" required>
                    <option value="">Select item...</option>
                </select>
                <input type="number" class="item-quantity" min="1" placeholder="Quantity" required>
                <button type="button" class="btn btn-danger btn-sm" onclick="removeItemRow(this)">✕</button>
            `;
  itemsList.appendChild(newRow);
  updateItemSelects();
}

function getReturnInfo(req) {
  const expected = req.expected_return_at ? new Date(req.expected_return_at).toLocaleString() : '—';
  if (req.returned_at) {
    return {
      expected,
      statusHtml: '<span class="status-badge status-returned">Returned</span>'
    };
  }

  if (req.expected_return_at) {
    const expectedDate = new Date(req.expected_return_at);
    if (Date.now() > expectedDate.getTime()) {
      return {
        expected,
        statusHtml: '<span class="status-badge status-overdue">Overdue</span>'
      };
    }
  }

  return {
    expected,
    statusHtml: '<span class="status-badge status-not-returned">Not returned</span>'
  };
}

function removeItemRow(button) {
  const itemsList = document.getElementById('itemsList');
  if (itemsList.children.length > 1) {
    button.closest('.item-row').remove();
  }
}

async function handleSubmit(event) {
  event.preventDefault();

  const purpose = document.getElementById('purpose').value;
  const department = document.getElementById('department').value.trim();
  const phoneNumber = document.getElementById('phoneNumber').value.trim();
  const returnDuration = parseInt(document.getElementById('returnDuration').value, 10) || 7;
  const itemRows = document.querySelectorAll('.item-row');
  const items = [];

  itemRows.forEach((row) => {
    const itemSelect = row.querySelector('.item-select');
    const quantityInput = row.querySelector('.item-quantity');

    if (itemSelect.value && quantityInput.value) {
      items.push({
        item: parseInt(itemSelect.value, 10),
        quantity: parseInt(quantityInput.value, 10)
      });
    }
  });

  if (items.length === 0) {
    document.getElementById('modalError').textContent = 'Please add at least one item';
    document.getElementById('modalError').style.display = 'block';
    return;
  }

  try {
    if (!currentUser?.user_id) {
      console.log('Current user not loaded, fetching...');
      await fetchCurrentUser();
    }

    if (!currentUser?.user_id) {
      console.error('User profile failed to load. currentUser:', currentUser);
      document.getElementById('modalError').textContent = 'Unable to load user profile';
      document.getElementById('modalError').style.display = 'block';
      return;
    }

    console.log('Submitting requisition for user:', currentUser.user_id);
    const response = await fetch(`${API_URL}/requisitions/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        purpose,
        department,
        phone_number: phoneNumber,
        return_duration_days: returnDuration,
        items,
        user: currentUser.user_id
      })
    });

    if (response.ok) {
      closeNewRequisitionModal();
      showSuccess('Requisition created successfully');
      fetchRequisitions();
    } else {
      const error = await response.json();
      console.error('API Error:', error);
      document.getElementById('modalError').textContent = error.detail || 'Failed to create requisition';
      document.getElementById('modalError').style.display = 'block';
    }
  } catch (error) {
    console.error('Error creating requisition:', error);
    document.getElementById('modalError').textContent = 'Error creating requisition: ' + error.message;
    document.getElementById('modalError').style.display = 'block';
  }
}

async function approveRequisition(reqId) {
  if (!confirm('Are you sure you want to approve this requisition?')) return;

  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/approve/`, {
      method: 'POST',
      headers: authHeaders()
    });

    if (response.ok) {
      showSuccess('Requisition approved successfully');
      fetchRequisitions();
    } else {
      const error = await response.json();
      showError(error.error || 'Failed to approve requisition');
    }
  } catch (error) {
    console.error('Error approving requisition:', error);
    showError('Error approving requisition');
  }
}

async function rejectRequisition(reqId) {
  if (!confirm('Are you sure you want to reject this requisition?')) return;

  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/reject/`, {
      method: 'POST',
      headers: authHeaders()
    });

    if (response.ok) {
      showSuccess('Requisition rejected successfully');
      fetchRequisitions();
    } else {
      const error = await response.json();
      showError(error.error || 'Failed to reject requisition');
    }
  } catch (error) {
    console.error('Error rejecting requisition:', error);
    showError('Error rejecting requisition');
  }
}

async function issueRequisition(reqId) {
  if (!confirm('Are you sure you want to issue items for this requisition? This will create stock OUT transactions.')) return;

  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/issue/`, {
      method: 'POST',
      headers: authHeaders()
    });

    if (response.ok) {
      showSuccess('Items issued successfully');
      fetchRequisitions();
    } else {
      const error = await response.json();
      showError(error.error || 'Failed to issue items');
    }
  } catch (error) {
    console.error('Error issuing items:', error);
    showError('Error issuing items');
  }
}

async function returnRequisition(reqId) {
  if (!confirm('Mark this requisition as returned?')) return;

  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/return/`, {
      method: 'POST',
      headers: authHeaders()
    });

    if (response.ok) {
      showSuccess('Requisition marked as returned');
      fetchRequisitions();
    } else {
      const error = await response.json();
      showError(error.error || 'Failed to mark requisition as returned');
    }
  } catch (error) {
    console.error('Error returning requisition:', error);
    showError('Error returning requisition');
  }
}

// Page-scoped messaging helpers to avoid conflicts
function showError(message) {
  const errorDiv = document.getElementById('errorMessage');
  if (!errorDiv) return;
  errorDiv.textContent = message;
  errorDiv.style.display = 'block';
  setTimeout(() => {
    errorDiv.style.display = 'none';
  }, 5000);
}

function showSuccess(message) {
  const successDiv = document.getElementById('successMessage');
  if (!successDiv) return;
  successDiv.textContent = message;
  successDiv.style.display = 'block';
  setTimeout(() => {
    successDiv.style.display = 'none';
  }, 5000);
}

function bindFilters() {
  document.getElementById('statusFilter').addEventListener('change', renderRequisitions);
  document.getElementById('searchInput').addEventListener('input', renderRequisitions);
  document.getElementById('requisitionForm').addEventListener('submit', handleSubmit);
}

document.addEventListener('DOMContentLoaded', async () => {
  setActiveNav('requisitionsNav');
  await loadUserProfile();
  await fetchCurrentUser();
  bindFilters();
  await fetchItems();
  await fetchRequisitions();
});
