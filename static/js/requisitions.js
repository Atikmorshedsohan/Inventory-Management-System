let allRequisitions = [];
let allItems = [];
let currentUser = null;
let openDetailsReqId = null;

const STATUS_LABELS = {
  pending: 'PENDING',
  approved: 'APPROVED',
  rejected: 'REJECTED',
  partially_issued: 'PARTIAL',
  issued: 'ISSUED',
  returned: 'RETURNED'
};

function statusLabel(status) {
  return STATUS_LABELS[status] || (status || '').toUpperCase();
}

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

const EVENT_ICON = {
  created: '📝',
  approved: '✅',
  rejected: '⛔',
  partially_issued: '📦',
  issued: '📦',
  returned: '↩️',
  comment: '💬'
};

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

  const isAdmin = currentUser?.role === 'admin';
  const isElevated = ['admin', 'manager', 'staff'].includes(currentUser?.role);

  tbody.innerHTML = filtered
    .map((req) => {
      const issuable = req.status === 'approved' || req.status === 'partially_issued';
      return `
                <tr>
                    <td>#${req.req_id}</td>
                    <td>${escapeHtml(req.user_name)}</td>
                    <td>${escapeHtml(req.purpose.substring(0, 50))}${req.purpose.length > 50 ? '…' : ''}</td>
                    <td><span class="status-badge status-${req.status}">${statusLabel(req.status)}</span></td>
                    <td>${req.items.length} items</td>
                    <td>${new Date(req.created_at).toLocaleString()}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-secondary btn-sm" onclick="viewDetails(${req.req_id})">View</button>
                            ${req.status === 'pending' && isAdmin ? `
                                <button class="btn btn-success btn-sm" onclick="approveRequisition(${req.req_id})">Approve</button>
                                <button class="btn btn-danger btn-sm" onclick="rejectRequisition(${req.req_id})">Reject</button>
                            ` : ''}
                            ${issuable && isAdmin ? `
                                <button class="btn btn-primary btn-sm" onclick="issueRequisition(${req.req_id})">${req.status === 'partially_issued' ? 'Issue remaining' : 'Issue'}</button>
                            ` : ''}
                            ${(req.status === 'issued' || req.status === 'partially_issued') && isElevated ? `
                              <button class="btn btn-secondary btn-sm" onclick="returnRequisition(${req.req_id})">Return</button>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `;
    })
    .join('');
}

function renderSummary() {
  const counts = { pending: 0, approved: 0, rejected: 0, partially_issued: 0, issued: 0 };
  allRequisitions.forEach((r) => {
    if (Object.prototype.hasOwnProperty.call(counts, r.status)) counts[r.status] += 1;
  });
  document.getElementById('statPending').textContent = counts.pending;
  document.getElementById('statApproved').textContent = counts.approved;
  document.getElementById('statRejected').textContent = counts.rejected;
  const partialEl = document.getElementById('statPartial');
  if (partialEl) partialEl.textContent = counts.partially_issued;
  document.getElementById('statIssued').textContent = counts.issued;
}

function viewDetails(reqId) {
  const req = allRequisitions.find((r) => r.req_id === reqId);
  if (!req) return;
  openDetailsReqId = reqId;

  const isAdmin = currentUser?.role === 'admin';
  const canIssueLines = isAdmin && (req.status === 'approved' || req.status === 'partially_issued');
  const canComment = currentUser?.user_id === req.user
    || ['admin', 'manager', 'staff'].includes(currentUser?.role);

  const itemsList = req.items
    .map((item) => {
      const catalogItem = allItems.find((i) => i.item_id === item.item || i.id === item.item);
      const available = catalogItem?.quantity ?? '—';
      const issued = item.issued_quantity ?? 0;
      const outstanding = item.outstanding_quantity ?? Math.max(item.quantity - issued, 0);
      const lineBtn = (canIssueLines && outstanding > 0)
        ? `<button class="btn btn-primary btn-sm" onclick="issueLine(${req.req_id}, ${item.req_item_id})">Issue ${Math.min(outstanding, Number(available) || 0) || ''}</button>`
        : '';
      return `
        <tr>
          <td>${escapeHtml(item.item_name)}</td>
          <td>${item.quantity}</td>
          <td>${issued}</td>
          <td class="${outstanding > 0 ? 'outstanding' : ''}">${outstanding}</td>
          <td>${available}</td>
          <td>${lineBtn}</td>
        </tr>
      `;
    })
    .join('');

  const returnInfo = getReturnInfo(req);
  const events = Array.isArray(req.events) ? req.events : [];
  const lastRejection = [...events].reverse().find((e) => e.event_type === 'rejected' && e.note);

  document.getElementById('detailsContent').innerHTML = `
                ${lastRejection ? `<div class="reject-note">⛔ <strong>Rejection reason:</strong> ${escapeHtml(lastRejection.note)}</div>` : ''}
                <div class="details-view">
                    <div class="details-row">
                        <div class="details-label">Requisition ID:</div>
                        <div class="details-value">#${req.req_id}</div>
                    </div>
                    <div class="details-row">
                        <div class="details-label">Requested By:</div>
                        <div class="details-value">${escapeHtml(req.user_name)}</div>
                    </div>
                    <div class="details-row">
                        <div class="details-label">Status:</div>
                        <div class="details-value"><span class="status-badge status-${req.status}">${statusLabel(req.status)}</span></div>
                    </div>
                    <div class="details-row">
                        <div class="details-label">Purpose:</div>
                        <div class="details-value">${escapeHtml(req.purpose)}</div>
                    </div>
                    <div class="details-row">
                      <div class="details-label">Department:</div>
                      <div class="details-value">${escapeHtml(req.department || '—')}</div>
                    </div>
                    <div class="details-row">
                      <div class="details-label">Mobile Number:</div>
                      <div class="details-value">${escapeHtml(req.phone_number || '—')}</div>
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
                  <table class="req-items-table">
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Requested</th>
                        <th>Issued</th>
                        <th>Outstanding</th>
                        <th>In stock</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      ${itemsList}
                    </tbody>
                  </table>
                </div>

                <h3 style="margin: 20px 0 10px 0;">History Timeline</h3>
                <ul class="req-timeline">
                  ${renderTimeline(events)}
                </ul>

                ${canComment ? `
                <div class="comment-box">
                  <textarea id="commentInput" rows="2" placeholder="Add a note or comment…"></textarea>
                  <button class="btn btn-primary btn-sm" onclick="addRequisitionComment(${req.req_id})">Add note</button>
                </div>` : ''}
            `;

  document.getElementById('viewDetailsModal').classList.add('active');
}

function renderTimeline(events) {
  if (!events.length) return '<li class="tl-empty">No history yet</li>';
  return events
    .map((e) => {
      const icon = EVENT_ICON[e.event_type] || '•';
      const when = e.created_at ? new Date(e.created_at).toLocaleString() : '';
      const who = e.actor_name || 'System';
      let headline = e.event_type_display || e.event_type;
      if (e.from_status && e.to_status && e.event_type !== 'comment') {
        headline += ` — ${statusLabel(e.from_status)} → ${statusLabel(e.to_status)}`;
      }
      const note = e.note
        ? `<div class="tl-note ${e.event_type === 'comment' ? 'is-comment' : ''}">${escapeHtml(e.note)}</div>`
        : '';
      return `
        <li class="tl-item tl-${e.event_type}">
          <span class="tl-icon">${icon}</span>
          <div class="tl-body">
            <div class="tl-headline">${escapeHtml(headline)}</div>
            <div class="tl-meta">${escapeHtml(who)} • ${when}</div>
            ${note}
          </div>
        </li>
      `;
    })
    .join('');
}

async function refreshOpenDetails() {
  await fetchRequisitions();
  if (openDetailsReqId != null
      && document.getElementById('viewDetailsModal').classList.contains('active')) {
    viewDetails(openDetailsReqId);
  }
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
  openDetailsReqId = null;
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
      refreshOpenDetails();
    } else {
      const error = await response.json();
      showError(error.detail || error.error || 'Failed to approve requisition');
    }
  } catch (error) {
    console.error('Error approving requisition:', error);
    showError('Error approving requisition');
  }
}

async function rejectRequisition(reqId) {
  const reason = prompt('Reason for rejection (the requester will see this):', '');
  if (reason === null) return;

  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/reject/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ note: reason.trim() })
    });

    if (response.ok) {
      showSuccess('Requisition rejected');
      refreshOpenDetails();
    } else {
      const error = await response.json();
      showError(error.detail || error.error || 'Failed to reject requisition');
    }
  } catch (error) {
    console.error('Error rejecting requisition:', error);
    showError('Error rejecting requisition');
  }
}

function summariseIssue(result) {
  const issued = (result.issued || []).map((r) => `${r.issued}× ${r.item}`).join(', ');
  const short = (result.shortfalls || [])
    .map((s) => s.remaining
      ? `${s.item} (${s.remaining} still outstanding)`
      : `${s.item} (out of stock)`)
    .join(', ');
  let msg = result.fully_issued ? 'All items issued' : 'Partially issued';
  if (issued) msg += `: ${issued}`;
  if (short) msg += `. Outstanding: ${short}`;
  return msg;
}

async function issueRequisition(reqId) {
  if (!confirm('Issue the available stock for this requisition? Items that are out of stock stay outstanding and can be issued later. This creates stock OUT transactions.')) return;

  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/issue/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ allow_partial: true })
    });

    const result = await response.json();
    if (response.ok) {
      showSuccess(summariseIssue(result));
      refreshOpenDetails();
    } else {
      showError(result.detail || result.error || 'Failed to issue items');
    }
  } catch (error) {
    console.error('Error issuing items:', error);
    showError('Error issuing items');
  }
}

async function issueLine(reqId, reqItemId) {
  if (!confirm('Issue the available stock for this line item?')) return;
  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/issue/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ allow_partial: true, req_item_ids: [reqItemId] })
    });
    const result = await response.json();
    if (response.ok) {
      showSuccess(summariseIssue(result));
      refreshOpenDetails();
    } else {
      showError(result.detail || result.error || 'Failed to issue item');
    }
  } catch (error) {
    console.error('Error issuing line item:', error);
    showError('Error issuing item');
  }
}

async function addRequisitionComment(reqId) {
  const input = document.getElementById('commentInput');
  const note = (input?.value || '').trim();
  if (!note) {
    showError('Type a note first');
    return;
  }
  try {
    const response = await fetch(`${API_URL}/requisitions/${reqId}/comment/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ note })
    });
    if (response.ok) {
      if (input) input.value = '';
      showSuccess('Note added');
      refreshOpenDetails();
    } else {
      const error = await response.json();
      showError(error.detail || 'Failed to add note');
    }
  } catch (error) {
    console.error('Error adding comment:', error);
    showError('Error adding note');
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
      refreshOpenDetails();
    } else {
      const error = await response.json();
      showError(error.detail || error.error || 'Failed to mark requisition as returned');
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
