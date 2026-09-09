// Endpoints
const ROOMWISE_ITEMS_URL = '/api/items/roomwise/';
const ROOMS_URL = '/api/rooms/';
const ITEMS_URL = '/api/items/?limit=1000';
const ROOM_KEYS_URL = '/api/room-keys/';
const KEY_BORROW_URL = '/api/key-borrows/';
const ROOMWISE_ACTIVITY_URL = '/api/reports/roomwise-activity/';

let roomKeys = [];
let keyBorrows = [];
let activeBorrows = [];
let myBorrows = [];          // the signed-in viewer's own key borrows, any status
let selectedRoomForKey = null;
let selectedBorrowForReturn = null;
let currentUserId = null;

const BORROW_ACTIVE_STATUSES = ['pending', 'approved', 'borrowed'];

// Inline SVG icon from the sprite defined in base.html
function icon(name, cls = 'ic') {
  return `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

// Auth headers helper (uses base.js if available)
function authHeaders(extra = {}) {
  // Try to get token from base.js first, then fallback to local storage
  let token = null;
  
  // Check if getAuthHeaders from base.js exists
  if (typeof getAuthHeaders === 'function') {
    console.log(' Using getAuthHeaders from base.js');
    return getAuthHeaders(extra);
  }
  
  // Fallback: get token from storage
  token = localStorage.getItem('access') || sessionStorage.getItem('access');
  console.log(` Token found: ${token ? ' Yes (' + token.substring(0, 20) + '...)' : ' No'}`);
  
  const headers = { ...extra };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
    console.log(` Built auth header: Bearer ${token.substring(0, 20)}...`);
  } else {
    console.warn(' No token found in localStorage or sessionStorage!');
  }
  return headers;
}

// Pull a human-readable message out of a failed DRF response.
// DRF errors come back as {"detail": "..."} (or a field map); fall back to raw text.
async function extractError(res, fallback = 'Request failed') {
  const raw = await res.text();
  try {
    const data = JSON.parse(raw);
    if (typeof data === 'string') return data;
    if (data.detail) return data.detail;
    const first = Object.values(data)[0];
    if (Array.isArray(first)) return first[0];
    if (typeof first === 'string') return first;
  } catch (_) { /* not JSON - use raw text */ }
  return raw || fallback;
}

// Reload every key-related list, then re-render the room cards.
async function refreshKeyData() {
  await loadRoomKeys();
  await loadKeyBorrows();
  await loadActiveBorrows();
  await loadMyBorrows();
  await loadAllData();
}

// Initialize page
document.addEventListener('DOMContentLoaded', async () => {
  setActiveNav('roomwiseNav');
  await loadUserProfileAndId();
  await refreshKeyData();
  await loadRecentActivity();
  // Auto-refresh every 60 seconds (1 minute)
  setInterval(async () => {
    await refreshKeyData();
    await loadRecentActivity();
  }, 60000);
});

// Load user profile and capture user ID
async function loadUserProfileAndId() {
  try {
    const token = localStorage.getItem('access') || sessionStorage.getItem('access');
    const res = await fetch('/api/auth/me/', {
      headers: { 'Authorization': 'Bearer ' + token }
    });
    if (res.ok) {
      const user = await res.json();
      currentUserId = user.user_id;
      // base.js also sets this, but it races with our first render - pin it now
      // so the viewer key actions decide on the right role from the start.
      if (user.role) userRole = user.role;
      console.log(` Current user ID: ${currentUserId}, role: ${userRole}`);
    }
  } catch (err) {
    console.error('Failed to load user profile:', err);
  }
}

// Load and render data
async function loadAllData() {
  const container = document.getElementById('roomsContainer');
  const errorDiv = document.getElementById('error');

  if (container) container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading rooms...</div>';
  if (errorDiv) errorDiv.classList.add('hidden');

  try {
    let roomsData = await loadRoomwiseData();
    console.log(` loadRoomwiseData returned:`, roomsData ? `${roomsData.length} rooms` : 'null/empty');

    if (!roomsData || roomsData.length === 0) {
      console.log(' No rooms from roomwise endpoint, falling back to /api/rooms/');
      roomsData = await loadAllRoomsAndItems();
    }

    console.log(` Final roomsData:`, roomsData ? `${roomsData.length} rooms` : 'empty');
    if (container) container.innerHTML = '';
    if (roomsData && roomsData.length > 0) {
      renderRooms(sortRoomsByRecency(roomsData), container);
    } else if (container) {
      container.innerHTML = '<div class="empty" style="padding: 40px; text-align: center;"><h3>No rooms found</h3><p>No room data is available.</p></div>';
    }
  } catch (err) {
    console.error('Error loading data:', err);
    if (container) container.innerHTML = '';
    if (errorDiv) {
      errorDiv.classList.remove('hidden');
      errorDiv.textContent = `Error: ${err.message}`;
    }
  }
}

// Most-recently-updated room first. Rooms with no known update time sink to the
// bottom; General Storage loses ties to real rooms; then alphabetical.
function sortRoomsByRecency(rooms) {
  return [...rooms].sort((a, b) => {
    const at = a.last_updated ? Date.parse(a.last_updated) : -Infinity;
    const bt = b.last_updated ? Date.parse(b.last_updated) : -Infinity;
    if (at !== bt) return bt - at;
    const aGen = a.room_id == null;
    const bGen = b.room_id == null;
    if (aGen !== bGen) return aGen ? 1 : -1;
    return (a.room_name || '').localeCompare(b.room_name || '');
  });
}

function isGeneralStorage(room) {
  return room.room_id == null || /^general storage/i.test(room.room_name || '');
}

function relTime(dateStr) {
  if (!dateStr) return '';
  const secs = Math.round((Date.now() - Date.parse(dateStr)) / 1000);
  if (!isFinite(secs)) return '';
  if (secs < 60) return 'just now';
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs === 1 ? '' : 's'} ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
  return new Date(dateStr).toLocaleDateString();
}

async function loadRoomwiseData() {
  try {
    const response = await fetch(ROOMWISE_ITEMS_URL, { headers: authHeaders() });
    if (!response.ok) {
      // Try to extract useful error details
      let detail = '';
      try { detail = await response.text(); } catch (_) {}
      throw new Error(`Roomwise items failed: ${response.status} ${response.statusText} ${detail}`.trim());
    }
    const data = await response.json();
    return Array.isArray(data) ? data : data.results || data;
  } catch (err) {
    console.warn('Roomwise endpoint failed:', err);
    return null;
  }
}

async function loadAllRoomsAndItems() {
  const roomsResponse = await fetch(ROOMS_URL, { headers: authHeaders() });
  if (!roomsResponse.ok) {
    let detail = '';
    try { detail = await roomsResponse.text(); } catch (_) {}
    throw new Error(`Rooms fetch failed: ${roomsResponse.status} ${roomsResponse.statusText} ${detail}`.trim());
  }

  const roomsResult = await roomsResponse.json();
  console.log(' Raw rooms API response:', roomsResult);
  const rooms = Array.isArray(roomsResult) ? roomsResult : roomsResult.results || [];
  console.log(` Extracted ${rooms.length} rooms from API`);
  if (!rooms || rooms.length === 0) return [];

  // Transform rooms to display format
  let roomsData = rooms.map(room => ({
    room_id: room.room_id,
    room_name: room.room_name,
    room_type: room.room_type,
    location: room.location,
    room_key: room.room_key,
    items: [],
    total_quantity: 0,
    item_count: 0,
    last_updated: null
  }));

  // Fan every item into its room bucket; unassigned items pool into General
  // Storage (created only if something actually lands there).
  const itemsResponse = await fetch(ITEMS_URL, { headers: authHeaders() });
  if (itemsResponse.ok) {
    const itemsResult = await itemsResponse.json();
    const items = Array.isArray(itemsResult) ? itemsResult : itemsResult.results || [];
    const byRoom = new Map(roomsData.map(r => [r.room_id, r]));
    let general = null;

    items.forEach(item => {
      const roomId = (item.room && (item.room.room_id ?? item.room)) ?? null;
      let bucket = roomId != null ? byRoom.get(roomId) : null;
      if (!bucket) {
        if (!general) {
          general = {
            room_id: null, room_name: 'General Storage', room_type: 'storage',
            location: 'N/A', room_key: false, items: [], total_quantity: 0,
            item_count: 0, last_updated: null
          };
          roomsData.push(general);
        }
        bucket = general;
      }
      bucket.items.push({
        item_id: item.item_id,
        item_name: item.item_name,
        category: item.category_name || (item.category && item.category.category_name) || item.category || 'Uncategorized',
        unit: item.unit,
        quantity: item.quantity,
        min_quantity: item.min_quantity,
        is_low_stock: item.quantity <= item.min_quantity,
        updated_at: item.updated_at || null
      });
      bucket.total_quantity += item.quantity;
      bucket.item_count += 1;
      if (item.updated_at && (!bucket.last_updated || item.updated_at > bucket.last_updated)) {
        bucket.last_updated = item.updated_at;
      }
    });
  }

  return roomsData;
}

async function loadRoomKeys() {
  try {
    const res = await fetch(ROOM_KEYS_URL, { headers: authHeaders() });
    if (!res.ok) {
      console.warn('Room keys fetch failed', res.status);
      return;
    }
    const data = await res.json();
    roomKeys = Array.isArray(data) ? data : data.results || [];
    console.log(` Loaded ${roomKeys.length} keys:`, roomKeys);
    roomKeys.forEach(k => {
      console.log(`- Key #${k.key_number} (Room: ${k.room_name}): Status = ${k.status}, Assigned to = ${k.assigned_to_name || 'None'}`);
    });
  } catch (err) {
    console.error('Failed to load room keys', err);
  }
}

