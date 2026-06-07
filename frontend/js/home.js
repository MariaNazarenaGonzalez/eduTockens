// TODO: Implement student dashboard logic for balance display and transaction history.

requireAuth();

const API_BASE_URL = '/api';

/**
 * Cargar datos iniciales del estudiante
 */
async function initDashboard() {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  document.getElementById('student-name').textContent = user.name || 'Estudiante';
  
  await loadBalance();
  await loadTransactions();
}

/**
 * Cargar saldo del estudiante
 */
async function loadBalance() {
  try {
    const token = getToken();
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    
    const response = await fetch(`${API_BASE_URL}/students/${user.legajo}/balance`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });

    if (response.ok) {
      const data = await response.json();
      const balance = data.balance || 0;
      
      document.getElementById('balance-amount').textContent = balance;
      document.getElementById('marketplace-balance').textContent = balance;
      
      // Actualizar métricas
      updateMetrics(balance, data);
    }
  } catch (error) {
    console.error('Error loading balance:', error);
  }
}

/**
 * Cargar historial de transacciones
 */
async function loadTransactions() {
  try {
    const token = getToken();
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    
    const response = await fetch(`${API_BASE_URL}/students/${user.legajo}/transactions`, {
      headers: { 'Authorization': 'Bearer ' + token }
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
      <div class="tx-icon ${tx.type === 'EARN' ? 'income' : 'expense'}">
        ${tx.type === 'EARN' ? '📈' : '📉'}
      </div>
      <div class="tx-info">
        <div class="tx-name">${tx.concept || tx.type}</div>
        <div class="tx-sub">${new Date(tx.timestamp).toLocaleDateString('es-AR')}</div>
      </div>
      <div class="tx-amount ${tx.type === 'EARN' ? 'income' : 'expense'}">
        ${tx.type === 'EARN' ? '+' : '-'}${tx.amount}
      </div>
    </div>
  `).join('');
}

/**
 * Actualizar métricas del dashboard
 */
function updateMetrics(balance, data) {
  const earned = data.earned || 0;
  const spent = data.spent || 0;
  const txCount = data.transaction_count || 0;
  
  document.getElementById('metric-earned').textContent = earned;
  document.getElementById('metric-spent').textContent = spent;
  document.getElementById('metric-transactions').textContent = txCount;
}

/**
 * Ver detalle de una transacción
 */
function viewTransaction(txId) {
  // TODO: Implementar vista de detalle de transacción
  console.log('Viewing transaction:', txId);
}

/**
 * Navegar a otra página
 */
function goTo(path) {
  if (path.startsWith('#')) {
    // Navegar a historial completo
    window.location.href = 'profile.html';
  } else {
    window.location.href = path;
  }
}

/**
 * Logout
 */
function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('user');
  window.location.href = 'login.html';
}

// Obtener token desde auth.js
function getToken() {
  return localStorage.getItem('token');
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = 'login.html';
  }
}

// Inicializar dashboard al cargar la página
window.addEventListener('DOMContentLoaded', initDashboard);