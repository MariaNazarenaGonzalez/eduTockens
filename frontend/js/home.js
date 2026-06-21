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
 * Renderizar transacciones en la UI
 */
function renderTransactions(transactions) {
  const container = document.getElementById('transactions-list');

  if (!transactions || transactions.length === 0) {
    container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">Sin transacciones</div>';
    return;
  }

  container.innerHTML = transactions.map(tx => `
    <div class="tx-item" onclick="viewTransaction('${tx.id}')">
      <div class="tx-icon ${tx.tx_type === 'EARN' ? 'income' : 'expense'}">
        ${tx.tx_type === 'EARN' ? '📈' : '📉'}
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

/**
 * Ver detalle de una transacción
 */
function viewTransaction(txId) {
  // TODO: Implementar vista de detalle de transacción
  console.log('Viewing transaction:', txId);
}

// Inicializar dashboard al cargar la página
window.addEventListener('DOMContentLoaded', initDashboard);