async function loadKeyBorrows() {
  try {
    const res = await fetch(`${KEY_BORROW_URL}?status=pending`, { headers: authHeaders() });
    if (!res.ok) {
      console.warn('Key borrows fetch failed', res.status);
      return;
    }
    const data = await res.json();
    keyBorrows = Array.isArray(data) ? data : data.results || [];
    console.log(` Loaded ${keyBorrows.length} pending key requests`);
  } catch (err) {
    console.error('Failed to load key borrows', err);
  }
}

async function loadActiveBorrows() {
  try {
    const res = await fetch(`${KEY_BORROW_URL}active_borrow/`, { headers: authHeaders() });
    if (!res.ok) {
      console.warn('Active borrows fetch failed', res.status);
      return;
    }
    const data = await res.json();
    activeBorrows = Array.isArray(data) ? data : data.results || [];
    console.log(` Loaded ${activeBorrows.length} active key borrows (currently in use):`, activeBorrows);
    if (activeBorrows.length > 0) {
      activeBorrows.forEach(b => {
        console.log(`- Key ID: ${b.key}, Key Number: ${b.key_number}, Borrower ID: ${b.borrower}, Borrower: ${b.borrower_name}, Status: ${b.status}`);
      });
    }
  } catch (err) {
    console.error('Failed to load active borrows', err);
  }
}

