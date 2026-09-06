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
  } catch(e) {
    showError('Failed to load dashboard');
    console.error(e);
  }
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
      container.innerHTML = '<p style="text-align: center; color: #999; padding: 20px;">No pending items</p>';
      return;
    }
    
    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'pending-item-card';
      card.style.cssText = `
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
      `;
      
      card.innerHTML = `
        <div style="flex: 1;">
          <div style="font-weight: 600; font-size: 15px; color: #333; margin-bottom: 6px;">
            ${item.item_name}
          </div>
          <div style="font-size: 13px; color: #666;">
            ${item.category_name || 'No category'} • ${item.quantity} ${item.unit || 'units'} • 
            Requested by ${item.requested_by_name || 'Unknown'} • 
            ${item.requested_at ? new Date(item.requested_at).toLocaleString() : ''}
          </div>
          ${item.description ? `<div style="font-size: 12px; color: #999; margin-top: 4px;">${item.description}</div>` : ''}
        </div>
        <div style="display: flex; gap: 8px;">
          <button 
            onclick="approvePendingItem(${item.pending_item_id})"
            style="background: #4caf50; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600;"
          >
            ✓ Approve
          </button>
          <button 
            onclick="rejectPendingItem(${item.pending_item_id})"
            style="background: #f44336; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600;"
          >
            ✗ Reject
          </button>
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
