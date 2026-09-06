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
let selectedRoomForKey = null;
let selectedBorrowForReturn = null;
let currentUserId = null;

// Auth headers helper (uses base.js if available)
function authHeaders(extra = {}) {
  // Try to get token from base.js first, then fallback to local storage
  let token = null;
  
  // Check if getAuthHeaders from base.js exists
  if (typeof getAuthHeaders === 'function') {
    console.log('✓ Using getAuthHeaders from base.js');
    return getAuthHeaders(extra);
  }
  
  // Fallback: get token from storage
  token = localStorage.getItem('access') || sessionStorage.getItem('access');
  console.log(`📌 Token found: ${token ? '✓ Yes (' + token.substring(0, 20) + '...)' : '❌ No'}`);
  
  const headers = { ...extra };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
    console.log(`📌 Built auth header: Bearer ${token.substring(0, 20)}...`);
  } else {
    console.warn('⚠️ No token found in localStorage or sessionStorage!');
  }
  return headers;
}

// Initialize page
document.addEventListener('DOMContentLoaded', async () => {
  setActiveNav('roomwiseNav');
  await loadUserProfileAndId();
  await loadRoomKeys();
  await loadKeyBorrows();
  await loadActiveBorrows();
  await loadAllData();
  await loadRecentActivity();
  // Auto-refresh every 60 seconds (1 minute)
  setInterval(async () => {
    await loadRoomKeys();
    await loadKeyBorrows();
    await loadActiveBorrows();
    await loadAllData();
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
      console.log(`👤 Current user ID: ${currentUserId}`);
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
    console.log(`🔍 loadRoomwiseData returned:`, roomsData ? `${roomsData.length} rooms` : 'null/empty');

    if (!roomsData || roomsData.length === 0) {
      console.log('⚠️ No rooms from roomwise endpoint, falling back to /api/rooms/');
      roomsData = await loadAllRoomsAndItems();
    }

    console.log(`✅ Final roomsData:`, roomsData ? `${roomsData.length} rooms` : 'empty');
    if (container) container.innerHTML = '';
    if (roomsData && roomsData.length > 0) {
      renderRooms(roomsData, container);
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
  console.log('📦 Raw rooms API response:', roomsResult);
  const rooms = Array.isArray(roomsResult) ? roomsResult : roomsResult.results || [];
  console.log(`📦 Extracted ${rooms.length} rooms from API`);
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
    item_count: 0
  }));

  // Optionally include unassigned items as a General Storage bucket
  const itemsResponse = await fetch(ITEMS_URL, { headers: authHeaders() });
  if (itemsResponse.ok) {
    const itemsResult = await itemsResponse.json();
    const items = Array.isArray(itemsResult) ? itemsResult : itemsResult.results || [];
    const unassignedItems = items.filter(item => !item.room);
    if (unassignedItems.length > 0) {
      roomsData.push({
        room_id: null,
        room_name: 'General Storage (Unassigned)',
        room_type: 'storage',
        location: 'N/A',
        room_key: false,
        items: unassignedItems.map(item => ({
          item_id: item.item_id,
          item_name: item.item_name,
          category: item.category_name || item.category || 'Uncategorized',
          unit: item.unit,
          quantity: item.quantity,
          min_quantity: item.min_quantity,
          is_low_stock: item.quantity <= item.min_quantity
        })),
        total_quantity: unassignedItems.reduce((sum, item) => sum + item.quantity, 0),
        item_count: unassignedItems.length
      });
    }
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
    console.log(`🔑 Loaded ${roomKeys.length} keys:`, roomKeys);
    roomKeys.forEach(k => {
      console.log(`  - Key #${k.key_number} (Room: ${k.room_name}): Status = ${k.status}, Assigned to = ${k.assigned_to_name || 'None'}`);
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
    console.log(`📥 Loaded ${keyBorrows.length} pending key requests`);
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
    console.log(`🔐 Loaded ${activeBorrows.length} active key borrows (currently in use):`, activeBorrows);
    if (activeBorrows.length > 0) {
      activeBorrows.forEach(b => {
        console.log(`  - Key ID: ${b.key}, Key Number: ${b.key_number}, Borrower ID: ${b.borrower}, Borrower: ${b.borrower_name}, Status: ${b.status}`);
      });
    }
  } catch (err) {
    console.error('Failed to load active borrows', err);
  }
}

// Render rooms in 4x4 grid layout
function renderRooms(roomsData, container) {
  console.log(`🎨 renderRooms() called with ${roomsData.length} rooms`, roomsData);
  
  // Create grid container
  const gridContainer = document.createElement('div');
  gridContainer.className = 'rooms-grid';
  gridContainer.style.cssText = `
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
  `;

  let totalItems = 0;
  let totalQuantity = 0;
  let lowStockCount = 0;

  roomsData.forEach(room => {
    const roomCard = createRoomCard(room);
    gridContainer.appendChild(roomCard);
    console.log(`✓ Added room card for: ${room.room_name}`);
    room.items.forEach(item => {
      totalItems++;
      totalQuantity += item.quantity;
      if (item.is_low_stock) lowStockCount++;
    });
  });

  container.appendChild(gridContainer);

  document.getElementById('totalRooms').textContent = roomsData.length;
  document.getElementById('totalItems').textContent = totalItems;
  document.getElementById('totalQuantity').textContent = totalQuantity;
  document.getElementById('lowStockCount').textContent = lowStockCount;
  console.log(`📊 Summary updated: ${roomsData.length} rooms, ${totalItems} items, ${totalQuantity} qty`);
}

function createRoomCard(room) {
  const card = document.createElement('div');
  card.className = 'room-card';
  card.style.cssText = `
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 20px;
    color: white;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    height: 100%;
  `;

  card.addEventListener('mouseenter', () => {
    card.style.transform = 'translateY(-5px)';
    card.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.15)';
  });

  card.addEventListener('mouseleave', () => {
    card.style.transform = 'translateY(0)';
    card.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.1)';
  });

  // Room name
  const roomName = document.createElement('h3');
  roomName.style.cssText = `
    margin: 0 0 15px 0;
    font-size: 18px;
    font-weight: 600;
  `;
  roomName.textContent = room.room_name || 'Unknown Room';
  card.appendChild(roomName);

  // Room info grid
  const infoGrid = document.createElement('div');
  infoGrid.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 15px;
    flex: 1;
  `;

  // Room Type
  const typeRow = createInfoRow('🏢', 'Type:', room.room_type || 'Unknown');
  infoGrid.appendChild(typeRow);

  // Location
  const locationRow = createInfoRow('📍', 'Location:', room.location || 'Not specified');
  infoGrid.appendChild(locationRow);

  // Key Status
  const key = getKeyForRoom(room.room_name);
  console.log(`🔍 Looking for key for room: ${room.room_name}, found:`, key);
  const keyStatus = key ? formatKeyStatus(key.status) : 'No key record';
  const keyIcon = key ? (key.status === 'available' ? '🟢' : '🟠') : '🔓';
  const keyRow = createInfoRow(keyIcon, 'Key:', keyStatus);
  infoGrid.appendChild(keyRow);

  // Room ID
  const idRow = createInfoRow('🆔', 'Room ID:', room.room_id || 'N/A');
  infoGrid.appendChild(idRow);

  card.appendChild(infoGrid);

  // Items summary box
  const itemsSummary = document.createElement('div');
  itemsSummary.style.cssText = `
    background: rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 12px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  `;

  const itemCountBox = createSummaryBox(`${room.item_count} Items`, 'Items');
  const quantityBox = createSummaryBox(`${room.total_quantity} Units`, 'Quantity');

  itemsSummary.appendChild(itemCountBox);
  itemsSummary.appendChild(quantityBox);
  card.appendChild(itemsSummary);

  const actions = document.createElement('div');
  actions.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 12px;
  `;

  // Check if key is in use (active borrow)
  const activeBorrow = key ? activeBorrows.find(b => b.key === key.key_id || b.key_id === key.key_id) : null;
  console.log(`📌 Room: ${room.room_name}, Key ID: ${key?.key_id}, Active Borrow Found:`, activeBorrow ? `Yes - Borrower ID: ${activeBorrow.borrower}` : 'No');
  console.log(`📌 Current User ID: ${currentUserId}, Key Status: ${key?.status}`);
  if (activeBorrow) {
    console.log(`📌 Active Borrow Details:`, activeBorrow);
  }

  if (userRole === 'viewer') {
    // Check if key is available (no active borrow AND status is available)
    const isKeyAvailable = !activeBorrow && key && key.status === 'available';
    const isKeyInUse = key && (key.status === 'in_use' || activeBorrow);
    
    console.log(`📌 Room ${room.room_name} - isKeyAvailable: ${isKeyAvailable}, isKeyInUse: ${isKeyInUse}, activeBorrow: ${!!activeBorrow}`);

    if (isKeyAvailable) {
      // Key is available - show request button
      const requestBtn = document.createElement('button');
      requestBtn.textContent = '🔑 Request Key';
      requestBtn.style.cssText = `
        background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
        color: white;
        border: none;
        padding: 10px 14px;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        width: 100%;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      `;
      requestBtn.addEventListener('mouseenter', () => {
        requestBtn.style.transform = 'translateY(-1px)';
        requestBtn.style.boxShadow = '0 4px 10px rgba(0,0,0,0.25)';
      });
      requestBtn.addEventListener('mouseleave', () => {
        requestBtn.style.transform = 'translateY(0)';
        requestBtn.style.boxShadow = '0 2px 6px rgba(0,0,0,0.2)';
      });
      requestBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openRequestKeyModal(room);
      });
      actions.appendChild(requestBtn);
      console.log(`✅ Showing REQUEST KEY button for ${room.room_name}`);
    } else if (isKeyInUse && activeBorrow && activeBorrow.borrower === currentUserId) {
      // Current user has the key - show return button
      const returnBtn = document.createElement('button');
      returnBtn.textContent = '↩️ Return Key';
      returnBtn.style.cssText = `
        background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
        color: white;
        border: none;
        padding: 10px 14px;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        width: 100%;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      `;
      returnBtn.addEventListener('mouseenter', () => {
        returnBtn.style.transform = 'translateY(-1px)';
        returnBtn.style.boxShadow = '0 4px 10px rgba(0,0,0,0.25)';
      });
      returnBtn.addEventListener('mouseleave', () => {
        returnBtn.style.transform = 'translateY(0)';
        returnBtn.style.boxShadow = '0 2px 6px rgba(0,0,0,0.2)';
      });
      returnBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openReturnKeyModal(activeBorrow);
      });
      actions.appendChild(returnBtn);
      console.log(`✅ Showing RETURN KEY button for ${room.room_name} (borrowed by current user)`);
    } else if (isKeyInUse && activeBorrow) {
      // Someone else has the key - show info message
      const infoMsg = document.createElement('div');
      infoMsg.style.cssText = `
        background: #fff3cd;
        border: 1px solid #ffc107;
        color: #856404;
        padding: 8px 10px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
      `;
      infoMsg.textContent = `🔐 In use by ${activeBorrow.borrower_name}`;
      actions.appendChild(infoMsg);
      console.log(`✅ Showing INFO message for ${room.room_name} (in use by ${activeBorrow.borrower_name})`);
    } else if (key && key.status !== 'available' && !activeBorrow) {
      // Key is not available but no active borrow found (maybe in maintenance, lost, etc.)
      const statusMsg = document.createElement('div');
      statusMsg.style.cssText = `
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 8px 10px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
      `;
      statusMsg.textContent = `⚠️ Key status: ${key.status.toUpperCase()}`;
      actions.appendChild(statusMsg);
      console.log(`✅ Showing STATUS message for ${room.room_name} (status: ${key.status})`);
    } else {
      console.log(`❌ No button shown for ${room.room_name} - no condition matched`);
    }
  }

  if (key && ['staff', 'admin', 'manager'].includes(userRole)) {
    const pending = getPendingRequestsForKey(key.key_id);
    if (pending.length > 0) {
      const pendingBox = document.createElement('div');
      pendingBox.style.cssText = `
        background: rgba(255,255,255,0.15);
        border-radius: 6px;
        padding: 8px;
        color: #1b1b1b;
        background: #fff3cd;
      `;
      const title = document.createElement('div');
      title.style.fontWeight = '700';
      title.style.fontSize = '13px';
      title.textContent = `Pending Requests (${pending.length})`;
      pendingBox.appendChild(title);

      pending.slice(0, 2).forEach(req => {
        const row = document.createElement('div');
        row.style.cssText = `display:flex; justify-content: space-between; align-items:center; margin-top:6px; gap:6px; font-size:12px;`;
        const info = document.createElement('div');
        info.textContent = `${req.borrower_name || 'Viewer'} → ${req.purpose || 'Request'} (${req.expected_return_at ? new Date(req.expected_return_at).toLocaleString() : ''})`;
        const approveBtn = document.createElement('button');
        approveBtn.textContent = 'Approve';
        approveBtn.style.cssText = `background:#2e7d32; color:white; border:none; padding:6px 10px; border-radius:4px; cursor:pointer; font-weight:600;`;
        approveBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          await approveKeyRequest(req.borrow_id);
        });
        row.appendChild(info);
        row.appendChild(approveBtn);
        pendingBox.appendChild(row);
      });

      actions.appendChild(pendingBox);
    }
  }

  if (actions.children.length > 0) {
    card.appendChild(actions);
  }

  // Click to expand items
  let isExpanded = false;
  card.addEventListener('click', () => {
    if (room.items && room.items.length > 0) {
      isExpanded = !isExpanded;
      const itemsList = card.querySelector('.items-list');
      if (itemsList) {
        itemsList.style.display = isExpanded ? 'block' : 'none';
      } else if (isExpanded) {
        const list = createItemsList(room.items);
        card.appendChild(list);
      }
    }
  });

  return card;
}