// The viewer's own borrow requests (every status). Staff/admin see per-key
// requests through the pending box instead, so this call is viewer-only.
async function loadMyBorrows() {
  if (userRole !== 'viewer') { myBorrows = []; return; }
  try {
    const res = await fetch(`${KEY_BORROW_URL}my_requests/`, { headers: authHeaders() });
    if (!res.ok) {
      console.warn('My key borrows fetch failed', res.status);
      return;
    }
    const data = await res.json();
    myBorrows = Array.isArray(data) ? data : data.results || [];
    console.log(` Loaded ${myBorrows.length} of my key borrows`);
  } catch (err) {
    console.error('Failed to load my key borrows', err);
  }
}

// The viewer's still-open borrow for a given key, if any.
function getMyBorrowForKey(keyId) {
  return myBorrows.find(
    b => (b.key === keyId || b.key_id === keyId) && BORROW_ACTIVE_STATUSES.includes(b.status)
  );
}

// Render room cards
function renderRooms(roomsData, container) {
  const grid = document.createElement('div');
  grid.className = 'rooms-grid';

  let totalItems = 0, totalQuantity = 0, lowStockCount = 0;

  roomsData.forEach(room => {
    grid.appendChild(createRoomCard(room));
    (room.items || []).forEach(item => {
      totalItems++;
      totalQuantity += item.quantity;
      if (item.is_low_stock) lowStockCount++;
    });
  });

  container.appendChild(grid);

  document.getElementById('totalRooms').textContent = roomsData.length;
  document.getElementById('totalItems').textContent = totalItems;
  document.getElementById('totalQuantity').textContent = totalQuantity;
  document.getElementById('lowStockCount').textContent = lowStockCount;
}

