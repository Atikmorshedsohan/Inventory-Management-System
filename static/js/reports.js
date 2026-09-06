let items = [];
let transactions = [];

/**
 * Reports Page - Specific functionality
 * Base functions inherited from base.js
 */

// Set active navigation
setActiveNav('reportsNav');

async function init() {
  setActiveNav('reportsNav');

  await loadUserProfile();
  await loadDashboardStats();
  await loadReports();
}

async function loadReports() {
  try {
    const [itemsRes, transRes] = await Promise.all([
      fetch(`${API_URL}/items/`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API_URL}/stock-transactions/`, { headers: { Authorization: `Bearer ${token}` } })
    ]);

    const itemsResponse = await itemsRes.json();
    const transactionsResponse = await transRes.json();

    items = itemsResponse.results || itemsResponse;
    transactions = transactionsResponse.results || transactionsResponse;

    renderLocationChart(transactions);
    renderCategoryChart(items);
    renderMovementChart(transactions);
    renderLowStockTable(items);
  } catch (error) {
    console.error('Error loading reports:', error);
    document.getElementById('locationChart').innerHTML = '<div style="padding:20px;text-align:center;color:#999;">Unable to load data</div>';
    document.getElementById('categoryChart').innerHTML = '<div style="padding:20px;text-align:center;color:#999;">Unable to load data</div>';
    document.getElementById('movementChart').innerHTML = '<div style="padding:20px;text-align:center;color:#999;">Unable to load data</div>';
  }
}

async function loadDashboardStats() {
  try {
    const res = await fetch(`${API_URL}/reports/dashboard/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) {
      const stats = await res.json();
      const totalEl = document.getElementById('statTotalItems');
      const lowEl = document.getElementById('statLowStock');
      const pendingEl = document.getElementById('statPendingReqs');
      if (totalEl) totalEl.textContent = stats.total_items ?? '—';
      if (lowEl) lowEl.textContent = stats.low_stock_items ?? '—';
      if (pendingEl) pendingEl.textContent = stats.pending_requisitions ?? '—';
    }
  } catch (error) {
    console.error('Failed to load dashboard stats', error);
  }
}

function renderLocationChart() {
  const locations = ['Lab 1', 'Lab 2', 'Lab 3', 'Classroom 305', 'Office Room'];
  const counts = [586, 520, 450, 330, 180];

  const ctx = document.getElementById('locationChart');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: locations,
      datasets: [
        {
          label: 'Items',
          data: counts,
          backgroundColor: '#3b82f6',
          borderRadius: 8,
          barThickness: 60
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 150 }
        }
      }
    }
  });
}

function renderCategoryChart(itemsData) {
  const catMap = new Map();
  itemsData.forEach((item) => {
    const catName = item.category?.category_name || 'Uncategorized';
    catMap.set(catName, (catMap.get(catName) || 0) + 1);
  });

  const labels = Array.from(catMap.keys());
  const data = Array.from(catMap.values());
  const total = data.reduce((a, b) => a + b, 0);
  const percentages = data.map((v) => `${((v / total) * 100).toFixed(0)}%`);

  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444'];

  const ctx = document.getElementById('categoryChart');
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.map((label, i) => `${label} ${percentages[i]}`),
      datasets: [
        {
          data,
          backgroundColor: colors,
          borderWidth: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: {
            padding: 15,
            font: { size: 12 },
            generateLabels(chart) {
              const dataset = chart.data.datasets[0];
              return chart.data.labels.map((label, i) => ({
                text: label,
                fillStyle: dataset.backgroundColor[i],
                hidden: false,
                index: i
              }));
            }
          }
        }
      }
    }
  });
}

function renderMovementChart(transactionsData) {
  // Get last 6 months dynamically
  const now = new Date();
  const months = [];
  const monthMap = new Map();
  
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const monthLabel = d.toLocaleDateString('en-US', { month: 'short' });
    const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    months.push(monthLabel);
    monthMap.set(monthKey, { in: 0, out: 0, label: monthLabel });
  }

  // Process transactions
  transactionsData.forEach((t) => {
    const date = new Date(t.timestamp || t.created_at);
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    
    if (monthMap.has(monthKey)) {
      const cur = monthMap.get(monthKey);
      const qty = t.quantity || 1;
      if (t.type === 'IN') cur.in += qty;
      else if (t.type === 'OUT') cur.out += qty;
    }
  });

  // Extract data for chart
  const stockInData = Array.from(monthMap.values()).map(m => m.in);
  const stockOutData = Array.from(monthMap.values()).map(m => m.out);

  const ctx = document.getElementById('movementChart');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months,
      datasets: [
        {
          label: 'Stock IN',
          data: stockInData,
          backgroundColor: '#10b981',
          borderRadius: 6,
          barThickness: 40
        },
        {
          label: 'Stock OUT',
          data: stockOutData,
          backgroundColor: '#3b82f6',
          borderRadius: 6,
          barThickness: 40
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            padding: 15,
            font: { size: 13 },
            usePointStyle: true,
            pointStyle: 'rect'
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 45 }
        },
        x: {
          grid: { display: false }
        }
      }
    }
  });
}

function renderLowStockTable(itemsData) {
  const lowStock = itemsData.filter((item) => item.quantity <= item.min_quantity);

  if (lowStock.length === 0) {
    document.getElementById('lowStockTable').innerHTML = '<tr><td colspan="5" style="text-align:center;color:#999;padding:20px;">No low stock items</td></tr>';
    return;
  }

  const tbody = lowStock
    .map(
      (item) => `
        <tr>
          <td><strong>${item.item_name}</strong></td>
          <td class="status-low">${item.quantity}</td>
          <td>${item.min_quantity}</td>
          <td class="status-low">-${item.min_quantity - item.quantity}</td>
          <td>${
            item.room?.room_name ||
            item.room_name ||
            (typeof item.room === 'string' ? item.room : null) ||
            (item.room_id ? `Room ${item.room_id}` : 'General Storage')
          }</td>
        </tr>
      `
    )
    .join('');

  document.getElementById('lowStockTable').innerHTML = tbody;
}

async function exportReport(format = 'csv') {
  try {
    const days = 90;
    const endpoint = format === 'excel' ? 'excel' : 'csv';
    const res = await fetch(`${API_URL}/reports/export/${endpoint}/?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) {
      alert(`Failed to export ${format.toUpperCase()}`);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().split('T')[0];
    const extension = format === 'excel' ? 'xlsx' : 'csv';
    link.href = url;
    link.download = `CSE_Inventory_Report_${timestamp}.${extension}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Export error', error);
    alert(`An error occurred while exporting the ${format.toUpperCase()}`);
  }
}

document.addEventListener('DOMContentLoaded', init);
