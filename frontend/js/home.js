/* DEO GLORIA */

// home.js — Dashboard del estudiante: balance e historial reciente.
//
// Dependencias (cargadas antes en el HTML):
//   common.js — getToken, requireAuth, getCurrentUser, logout, goTo

requireAuth();

/**
 * Cargar datos iniciales del estudiante
 */
async function initDashboard() {
  const user = getCurrentUser();
  document.getElementById('student-name').textContent = user.name || 'Estudiante';

  await loadBalance();
  await loadTransactions();
}

/**
 * Cargar saldo del estudiante.
 * GET /students/{legajo}/balance devuelve { legajo, public_key, balance, nonce }.
 */
async function loadBalance() {
  try {
    const user = getCurrentUser();

    const response = await fetch(`${API_BASE_URL}/students/${user.legajo}/balance`, {
      headers: getAuthHeaders()
    });

    if (response.ok) {
      const data = await response.json();
      const balance = data.balance ?? 0;

      document.getElementById('balance-amount').textContent = balance;
    }
  } catch (error) {
    console.error('Error loading balance:', error);
  }
}

/**
 * Cargar historial de transacciones.
 * GET /students/{legajo}/transactions devuelve una lista de
 * { id, tx_type, counterparty_pubkey, amount, concept, nct_tx_id, created_at }.
 */
async function loadTransactions() {
  try {
    const user = getCurrentUser();

    const response = await fetch(`${API_BASE_URL}/students/${user.legajo}/transactions`, {
      headers: getAuthHeaders()
    });

    if (response.ok) {
      const transactions = await response.json();
      renderTransactions(transactions.slice(0, 5));
    }
  } catch (error) {
    console.error('Error loading transactions:', error);
  }
}

/**
 * Renderizar transacciones en la UI.
 * Usa íconos SVG direccionales: ↑ verde (EARN), ↓ rojo (SPEND).
 */
function renderTransactions(transactions) {
  // Ocultar skeleton
  const skeleton = document.getElementById('tx-skeleton');
  if (skeleton) skeleton.style.display = 'none';

  const container = document.getElementById('transactions-list');

  if (!transactions || transactions.length === 0) {
    container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">Sin transacciones aún</div>';
    return;
  }

  const arrowUp = '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 3v12M5 7l4-4 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const arrowDown = '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 15V3M5 11l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  container.innerHTML = transactions.map(tx => `
    <div class="tx-item stagger-item">
      <div class="tx-icon ${tx.tx_type === 'EARN' ? 'income' : 'expense'}">
        ${tx.tx_type === 'EARN' ? arrowUp : arrowDown}
      </div>
      <div class="tx-info">
        <div class="tx-name">${tx.concept || tx.tx_type}</div>
        <div class="tx-sub">${new Date(tx.created_at).toLocaleDateString('es-AR')}</div>
      </div>
      <div class="tx-amount ${tx.tx_type === 'EARN' ? 'income' : 'expense'}">
        ${tx.tx_type === 'EARN' ? '+' : '-'}${tx.amount}
      </div>
    </div>
  `).join('');
}

window.addEventListener('DOMContentLoaded', initDashboard);