function prop(iconName, label, value, valueClass = '') {
  return `<div class="room-prop">${icon(iconName)}` +
    `<span class="room-prop-label">${label}</span>` +
    `<span class="room-prop-value ${valueClass}">${value}</span></div>`;
}

function createRoomCard(room) {
  const card = document.createElement('div');
  card.className = 'room-card';

  const key = getKeyForRoom(room.room_name);
  const keyStatus = key ? formatKeyStatus(key.status) : 'No key record';
  const keyState = key ? key.status : 'none';

  const updatedLabel = room.last_updated ? relTime(room.last_updated) : '';

  card.innerHTML = `
    <div class="room-card-head">
      <h3 class="room-name">${room.room_name || 'Unknown Room'}</h3>
      <span class="room-type-badge">${room.room_type || 'room'}</span>
    </div>
    ${updatedLabel ? `<div class="room-updated" title="${new Date(room.last_updated).toLocaleString()}">${icon('clock')}Updated ${updatedLabel}</div>` : ''}
    <div class="room-props">
      ${prop('pin', 'Location', room.location || 'Not specified')}
      ${prop('key', 'Key', keyStatus, 'key-state key-' + keyState)}
      ${prop('hash', 'Room ID', room.room_id ?? 'N/A')}
    </div>
    <div class="room-summary">
      <div class="room-metric">
        <div class="room-metric-value">${room.item_count ?? 0}</div>
        <div class="room-metric-label">Items</div>
      </div>
      <div class="room-metric">
        <div class="room-metric-value">${room.total_quantity ?? 0}</div>
        <div class="room-metric-label">Units</div>
      </div>
    </div>
    <div class="room-actions"></div>
  `;

  const actions = card.querySelector('.room-actions');
  const activeBorrow = key
    ? activeBorrows.find(b => b.key === key.key_id || b.key_id === key.key_id)
    : null;

  if (userRole === 'viewer') {
    const myBorrow = key ? getMyBorrowForKey(key.key_id) : null;

    if (myBorrow && myBorrow.status === 'borrowed') {
      // The key is in this viewer's hands - offer the return.
      actions.insertAdjacentHTML('beforeend',
        `<div class="room-note note-warn">${icon('key')}You have this key</div>`);
      const btn = document.createElement('button');
      btn.className = 'btn btn-secondary btn-sm';
      btn.innerHTML = icon('undo') + 'Return Key';
      btn.addEventListener('click', e => { e.stopPropagation(); openReturnKeyModal(myBorrow); });
      actions.appendChild(btn);
    } else if (myBorrow && myBorrow.status === 'approved') {
      // Approved but not yet collected - let the viewer confirm the handover.
      actions.insertAdjacentHTML('beforeend',
        `<div class="room-note note-warn">${icon('check')}Approved &mdash; collect the key to start your borrow</div>`);
      const btn = document.createElement('button');
      btn.className = 'btn btn-primary btn-sm';
      btn.innerHTML = icon('key') + 'Collect Key';
      btn.addEventListener('click', e => { e.stopPropagation(); collectKey(myBorrow.borrow_id); });
      actions.appendChild(btn);
    } else if (myBorrow && myBorrow.status === 'pending') {
      actions.insertAdjacentHTML('beforeend',
        `<div class="room-note note-warn">${icon('clock')}Your key request is awaiting approval</div>`);
    } else if (activeBorrow) {
      actions.insertAdjacentHTML('beforeend',
        `<div class="room-note note-warn">${icon('key')}In use by ${activeBorrow.borrower_name || 'someone'}</div>`);
    } else if (key && key.status === 'available') {
      const btn = document.createElement('button');
      btn.className = 'btn btn-primary btn-sm';
      btn.innerHTML = icon('key') + 'Request Key';
      btn.addEventListener('click', e => { e.stopPropagation(); openRequestKeyModal(room); });
      actions.appendChild(btn);
    } else if (key && key.status === 'reserved') {
      actions.insertAdjacentHTML('beforeend',
        `<div class="room-note note-warn">${icon('key')}Key unavailable &mdash; reserved for another borrower</div>`);
    } else if (key && key.status !== 'available') {
      actions.insertAdjacentHTML('beforeend',
        `<div class="room-note note-danger">${icon('alert')}Key ${String(key.status).toUpperCase()}</div>`);
    }
  }

  if (key && ['staff', 'admin', 'manager'].includes(userRole)) {
    const pending = getPendingRequestsForKey(key.key_id);
    if (pending.length > 0) {
      const box = document.createElement('div');
      box.className = 'room-pending';
      box.innerHTML = `<div class="room-pending-title">Pending requests (${pending.length})</div>`;
      pending.slice(0, 2).forEach(req => {
        const row = document.createElement('div');
        row.className = 'room-pending-row';

        const meta = document.createElement('div');
        meta.className = 'room-pending-meta';

        const name = document.createElement('span');
        name.className = 'room-pending-name';
        name.textContent = req.borrower_name || 'Viewer';
        meta.appendChild(name);

        const subParts = [];
        if (req.purpose) subParts.push(req.purpose);
        if (req.expected_return_at) {
          subParts.push('Due ' + new Date(req.expected_return_at).toLocaleString());
        }
        if (subParts.length) {
          const sub = document.createElement('span');
          sub.className = 'room-pending-sub';
          sub.textContent = subParts.join(' · ');
          meta.appendChild(sub);
        }
        row.appendChild(meta);

        const btn = document.createElement('button');
        btn.className = 'btn btn-primary btn-sm';
        btn.textContent = 'Approve';
        btn.addEventListener('click', async e => { e.stopPropagation(); await approveKeyRequest(req.borrow_id); });
        row.appendChild(btn);

        box.appendChild(row);
      });
      actions.appendChild(box);
    }
  }

  if (!actions.children.length) actions.remove();

  const hasItems = !!(room.items && room.items.length);

  // General Storage opens expanded so a freshly stocked-in item is visible
  // without a click; every other room stays collapsed until clicked.
  let expanded = hasItems && isGeneralStorage(room);
  if (expanded) {
    card.classList.add('is-expanded');
    card.appendChild(createItemsList(room.items));
  }

  // Click the card to expand / collapse its item list
  card.addEventListener('click', () => {
    if (!hasItems) return;
    expanded = !expanded;
    card.classList.toggle('is-expanded', expanded);
    const list = card.querySelector('.room-items-list');
    if (list) {
      list.hidden = !expanded;
    } else if (expanded) {
      card.appendChild(createItemsList(room.items));
    }
  });

  return card;
}

