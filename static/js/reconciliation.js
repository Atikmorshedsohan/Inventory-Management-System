/**
 * Reconciliation Page
 * Compares each item's current balance against the sum of its stock ledger.
 * Base helpers (API_URL, token, userRole, formatDate) come from base.js.
 */

let reconReport = { rows: [] };

setActiveNav('reconciliationNav');

async function loadReconciliation() {
  const body = document.getElementById('reconBody');
  body.innerHTML = '<tr><td colspan="11" class="loading">Loading reconciliation…</td></tr>';
  try {
    const res = await fetch(`${API_URL}/reports/reconciliation/`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { logout(); return; }
    if (!res.ok) throw new Error('Request failed');
    reconReport = await res.json();
    renderSummary();
    renderRows();
  } catch (e) {
    console.error(e);
    body.innerHTML = '<tr><td colspan="11" class="error">Failed to load reconciliation report</td></tr>';
  }
}

function renderSummary() {
  document.getElementById('statTotal').textContent = reconReport.total_items ?? 0;
  document.getElementById('statBalanced').textContent = reconReport.balanced ?? 0;
  document.getElementById('statMismatched').textContent = reconReport.mismatched ?? 0;
  document.getElementById('statGenerated').textContent = reconReport.generated_at
    ? formatDate(reconReport.generated_at)
    : '—';

  const banner = document.getElementById('banner');
  if ((reconReport.mismatched ?? 0) === 0) {
    banner.className = 'recon-banner ok';
    banner.textContent = '✓ Every item balances against its transaction history.';
  } else {
    banner.className = 'recon-banner bad';
    banner.textContent = `⚠ ${reconReport.mismatched} item(s) do not match their ledger. `
      + 'A discrepancy means the quantity changed without a matching stock transaction.';
  }
  banner.classList.remove('hidden');
}

function visibleRows() {
  const q = document.getElementById('searchInput').value.trim().toLowerCase();
  const mismatchOnly = document.getElementById('mismatchOnly').checked;
  return (reconReport.rows || []).filter((r) => {
    if (mismatchOnly && r.status === 'balanced') return false;
    if (q && !r.item_name.toLowerCase().includes(q)) return false;
    return true;
  });
}

function renderRows() {
  const body = document.getElementById('reconBody');
  const rows = visibleRows();
  const canReconcile = userRole === 'admin' || userRole === 'manager';

  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="11" class="empty">No items match this view</td></tr>';
    return;
  }

  body.innerHTML = rows.map((r) => {
    const diff = r.discrepancy;
    const diffTxt = diff > 0 ? `+${diff}` : `${diff}`;
    const statusBadge = r.status === 'balanced'
      ? '<span class="pill ok">Balanced</span>'
      : `<span class="pill bad">${r.status === 'over' ? 'Over' : 'Short'}</span>`;
    const action = (r.status !== 'balanced' && canReconcile)
      ? `<button class="btn btn-primary btn-sm" onclick="reconcile(${r.item_id}, this)">Reconcile</button>`
      : '';
    return `<tr class="${r.status !== 'balanced' ? 'row-bad' : ''}">
      <td><strong>${r.item_name}</strong><div class="sub">${r.category}</div></td>
      <td>${r.room_name}</td>
      <td class="num">${r.system_quantity}</td>
      <td class="num">${r.opening_quantity}</td>
      <td class="num">${r.total_in}</td>
      <td class="num">${r.total_out}</td>
      <td class="num">${r.total_adjust}</td>
      <td class="num">${r.expected_quantity}</td>
      <td class="num ${diff !== 0 ? 'bad' : ''}">${diffTxt}</td>
      <td>${statusBadge}</td>
      <td class="num">${action}</td>
    </tr>`;
  }).join('');
}

async function reconcile(itemId, btn) {
  if (!confirm('Post an adjustment transaction so the ledger matches this item\'s counted balance?')) return;
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    if (csrftoken) headers['X-CSRFToken'] = csrftoken;
    const res = await fetch(`${API_URL}/reports/reconciliation/reconcile/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ item_id: itemId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to reconcile');
    await loadReconciliation();
    if (typeof loadNotificationBadge === 'function') loadNotificationBadge();
  } catch (e) {
    alert(`Error: ${e.message}`);
    btn.disabled = false;
    btn.textContent = 'Reconcile';
  }
}

function downloadCsv() {
  const rows = visibleRows();
  const head = ['Item', 'Category', 'Room', 'System Qty', 'Opening', 'IN', 'OUT', 'ADJUST', 'Expected', 'Discrepancy', 'Status'];
  const lines = [head.join(',')];
  rows.forEach((r) => {
    lines.push([
      `"${r.item_name}"`, `"${r.category}"`, `"${r.room_name}"`,
      r.system_quantity, r.opening_quantity, r.total_in, r.total_out, r.total_adjust,
      r.expected_quantity, r.discrepancy, r.status
    ].join(','));
  });
  const blob = new Blob([lines.join('\r\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `reconciliation_${new Date().toISOString().split('T')[0]}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function refresh() {
  loadReconciliation();
}

document.addEventListener('DOMContentLoaded', () => {
  setActiveNav('reconciliationNav');
  loadUserProfile();
  document.getElementById('searchInput').addEventListener('input', renderRows);
  document.getElementById('mismatchOnly').addEventListener('change', renderRows);
  loadReconciliation();
});
