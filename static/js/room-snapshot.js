/**
 * Room Inventory Snapshot
 * A point-in-time listing of what sits in each room, built for printing and
 * for export. Base helpers come from base.js.
 */

let snapshot = { rooms: [] };

setActiveNav('roomSnapshotNav');

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

async function loadSnapshot() {
  const container = document.getElementById('roomsContainer');
  container.innerHTML = '<div class="section"><div class="loading">Loading rooms…</div></div>';
  try {
    const res = await fetch(`${API_URL}/reports/room-snapshot/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');

    snapshot = await res.json();
    renderMeta();
    populateRoomFilter();
    renderRooms();
  } catch (e) {
    console.error(e);
    container.innerHTML = '<div class="section"><div class="error">Failed to load the room snapshot</div></div>';
  }
}

function renderMeta() {
  const taken = snapshot.generated_at ? new Date(snapshot.generated_at).toLocaleString() : '—';
  document.getElementById('snapshotMeta').textContent = `Snapshot taken: ${taken}`;
  const stamp = document.getElementById('printStamp');
  if (stamp) stamp.textContent = `Snapshot taken: ${taken}`;

  document.getElementById('statRooms').textContent = snapshot.room_count ?? 0;
  document.getElementById('statItems').textContent = snapshot.item_count ?? 0;
  document.getElementById('statUnits').textContent = snapshot.total_quantity ?? 0;
  document.getElementById('statLow').textContent = snapshot.low_stock_count ?? 0;
}

function populateRoomFilter() {
  const select = document.getElementById('roomFilter');
  const chosen = select.value;
  select.innerHTML = '<option value="">All rooms</option>';
  (snapshot.rooms || []).forEach((room) => {
    const opt = document.createElement('option');
    opt.value = room.room_name;
    opt.textContent = `${room.room_name} (${room.item_count})`;
    select.appendChild(opt);
  });
  select.value = chosen;
}

function visibleRooms() {
  const q = document.getElementById('searchInput').value.trim().toLowerCase();
  const roomChoice = document.getElementById('roomFilter').value;
  const lowOnly = document.getElementById('lowOnly').checked;

  return (snapshot.rooms || [])
    .filter((room) => !roomChoice || room.room_name === roomChoice)
    .map((room) => {
      const items = (room.items || []).filter((item) => {
        if (lowOnly && !item.is_low_stock) return false;
        if (!q) return true;
        return item.item_name.toLowerCase().includes(q)
          || (item.category || '').toLowerCase().includes(q)
          || room.room_name.toLowerCase().includes(q);
      });
      return { ...room, items };
    })
    .filter((room) => room.items.length > 0);
}

function renderRooms() {
  const container = document.getElementById('roomsContainer');
  const rooms = visibleRooms();

  if (!rooms.length) {
    container.innerHTML = '<div class="section"><div class="empty">No items match this view</div></div>';
    return;
  }

  container.innerHTML = rooms.map((room) => {
    const units = room.items.reduce((sum, i) => sum + (i.quantity || 0), 0);
    const low = room.items.filter((i) => i.is_low_stock).length;
    const meta = [
      room.room_type,
      room.location,
      room.room_key ? 'has key' : null
    ].filter(Boolean).join(' • ');

    return `
      <div class="section room-block">
        <div class="room-head">
          <div>
            <h3>${escapeHtml(room.room_name)}</h3>
            ${meta ? `<div class="room-meta">${escapeHtml(meta)}</div>` : ''}
          </div>
          <div class="room-totals">
            <span>${room.items.length} item(s)</span>
            <span>${units} unit(s)</span>
            ${low ? `<span class="bad">${low} low</span>` : ''}
          </div>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Category</th>
                <th class="num">Quantity</th>
                <th>Unit</th>
                <th class="num">Minimum</th>
                <th>Status</th>
                <th class="count-col">Counted</th>
              </tr>
            </thead>
            <tbody>
              ${room.items.map((item) => `
                <tr class="${item.is_low_stock ? 'row-low' : ''}">
                  <td><strong>${escapeHtml(item.item_name)}</strong></td>
                  <td>${escapeHtml(item.category || '—')}</td>
                  <td class="num">${item.quantity}</td>
                  <td>${escapeHtml(item.unit || '')}</td>
                  <td class="num">${item.min_quantity}</td>
                  <td>${item.is_low_stock
                      ? '<span class="status-badge status-pending">LOW</span>'
                      : '<span class="status-badge status-approved">OK</span>'}</td>
                  <td class="count-col"></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }).join('');
}

async function exportSnapshot(format) {
  const endpoint = format === 'excel' ? 'excel' : 'csv';
  try {
    const res = await fetch(`${API_URL}/reports/room-snapshot/export/${endpoint}/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error(`Failed to export ${endpoint.toUpperCase()}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `CSE_Room_Snapshot_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'csv'}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setActiveNav('roomSnapshotNav');
  loadUserProfile();
  document.getElementById('searchInput').addEventListener('input', renderRooms);
  document.getElementById('roomFilter').addEventListener('change', renderRooms);
  document.getElementById('lowOnly').addEventListener('change', renderRooms);
  loadSnapshot();
});