function createItemsList(items) {
  const wrap = document.createElement('div');
  wrap.className = 'room-items-list';
  wrap.innerHTML = `<h4 class="room-items-title">${icon('items')}Items in this room</h4>`;

  items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'room-item-row' + (item.is_low_stock ? ' is-low' : '');
    row.innerHTML =
      `<span class="room-item-name">${item.item_name}</span>` +
      `<span class="room-item-qty">${item.quantity} ${item.unit || ''}</span>`;
    wrap.appendChild(row);
  });

  return wrap;
}
function getKeyForRoom(roomName) {
  return roomKeys.find(k => k.room_name === roomName);
}

function formatKeyStatus(status) {
  if (!status) return 'Unknown';
  if (status === 'available') return 'Available';
  if (status === 'reserved') return 'Reserved';
  if (status === 'in_use') return 'In Use';
  if (status === 'maintenance') return 'Maintenance';
  if (status === 'lost') return 'Lost';
  return status;
}

function getPendingRequestsForKey(keyId) {
  return keyBorrows.filter(req => req.key === keyId || req.key_id === keyId);
}

async function approveKeyRequest(borrowId) {
  try {
    const res = await fetch(`${KEY_BORROW_URL}${borrowId}/approve/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
    });
    if (!res.ok) {
      throw new Error(await extractError(res, 'Approve failed'));
    }
    console.log(' Key request approved successfully');
    await refreshKeyData();
    await loadRecentActivity(); // Refresh activity section to show updated key borrow info
  } catch (err) {
    console.error('Approve request failed', err);
    alert(err.message || 'Approve failed');
  }
}

// Viewer confirms they have physically collected an approved key.
// This is what flips the key to "in use" and unlocks the return option.
async function collectKey(borrowId) {
  try {
    const res = await fetch(`${KEY_BORROW_URL}${borrowId}/pickup/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
    });
    if (!res.ok) {
      throw new Error(await extractError(res, 'Could not collect the key'));
    }
    await refreshKeyData();
    await loadRecentActivity();
    alert('Key collected. It stays assigned to you until you return it.');
  } catch (err) {
    console.error('Collect key failed', err);
    alert(err.message || 'Could not collect the key');
  }
}

