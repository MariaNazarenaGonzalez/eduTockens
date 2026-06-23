/* DEO GLORIA */

// wallet-page.js — Lógica para la página Academic Ledger.
// Carga balance, clave pública, historial de transacciones y
// estado de la wallet cifrada. Permite copiar la pubkey y
// resetear la wallet.

requireAuth();

// ── Helpers ──────────────────────────────────────────────────────

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2500);
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: '2-digit' });
}

// ── Init ─────────────────────────────────────────────────────────

let _user = null;

async function initWalletPage() {
  _user = getCurrentUser();
  if (!_user) {
    document.getElementById('balance-amount').textContent = 'Error';
    return;
  }

  document.getElementById('pubkey-value').textContent = _user.public_key || '—';

  // Wallet status
  const hasWallet = EduWallet.hasStoredKey(_user.legajo);
  const statusEl = document.getElementById('wallet-status');
  if (hasWallet) {
    statusEl.innerHTML = '<span class="status-dot green"></span> Clave privada cifrada en este navegador';
  } else {
    statusEl.innerHTML = '<span class="status-dot amber"></span> Sin clave privada guardada — no podés firmar SPEND';
  }

  // Balance from NCT
  try {
    const balRes = await fetch(`${API_BASE_URL}/students/${_user.legajo}/balance`, {
      headers: getAuthHeaders(),
    });
    if (!balRes.ok) throw new Error('No se pudo cargar el balance');

    const bal = await balRes.json();
    document.getElementById('balance-amount').textContent = bal.balance;
    document.getElementById('nonce-value').textContent = bal.nonce;
    document.getElementById('pending-nonce').textContent = bal.pending_nonce;
  } catch (e) {
    document.getElementById('balance-amount').textContent = '—';
    toast('Error al consultar el balance: ' + e.message);
  }

  // Transactions
  try {
    const txRes = await fetch(`${API_BASE_URL}/students/${_user.legajo}/transactions`, {
      headers: getAuthHeaders(),
    });
    if (!txRes.ok) throw new Error('No se pudieron cargar las transacciones');

    const txs = await txRes.json();
    renderTransactions(txs);
  } catch (e) {
    document.getElementById('tx-list').innerHTML =
      '<div class="tx-empty">Error al cargar el historial</div>';
    toast('Error: ' + e.message);
  }
}

function renderTransactions(txs) {
  const list = document.getElementById('tx-list');
  document.getElementById('tx-count').textContent = `${txs.length} tx`;

  if (!txs || txs.length === 0) {
    list.innerHTML = '<div class="tx-empty">Sin transacciones todavía</div>';
    return;
  }

  list.innerHTML = txs.map((tx) => {
    const isEarn = tx.tx_type === 'EARN';
    const typeClass = isEarn ? 'earn' : 'spend';
    const prefix = isEarn ? '+' : '−';
    const date = tx.created_at ? formatDate(tx.created_at) : '—';

    return `
      <div class="tx-row">
        <span class="tx-type ${typeClass}">${tx.tx_type}</span>
        <span class="tx-concept" title="${tx.concept}">${tx.concept}</span>
        <span class="tx-amount ${typeClass}">${prefix}${tx.amount}</span>
        <span class="tx-date">${date}</span>
      </div>
    `;
  }).join('');
}

// ── Copy Pubkey ──────────────────────────────────────────────────

async function copyPubkey() {
  const pubkey = _user.public_key;
  if (!pubkey) {
    toast('No hay clave pública disponible');
    return;
  }

  try {
    await navigator.clipboard.writeText(pubkey);
    const btn = document.getElementById('btn-copy');
    btn.textContent = 'Copiado ✓';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copiar';
      btn.classList.remove('copied');
    }, 2000);
    toast('Clave pública copiada al portapapeles');
  } catch {
    toast('No se pudo copiar. Seleccioná el texto manualmente.');
  }
}

// ── Reset Wallet ─────────────────────────────────────────────────

function onResetInput() {
  const input = document.getElementById('reset-input');
  const btn = document.getElementById('btn-reset');
  btn.disabled = input.value.trim() !== 'ELIMINAR';
}

async function resetWallet() {
  const input = document.getElementById('reset-input');
  if (input.value.trim() !== 'ELIMINAR') return;

  try {
    EduWallet.clearStoredKey(_user.legajo);
    input.value = '';
    document.getElementById('btn-reset').disabled = true;
    document.getElementById('wallet-status').innerHTML =
      '<span class="status-dot amber"></span> Sin clave privada guardada — no podés firmar SPEND';
    toast('Wallet reseteada. La clave privada fue eliminada de este navegador.');
  } catch (e) {
    toast('Error al resetear: ' + e.message);
  }
}

// ── Boot ─────────────────────────────────────────────────────────

initWalletPage();
