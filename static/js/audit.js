let allLogs = [];
let filteredLogs = [];
let currentPage = 1;
const logsPerPage = 50;

/**
 * Audit Page - Specific functionality
 * Base functions inherited from base.js
 */

// Set active navigation
setActiveNav('auditNav');

async function loadAuditLogs() {
  try {
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('tableContainer').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';

    const res = await fetch(`${API_URL}/audit-logs/?page_size=1000`, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (res.status === 401) {
      logout();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      allLogs = data.results || data;
      filteredLogs = [...allLogs];

      renderSummary();
      loadUsers();
      applyFilters();
    }
  } catch (error) {
    console.error('Error loading audit logs:', error);
  } finally {
    document.getElementById('loadingState').style.display = 'none';
  }
}

function renderSummary() {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const weekStart = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

  const todayCount = allLogs.filter((log) => new Date(log.timestamp) >= todayStart).length;
  const weekCount = allLogs.filter((log) => new Date(log.timestamp) >= weekStart).length;
  const monthCount = allLogs.filter((log) => new Date(log.timestamp) >= monthStart).length;

  document.getElementById('statTotal').textContent = allLogs.length;
  document.getElementById('statToday').textContent = todayCount;
  document.getElementById('statWeek').textContent = weekCount;
  document.getElementById('statMonth').textContent = monthCount;
}

async function loadUsers() {
  try {
    const res = await fetch(`${API_URL}/users/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) {
      const data = await res.json();
      const users = data.results || data;
      const select = document.getElementById('userFilter');
      users.forEach((user) => {
        const option = document.createElement('option');
        option.value = user.user_id;
        option.textContent = user.name;
        select.appendChild(option);
      });
    }
  } catch (error) {
    console.error('Failed to load users:', error);
  }
}

function applyFilters() {
  const searchText = document.getElementById('searchInput').value.toLowerCase();
  const userFilter = document.getElementById('userFilter').value;
  const periodFilter = document.getElementById('periodFilter').value;

  filteredLogs = allLogs.filter((log) => {
    const matchesSearch = !searchText || log.action.toLowerCase().includes(searchText);
    const matchesUser = !userFilter || (log.user && log.user.toString() === userFilter);

    let matchesPeriod = true;
    if (periodFilter !== 'all') {
      const logDate = new Date(log.timestamp);
      const now = new Date();

      if (periodFilter === 'today') {
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        matchesPeriod = logDate >= todayStart;
      } else if (periodFilter === 'week') {
        const weekStart = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        matchesPeriod = logDate >= weekStart;
      } else if (periodFilter === 'month') {
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
        matchesPeriod = logDate >= monthStart;
      }
    }

    return matchesSearch && matchesUser && matchesPeriod;
  });

  currentPage = 1;
  renderLogs();
}

function getActionType(action) {
  const lower = action.toLowerCase();
  if (lower.includes('created')) return 'create';
  if (lower.includes('approved')) return 'approve';
  if (lower.includes('rejected')) return 'reject';
  if (lower.includes('issued')) return 'issue';
  if (lower.includes('stock')) return 'stock';
  if (lower.includes('updated')) return 'update';
  if (lower.includes('deleted')) return 'delete';
  return 'update';
}

function renderLogs() {
  if (filteredLogs.length === 0) {
    document.getElementById('tableContainer').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
    document.getElementById('pagination').style.display = 'none';
    return;
  }

  document.getElementById('tableContainer').style.display = 'block';
  document.getElementById('emptyState').style.display = 'none';

  const startIndex = (currentPage - 1) * logsPerPage;
  const endIndex = startIndex + logsPerPage;
  const pageLogs = filteredLogs.slice(startIndex, endIndex);

  const tbody = document.getElementById('logsBody');
  tbody.innerHTML = pageLogs
    .map((log) => {
      const actionType = getActionType(log.action);
      return `
          <tr>
            <td>#${log.log_id}</td>
            <td>${log.user_name || 'System'}</td>
            <td><span class="action-type action-${actionType}">${log.action}</span></td>
            <td>${new Date(log.timestamp).toLocaleString()}</td>
          </tr>
        `;
    })
    .join('');

  renderPagination();
}

function renderPagination() {
  const totalPages = Math.ceil(filteredLogs.length / logsPerPage);

  if (totalPages <= 1) {
    document.getElementById('pagination').style.display = 'none';
    return;
  }

  document.getElementById('pagination').style.display = 'flex';
  const pagination = document.getElementById('pagination');
  pagination.innerHTML = '';

  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '← Previous';
  prevBtn.disabled = currentPage === 1;
  prevBtn.onclick = () => {
    if (currentPage > 1) {
      currentPage -= 1;
      renderLogs();
    }
  };
  pagination.appendChild(prevBtn);

  const maxButtons = 5;
  let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
  let endPage = Math.min(totalPages, startPage + maxButtons - 1);

  if (endPage - startPage + 1 < maxButtons) {
    startPage = Math.max(1, endPage - maxButtons + 1);
  }

  for (let i = startPage; i <= endPage; i += 1) {
    const pageBtn = document.createElement('button');
    pageBtn.className = `page-btn${i === currentPage ? ' active' : ''}`;
    pageBtn.textContent = i;
    pageBtn.onclick = () => {
      currentPage = i;
      renderLogs();
    };
    pagination.appendChild(pageBtn);
  }

  const nextBtn = document.createElement('button');
  nextBtn.className = 'page-btn';
  nextBtn.textContent = 'Next →';
  nextBtn.disabled = currentPage === totalPages;
  nextBtn.onclick = () => {
    if (currentPage < totalPages) {
      currentPage += 1;
      renderLogs();
    }
  };
  pagination.appendChild(nextBtn);
}

function bindFilters() {
  document.getElementById('searchInput').addEventListener('input', applyFilters);
  document.getElementById('userFilter').addEventListener('change', applyFilters);
  document.getElementById('periodFilter').addEventListener('change', applyFilters);
}

document.addEventListener('DOMContentLoaded', () => {
  setActiveNav('auditNav');
  loadUserProfile();
  bindFilters();
  loadAuditLogs();
});