function openRequestKeyModal(room) {
  selectedRoomForKey = room;
  const modal = document.getElementById('requestKeyModal');
  const roomLabel = document.getElementById('requestRoomName');
  const keySelect = document.getElementById('requestKeySelect');
  const errorBox = document.getElementById('requestKeyError');
  const returnInput = document.getElementById('requestReturn');

  if (roomLabel) roomLabel.textContent = room.room_name || 'Selected Room';
  if (errorBox) errorBox.textContent = '';

  if (keySelect) {
    keySelect.innerHTML = '';
    const matched = roomKeys.filter(k => k.room_name === room.room_name);
    if (!matched.length) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'No key found for this room';
      keySelect.appendChild(opt);
      keySelect.disabled = true;
    } else {
      keySelect.disabled = false;
      matched.forEach(k => {
        const opt = document.createElement('option');
        opt.value = k.key_id;
        opt.textContent = `${k.key_number} — ${k.room_name}`;
        keySelect.appendChild(opt);
      });
    }
  }

  // Prefill expected return to +2 hours from now for convenience
  if (returnInput) {
    const now = new Date();
    const plus2h = new Date(now.getTime() + 2 * 60 * 60 * 1000);
    // ISO string without seconds for datetime-local compatibility
    const local = new Date(plus2h.getTime() - plus2h.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    returnInput.value = local;
  }

  if (modal) modal.classList.add('show');
}

function closeRequestKeyModal() {
  const modal = document.getElementById('requestKeyModal');
  if (modal) modal.classList.remove('show');
}

async function submitKeyRequest(e) {
  if (e) e.preventDefault();
  const keySelect = document.getElementById('requestKeySelect');
  const purposeInput = document.getElementById('requestPurpose');
  const returnInput = document.getElementById('requestReturn');
  const errorBox = document.getElementById('requestKeyError');

  if (!keySelect || !purposeInput || !returnInput) return;

  if (!keySelect.value) {
    errorBox.textContent = 'No key available for this room.';
    return;
  }

  if (!purposeInput.value.trim()) {
    errorBox.textContent = 'Please enter a purpose.';
    return;
  }

  if (!returnInput.value) {
    errorBox.textContent = 'Please set expected return time.';
    return;
  }

  errorBox.textContent = '';

  const payload = {
    key: Number(keySelect.value),
    purpose: purposeInput.value.trim() || 'Room access',
    expected_return_at: new Date(returnInput.value).toISOString()
  };

  try {
    const res = await fetch(KEY_BORROW_URL, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(await extractError(res, 'Failed to submit request.'));
    }

    const result = await res.json();
    console.log(' Key request submitted:', result);

    // Clear form
    purposeInput.value = '';
    returnInput.value = '';

    // Reload data to show updated status
    await refreshKeyData();

    closeRequestKeyModal();
    alert(`Key request submitted successfully!\nRoom: ${selectedRoomForKey?.room_name}\nStatus: Pending staff approval`);
  } catch (err) {
    console.error('Key request error', err);
    errorBox.textContent = err.message || 'Failed to submit request.';
  }
}

