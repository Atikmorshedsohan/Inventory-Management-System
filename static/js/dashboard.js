/**
 * Dashboard Page - Specific functionality
 * Base functions inherited from base.js
 */

// Set active navigation
setActiveNav('dashboardNav');

async function loadDashboard() {
  try {
    const res = await fetch(`${API_URL}/reports/dashboard/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    const data = await res.json();
    
    document.getElementById('total_items').textContent = data.total_items ?? 0;
    document.getElementById('low_stock_items').textContent = data.low_stock_items ?? 0;
    document.getElementById('available_items').textContent = data.available_items ?? 0;
    document.getElementById('stock_in').textContent = data.stock_in_month ?? 0;
    
    loadLocations();
    loadRecentActivity();
    loadRoomStats();
    loadPendingItems(); // Load pending items for admin
    loadStockMovement();
    loadLowStock();
  } catch(e) {
    showError('Failed to load dashboard');
    console.error(e);
  }
}

// ============ Low stock list ============

let lowStockLoaded = false;

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

async function loadLowStock() {
  const body = document.getElementById('lowStockBody');
  if (!body) return;
  try {
    const res = await fetch(`${API_URL}/reports/low-stock/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');

    const data = await res.json();
    const items = data.items || [];
    lowStockLoaded = true;

    const hint = document.getElementById('lowStockHint');
    if (hint) hint.textContent = items.length ? '— click to view' : '— all good';

    if (!items.length) {
      body.innerHTML = '<tr><td colspan="7" class="empty">Nothing is below its minimum</td></tr>';
      return;
    }

    body.innerHTML = items.map((it) => `
      <tr class="${it.out_of_stock ? 'row-critical' : ''}">
        <td><strong>${escapeHtml(it.item_name)}</strong></td>
        <td>${escapeHtml(it.room_name)}</td>
        <td>${escapeHtml(it.category)}</td>
        <td class="num">${it.quantity} ${escapeHtml(it.unit || '')}</td>
        <td class="num">${it.min_quantity}</td>
        <td class="num shortage">${it.shortage > 0 ? `-${it.shortage}` : '0'}</td>
        <td><span class="status-badge ${it.out_of_stock ? 'status-rejected' : 'status-pending'}">
          ${it.out_of_stock ? 'OUT OF STOCK' : 'LOW'}</span></td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Failed to load low stock items:', e);
    body.innerHTML = '<tr><td colspan="7" class="error">Could not load low stock items</td></tr>';
  }
}

function toggleLowStock() {
  const section = document.getElementById('lowStockSection');
  if (!section) return;
  const hidden = section.classList.toggle('hidden');
  if (!hidden) {
    if (!lowStockLoaded) loadLowStock();
    section.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

// ============ Stock movement chart ============

let movementChart = null;

async function loadStockMovement() {
  const canvas = document.getElementById('movementChart');
  if (!canvas || typeof Chart === 'undefined') return;

  const days = document.getElementById('movementRange')?.value || 30;
  try {
    const res = await fetch(`${API_URL}/reports/stock-movement/?days=${days}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');

    const data = await res.json();
    renderMovementTotals(data);

    // Daily bars get noisy over long windows; switch to lines there.
    const asLine = data.labels.length > 45;
    const shortLabels = data.labels.map((iso) => {
      const d = new Date(`${iso}T00:00:00`);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    if (movementChart) movementChart.destroy();
    movementChart = new Chart(canvas, {
      type: asLine ? 'line' : 'bar',
      data: {
        labels: shortLabels,
        datasets: [
          {
            label: 'Stock IN',
            data: data.stock_in,
            backgroundColor: '#10b981',
            borderColor: '#10b981',
            borderRadius: 4,
            tension: 0.3,
            fill: false
          },
          {
            label: 'Stock OUT',
            data: data.stock_out,
            backgroundColor: '#ef4444',
            borderColor: '#ef4444',
            borderRadius: 4,
            tension: 0.3,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 15, usePointStyle: true, pointStyle: 'rect' }
          },
          tooltip: {
            callbacks: {
              title: (ctx) => data.labels[ctx[0].dataIndex],
              label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} units`
            }
          }
        },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: 'Units' } },
          x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 16 } }
        }
      }
    });
  } catch (e) {
    console.error('Failed to load stock movement:', e);
    const totals = document.getElementById('movementTotals');
    if (totals) totals.innerHTML = '<span class="error">Could not load stock movement</span>';
  }
}

function renderMovementTotals(data) {
  const el = document.getElementById('movementTotals');
  if (!el) return;
  const netClass = data.net > 0 ? 'pos' : (data.net < 0 ? 'neg' : '');
  el.innerHTML = `
    <span class="mv in">▼ IN <strong>${data.total_in}</strong></span>
    <span class="mv out">▲ OUT <strong>${data.total_out}</strong></span>
    <span class="mv net ${netClass}">NET <strong>${data.net > 0 ? '+' : ''}${data.net}</strong></span>
    <span class="mv range">${data.start} → ${data.end}</span>
  `;
}

async function loadLocations() {
  const grid = document.getElementById('locationGrid');
  if (!grid) return;

  grid.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const res = await fetch(`${API_URL}/items/roomwise/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (res.status === 401) { logout(); return; }

    const rooms = await res.json();
    grid.innerHTML = '';

    if (Array.isArray(rooms) && rooms.length) {
      rooms.forEach(room => {
        const lowStockCount = (room.items || []).filter(it => it.is_low_stock).length;
        const card = document.createElement('div');
        card.className = 'location-card';
        card.innerHTML = `
          <div class="location-name">${room.room_name || 'General Storage'}</div>
          <div class="location-items">${room.item_count || 0} items • ${room.total_quantity || 0} total qty</div>
          <div class="location-detail">
            <span>Low stock</span>
            <span>${lowStockCount}</span>
          </div>
        `;
        grid.appendChild(card);
      });
    } else {
      grid.innerHTML = '<p style="color:#777;">No room data yet</p>';
    }
  } catch(e) {
    console.error('Failed to load locations:', e);
    grid.innerHTML = '<p style="color:#c62828;">Could not load location overview</p>';
  }
}

async function loadRecentActivity() {
  try {
    const res = await fetch(`${API_URL}/stock-transactions/?page=1`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();
    const list = document.getElementById('activityList');
    list.innerHTML = '';

    const txns = Array.isArray(data) ? data : data.results || [];
    const topTxns = txns.slice(0, 5);
    if (topTxns.length === 0) {
      list.innerHTML = '<li style="text-align:center;color:#999;padding:20px;">No recent activity</li>';
      return;
    }

    topTxns.forEach(txn => {
      const icon = txn.type === 'IN' ? '↓' : '↑';
      const iconClass = txn.type === 'IN' ? 'in' : 'out';
      const action = txn.type === 'IN' ? 'Stock In' : 'Stock Out';
      const detailTime = txn.timestamp ? new Date(txn.timestamp).toLocaleString() : 'Recently';
      const itemName = txn.item_name || txn.item || 'Item';
      const userName = txn.user_name || 'System';
      
      const li = document.createElement('li');
      li.className = 'activity-item';
      li.innerHTML = `
        <div class="activity-icon ${iconClass}">${icon}</div>
        <div class="activity-content">
          <div class="activity-title">${action} • ${txn.quantity} units</div>
          <div class="activity-detail">${itemName} • ${userName} • ${detailTime}</div>
        </div>
      `;
      list.appendChild(li);
    });
  } catch(e) {
    console.error('Failed to load activity:', e);
  }
}

async function loadRoomStats() {
  const totalEl = document.getElementById('rooms_total');
  const unassignedEl = document.getElementById('rooms_unassigned');
  const movesEl = document.getElementById('rooms_moves_7d');
  const list = document.getElementById('roomActivityList');
  if (!totalEl) return;

  if (list) {
    list.innerHTML = '<li class="loading"><div class="spinner"></div></li>';
  }

  try {
    const res = await fetch(`${API_URL}/reports/rooms-overview/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (res.status === 401) { logout(); return; }

    const data = await res.json();
    totalEl.textContent = data.total_rooms ?? 0;
    unassignedEl.textContent = data.unassigned_items ?? 0;
    movesEl.textContent = data.recent_moves_7d ?? 0;

    if (list) {
      const moves = Array.isArray(data.recent_moves) ? data.recent_moves.slice(0, 5) : [];
      list.innerHTML = '';
      if (!moves.length) {
        list.innerHTML = '<li style="text-align:center;color:#999;padding:20px;">No recent room moves</li>';
      } else {
        moves.forEach(log => {
          const when = log.moved_at ? new Date(log.moved_at).toLocaleString() : '';
          const li = document.createElement('li');
          li.className = 'activity-item';
          li.innerHTML = `
            <div class="activity-icon in">↔</div>
            <div class="activity-content">
              <div class="activity-title">${log.item_name || 'Item'} • ${log.from_room_name || '—'} → ${log.to_room_name || '—'}</div>
              <div class="activity-detail">${log.user_name || 'System'}${when ? ' • ' + when : ''}</div>
            </div>
          `;
          list.appendChild(li);
        });
      }
    }
  } catch (e) {
    console.error('Failed to load room stats:', e);
    totalEl.textContent = unassignedEl.textContent = movesEl.textContent = '—';
    if (list) {
      list.innerHTML = '<li style="text-align:center;color:#c62828;padding:20px;">Failed to load room activity</li>';
    }
  }
}

// Load pending items (Admin/Manager only)
async function loadPendingItems() {
  const section = document.getElementById('pendingItemsSection');
  const container = document.getElementById('pendingItemsContainer');
  
  if (!section || !container) return;
  
  // Check if user is admin/manager
  if (userRole !== 'admin' && userRole !== 'manager') {
    section.style.display = 'none';
    return;
  }
  
  section.style.display = 'block';
  container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  
  try {
    const res = await fetch(`${API_URL}/pending-items/?status=pending`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Failed to load pending items');
    
    const data = await res.json();
    const items = Array.isArray(data) ? data : data.results || [];
    
    container.innerHTML = '';
    
    if (items.length === 0) {
      container.innerHTML = '<p class="empty">No pending items</p>';
      return;
    }

    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'pending-item-card';
      const meta = [
        item.category_name || 'No category',
        `${item.quantity} ${item.unit || 'units'}`,
        `Requested by ${item.requested_by_name || 'Unknown'}`,
        item.requested_at ? new Date(item.requested_at).toLocaleString() : ''
      ].filter(Boolean).join(' • ');

      card.innerHTML = `
        <div style="flex:1; min-width:0;">
          <div class="pending-title">${item.item_name}</div>
          <div class="pending-meta">${meta}</div>
          ${item.description ? `<div class="pending-desc">${item.description}</div>` : ''}
        </div>
        <div class="pending-actions">
          <button class="btn btn-primary btn-sm" onclick="approvePendingItem(${item.pending_item_id})">Approve</button>
          <button class="btn btn-danger btn-sm" onclick="rejectPendingItem(${item.pending_item_id})">Reject</button>
        </div>
      `;

      container.appendChild(card);
    });
  } catch (e) {
    console.error('Failed to load pending items:', e);
    container.innerHTML = '<p style="text-align: center; color: #c62828; padding: 20px;">Failed to load pending items</p>';
  }
}

async function approvePendingItem(itemId) {
  if (!confirm('Approve this item and add it to inventory?')) return;
  
  try {
    const res = await fetch(`${API_URL}/pending-items/${itemId}/approve/`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (res.status === 401) { logout(); return; }
    if (!res.ok) {
      const error = await res.text();
      throw new Error(error || 'Failed to approve item');
    }
    
    alert('Item approved and added to inventory!');
    loadPendingItems(); // Reload pending items
    loadDashboard(); // Refresh dashboard stats
  } catch (e) {
    console.error('Failed to approve item:', e);
    showError('Failed to approve item: ' + e.message);
  }
}

async function rejectPendingItem(itemId) {
  const reason = prompt('Enter rejection reason (optional):');
  if (reason === null) return; // User cancelled
  
  try {
    const res = await fetch(`${API_URL}/pending-items/${itemId}/reject/`, {
      method: 'POST',
      headers: { 
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ rejection_reason: reason || 'No reason provided' })
    });
    
    if (res.status === 401) { logout(); return; }
    if (!res.ok) {
      const error = await res.text();
      throw new Error(error || 'Failed to reject item');
    }
    
    alert('Item rejected');
    loadPendingItems(); // Reload pending items
  } catch (e) {
    console.error('Failed to reject item:', e);
    showError('Failed to reject item: ' + e.message);
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  loadUserProfile();
  loadDashboard();
});