function createInfoRow(icon, label, value) {
  const row = document.createElement('div');
  row.style.cssText = `
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
  `;
  row.innerHTML = `
    <span style="font-size: 16px;">${icon}</span>
    <span style="opacity: 0.9;">${label}</span>
    <span style="font-weight: 600;">${value}</span>
  `;
  return row;
}

function createSummaryBox(value, label) {
  const box = document.createElement('div');
  box.style.cssText = `
    text-align: center;
  `;
  box.innerHTML = `
    <div style="font-size: 16px; font-weight: 700;">${value}</div>
    <div style="font-size: 11px; opacity: 0.9;">${label}</div>
  `;
  return box;
}

function createItemsList(items) {
  const listContainer = document.createElement('div');
  listContainer.className = 'items-list';
  listContainer.style.cssText = `
    margin-top: 15px;
    padding-top: 15px;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
    max-height: 300px;
    overflow-y: auto;
  `;

  const itemsTitle = document.createElement('h4');
  itemsTitle.style.cssText = `
    margin: 0 0 10px 0;
    font-size: 12px;
    text-transform: uppercase;
    opacity: 0.9;
  `;
  itemsTitle.textContent = '📋 Items in this Room';
  listContainer.appendChild(itemsTitle);

  items.forEach(item => {
    const itemRow = document.createElement('div');
    itemRow.style.cssText = `
      background: rgba(255, 255, 255, 0.1);
      border-radius: 6px;
      padding: 8px;
      margin-bottom: 6px;
      font-size: 12px;
    `;

    const itemInfo = document.createElement('span');
    itemInfo.textContent = `${item.item_name} (${item.quantity} ${item.unit})`;

    itemRow.appendChild(itemInfo);
    listContainer.appendChild(itemRow);
  });

  return listContainer;
}