function openReturnKeyModal(borrow) {
  selectedBorrowForReturn = borrow;
  const modal = document.getElementById('returnKeyModal');
  const keyNumberDiv = document.getElementById('returnKeyNumber');
  const roomNameDiv = document.getElementById('returnRoomName');
  const errorBox = document.getElementById('returnKeyError');
  const locationInput = document.getElementById('returnLocation');

  if (keyNumberDiv) keyNumberDiv.textContent = borrow.key_number || 'Unknown';
  if (roomNameDiv) roomNameDiv.textContent = borrow.room_name || 'Unknown';
  if (errorBox) errorBox.textContent = '';
  if (locationInput) locationInput.value = '';

  if (modal) modal.classList.add('show');
}

function closeReturnKeyModal() {
  const modal = document.getElementById('returnKeyModal');
  if (modal) modal.classList.remove('show');
}

async function submitReturnKey(e) {
  if (e) e.preventDefault();
  
  if (!selectedBorrowForReturn) {
    alert('Error: No borrow selected');
    return;
  }

  const locationInput = document.getElementById('returnLocation');
  const errorBox = document.getElementById('returnKeyError');

  if (!locationInput) return;

  if (!locationInput.value.trim()) {
    errorBox.textContent = 'Please specify return location.';
    return;
  }

  errorBox.textContent = '';

  const payload = {
    location: locationInput.value.trim()
  };

  try {
    const borrowId = selectedBorrowForReturn.borrow_id;
    const res = await fetch(`${KEY_BORROW_URL}${borrowId}/return_key/`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(await extractError(res, 'Return failed'));
    }

    const result = await res.json();
    console.log(' Key returned:', result);

    // Reload data to show updated status
    await refreshKeyData();
    await loadRecentActivity();

    closeReturnKeyModal();
    alert(`Key returned successfully!\nKey: ${selectedBorrowForReturn.key_number}\nLocation: ${locationInput.value}`);
  } catch (err) {
    console.error('Key return error', err);
    const errorBox = document.getElementById('returnKeyError');
    errorBox.textContent = err.message || 'Failed to return key.';
  }
}

// Load and display recent activity
async function loadRecentActivity() {
  const activityList = document.getElementById('activityList');
  const roomMovesList = document.getElementById('roomMovesList');

  if (!activityList && !roomMovesList) return;

  // Set loading state
  if (activityList) {
    activityList.innerHTML = '<li class="empty-activity">Loading...</li>';
  }
  if (roomMovesList) {
    roomMovesList.innerHTML = '<li class="empty-activity">Loading...</li>';
  }

  try {
    const res = await fetch(ROOMWISE_ACTIVITY_URL, { headers: authHeaders() });
    if (!res.ok) {
      throw new Error('Failed to load activity: ' + res.status);
    }

    const data = await res.json();
    console.log(' Activity data received:', data);
    console.log('- Transactions:', data.recent_transactions?.length || 0);
    console.log('- Key borrows:', data.recent_key_borrows?.length || 0);
    
    // Render recent transactions (stock in/out)
    if (activityList) {
      const transactions = Array.isArray(data.recent_transactions) ? data.recent_transactions : [];
      activityList.innerHTML = '';
      
      if (transactions.length === 0) {
        activityList.innerHTML = '<li class="empty-activity">No recent activity</li>';
      } else {
        transactions.slice(0, 5).forEach(txn => {
          const dir = txn.type === 'IN' ? 'in' : 'out';
          const iconName = txn.type === 'IN' ? 'arrow-down' : 'arrow-up';
          const action = txn.type === 'IN' ? 'Stock In' : txn.type === 'OUT' ? 'Stock Out' : 'Adjustment';
          const detailTime = txn.timestamp ? new Date(txn.timestamp).toLocaleString() : 'Recently';

          const li = document.createElement('li');
          li.className = 'activity-item';
          li.innerHTML = '<div class="activity-icon ' + dir + '">' + icon(iconName) + '</div>' +
            '<div class="activity-content">' +
            '<div class="activity-title">' + action + ' &bull; ' + txn.quantity + ' units</div>' +
            '<div class="activity-detail">' + txn.item_name + ' &bull; ' + txn.user_name + ' &bull; ' + detailTime + '</div>' +
            '</div>';
          activityList.appendChild(li);
        });
      }
    }

    // Render recent key activities
    if (roomMovesList) {
      const keyBorrows = Array.isArray(data.recent_key_borrows) ? data.recent_key_borrows : [];
      console.log(' Processing key activities:');
      console.log('- Key borrows array:', keyBorrows.length);
      roomMovesList.innerHTML = '';

      // Sort key borrows by most recent timestamp
      const allActivities = keyBorrows.map(borrow => ({
        type: 'key',
        timestamp: borrow.returned_at || borrow.borrowed_at || borrow.approved_at || borrow.requested_at,
        data: borrow
      }));
      allActivities.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      console.log('- Key activities:', allActivities.length);

      if (allActivities.length === 0) {
        roomMovesList.innerHTML = '<li class="empty-activity">No recent key activities</li>';
      } else {
        allActivities.slice(0, 8).forEach(activity => {
          const li = document.createElement('li');
          li.className = 'activity-item';

          const borrow = activity.data;
          const statusMap = {
            returned: { ic: 'check', cls: 'in', text: 'Returned' },
            borrowed: { ic: 'key', cls: 'key', text: 'Currently holding' },
            approved: { ic: 'check', cls: 'in', text: 'Approved' }
          };
          const st = statusMap[borrow.status] || { ic: 'clock', cls: 'out', text: 'Requested' };
          const when = activity.timestamp ? new Date(activity.timestamp).toLocaleString() : '';

          // Build detailed borrower information
          let borrowerDetails = borrow.borrower_name;
          if (borrow.status === 'borrowed') {
            const details = [];
            if (borrow.borrower_phone) details.push('Phone: ' + borrow.borrower_phone);
            if (borrow.borrower_email) details.push('Email: ' + borrow.borrower_email);
            if (borrow.borrower_department) details.push('Dept: ' + borrow.borrower_department);
            if (borrow.purpose) details.push('Purpose: ' + borrow.purpose);
            if (borrow.expected_return_at) {
              const returnDate = new Date(borrow.expected_return_at);
              const isOverdue = returnDate < new Date();
              details.push((isOverdue ? 'Overdue &mdash; due ' : 'Due ') + returnDate.toLocaleString());
            }
            if (details.length > 0) {
              borrowerDetails += ' &bull; ' + details.join(' &bull; ');
            }
          }

          li.innerHTML = '<div class="activity-icon ' + st.cls + '">' + icon(st.ic) + '</div>' +
            '<div class="activity-content">' +
            '<div class="activity-title">Key ' + st.text + ' &bull; ' + borrow.key_number + ' (' + borrow.room_name + ')</div>' +
            '<div class="activity-detail">' + borrowerDetails + (when ? ' &bull; ' + when : '') + '</div>' +
            '</div>';

          roomMovesList.appendChild(li);
        });
      }
    }
  } catch (err) {
    console.error('Failed to load recent activity:', err);
    if (activityList) {
      activityList.innerHTML = '<li class="empty-activity">Error loading activity</li>';
    }
    if (roomMovesList) {
      roomMovesList.innerHTML = '<li class="empty-activity">Error loading key activities</li>';
    }
  }
}