function getKeyForRoom(roomName) {
  return roomKeys.find(k => k.room_name === roomName);
}

function formatKeyStatus(status) {
  if (!status) return 'Unknown';
  if (status === 'available') return 'Available';
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
      const detail = await res.text();
      throw new Error(detail || 'Approve failed');
    }
    console.log('✅ Key request approved successfully');
    await loadRoomKeys();
    await loadKeyBorrows();
    await loadActiveBorrows();
    await loadRecentActivity(); // Refresh activity section to show updated key borrow info
    await loadAllData();
  } catch (err) {
    console.error('Approve request failed', err);
    alert(err.message || 'Approve failed');
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
      const detail = await res.text();
      throw new Error(detail || 'Request failed');
    }

    const result = await res.json();
    console.log('✅ Key request submitted:', result);

    // Clear form
    purposeInput.value = '';
    returnInput.value = '';
    
    // Reload data to show updated status
    await loadRoomKeys();
    await loadKeyBorrows();
    await loadActiveBorrows();
    await loadAllData();
    
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
      const detail = await res.text();
      throw new Error(detail || 'Return failed');
    }

    const result = await res.json();
    console.log('✅ Key returned:', result);

    // Reload data to show updated status
    await loadRoomKeys();
    await loadKeyBorrows();
    await loadActiveBorrows();
    await loadAllData();
    
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
    console.log('📊 Activity data received:', data);
    console.log('  - Transactions:', data.recent_transactions?.length || 0);
    console.log('  - Moves:', data.recent_moves?.length || 0);
    console.log('  - Key borrows:', data.recent_key_borrows?.length || 0);
    
    // Render recent transactions (stock in/out)
    if (activityList) {
      const transactions = Array.isArray(data.recent_transactions) ? data.recent_transactions : [];
      activityList.innerHTML = '';
      
      if (transactions.length === 0) {
        activityList.innerHTML = '<li class="empty-activity">No recent activity</li>';
      } else {
        transactions.slice(0, 5).forEach(txn => {
          const icon = txn.type === 'IN' ? '↓' : '↑';
          const iconClass = txn.type === 'IN' ? 'in' : 'out';
          const action = txn.type === 'IN' ? 'Stock In' : txn.type === 'OUT' ? 'Stock Out' : 'Adjustment';
          const detailTime = txn.timestamp ? new Date(txn.timestamp).toLocaleString() : 'Recently';
          
          const li = document.createElement('li');
          li.className = 'activity-item';
          li.innerHTML = '<div class="activity-icon ' + iconClass + '">' + icon + '</div>' +
            '<div class="activity-content">' +
            '<div class="activity-title">' + action + ' • ' + txn.quantity + ' units</div>' +
            '<div class="activity-detail">' + txn.item_name + ' • ' + txn.user_name + ' • ' + detailTime + '</div>' +
            '</div>';
          activityList.appendChild(li);
        });
      }
    }

    // Render recent room moves
    if (roomMovesList) {
      const moves = Array.isArray(data.recent_moves) ? data.recent_moves : [];
      const keyBorrows = Array.isArray(data.recent_key_borrows) ? data.recent_key_borrows : [];
      console.log('🏠 Processing room activities:');
      console.log('  - Moves array:', moves.length);
      console.log('  - Key borrows array:', keyBorrows.length);
      roomMovesList.innerHTML = '';
      
      // Combine moves and key borrows, sort by timestamp
      const allActivities = [];
      
      // Add room moves
      moves.forEach(move => {
        allActivities.push({
          type: 'move',
          timestamp: move.moved_at,
          data: move
        });
      });
      
      // Add key borrows
      keyBorrows.forEach(borrow => {
        const timestamp = borrow.returned_at || borrow.borrowed_at || borrow.approved_at || borrow.requested_at;
        allActivities.push({
          type: 'key',
          timestamp: timestamp,
          data: borrow
        });
      });
      
      // Sort by timestamp descending
      allActivities.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      console.log('  - Combined activities:', allActivities.length);
      console.log('  - Activities:', allActivities.map(a => `${a.type}: ${a.timestamp}`));
      
      if (allActivities.length === 0) {
        roomMovesList.innerHTML = '<li class="empty-activity">No recent room moves or key activities</li>';
      } else {
        allActivities.slice(0, 8).forEach(activity => {
          const li = document.createElement('li');
          li.className = 'activity-item';
          
          if (activity.type === 'move') {
            const move = activity.data;
            const when = move.moved_at ? new Date(move.moved_at).toLocaleString() : '';
            li.innerHTML = '<div class="activity-icon in">↔</div>' +
              '<div class="activity-content">' +
              '<div class="activity-title">' + move.item_name + ' • ' + (move.from_room_name || '—') + ' → ' + (move.to_room_name || '—') + '</div>' +
              '<div class="activity-detail">' + move.user_name + (when ? ' • ' + when : '') + '</div>' +
              '</div>';
          } else {
            const borrow = activity.data;
            const statusIcon = borrow.status === 'returned' ? '✓' : borrow.status === 'borrowed' ? '🔓' : borrow.status === 'approved' ? '👍' : '📝';
            const statusText = borrow.status === 'returned' ? 'Returned' : borrow.status === 'borrowed' ? 'Currently Holding' : borrow.status === 'approved' ? 'Approved' : 'Requested';
            const statusClass = borrow.status === 'returned' ? 'in' : 'out';
            const when = activity.timestamp ? new Date(activity.timestamp).toLocaleString() : '';
            
            // Build detailed borrower information
            let borrowerDetails = borrow.borrower_name;
            if (borrow.status === 'borrowed') {
              // Show more details for currently borrowed keys
              const details = [];
              if (borrow.borrower_phone) details.push('📞 ' + borrow.borrower_phone);
              if (borrow.borrower_email) details.push('✉️ ' + borrow.borrower_email);
              if (borrow.borrower_department) details.push('🏢 ' + borrow.borrower_department);
              if (borrow.purpose) details.push('📝 ' + borrow.purpose);
              if (borrow.expected_return_at) {
                const returnDate = new Date(borrow.expected_return_at);
                const isOverdue = returnDate < new Date();
                details.push((isOverdue ? '⚠️ ' : '🕐 ') + 'Expected return: ' + returnDate.toLocaleString());
              }
              
              if (details.length > 0) {
                borrowerDetails += ' • ' + details.join(' • ');
              }
            }
            
            li.innerHTML = '<div class="activity-icon ' + statusClass + '">' + statusIcon + '</div>' +
              '<div class="activity-content">' +
              '<div class="activity-title">Key ' + statusText + ' • ' + borrow.key_number + ' (' + borrow.room_name + ')</div>' +
              '<div class="activity-detail">' + borrowerDetails + (when ? ' • ' + when : '') + '</div>' +
              '</div>';
          }
          
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
      roomMovesList.innerHTML = '<li class="empty-activity">Error loading room moves</li>';
    }
  }
}

