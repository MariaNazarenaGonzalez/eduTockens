/* DEO GLORIA */

// purchase.js — Confirmación de compra: arma y firma la transacción SPEND
// client-side (la clave privada del estudiante nunca sale del navegador
// en texto plano — vive cifrada en localStorage y se descifra en memoria
// solo para firmar).
//
// El backend (POST /purchases) NO firma nada por el estudiante — solo
// reenvía esta transacción ya firmada al NCT.
//
// Dependencias (cargadas antes en el HTML):
//   common.js      — getToken, getCurrentUser, requireAuth, getAuthHeaders
//   wallet-crypto.js — decryptStoredPrivateKey
//   wallet.js      — EduWallet.signTransaction()

requireAuth();

let _selectedProduct = null;
let _currentAccount = null;

/**
 * Inicializa la página: carga el producto seleccionado (sessionStorage,
 * seteado por marketplace.js) y el balance/nonce actual del estudiante.
 */
async function initPurchasePage() {
  const productId = sessionStorage.getItem('selected_product_id');

  if (!productId) {
    showError('error-msg', 'No se seleccionó ningún producto');
    return;
  }

  try {
    const user = getCurrentUser();

    const [productRes, balanceRes] = await Promise.all([
      fetch(`${API_BASE_URL}/products/${productId}`, { headers: getAuthHeaders() }),
      fetch(`${API_BASE_URL}/students/${user.legajo}/balance`, { headers: getAuthHeaders() }),
    ]);

    if (!productRes.ok) throw new Error('No se pudo cargar el producto');
    if (!balanceRes.ok) throw new Error('No se pudo cargar el saldo');

    _selectedProduct = await productRes.json();
    _currentAccount = await balanceRes.json();

    renderPurchaseSummary();
  } catch (error) {
    showError('error-msg', error.message);
  }
}

function renderPurchaseSummary() {
  const product = _selectedProduct;
  const account = _currentAccount;

  document.getElementById('product-name').textContent = product.name;
  document.getElementById('product-desc').textContent = product.description || 'Producto del campus';
  document.getElementById('product-price').textContent = `${product.price_points} pts`;
  document.getElementById('current-balance').textContent = `${account.balance} pts`;

  const remaining = account.balance - product.price_points;
  document.getElementById('remaining-balance').textContent = `${remaining} pts`;

  const warningEl = document.getElementById('insufficient-warning');
  const confirmBtn = document.getElementById('confirm-btn');
  if (remaining < 0) {
    warningEl.style.display = 'block';
    confirmBtn.disabled = true;
  } else {
    warningEl.style.display = 'none';
    confirmBtn.disabled = false;
  }
}

// ── Password Modal ────────────────────────────────────────────────

function showPasswordModal() {
  document.getElementById('modal-password').value = '';
  document.getElementById('password-modal').classList.add('show');
  document.getElementById('modal-password').focus();
}

function closePasswordModal() {
  document.getElementById('password-modal').classList.remove('show');
}

function showLoading(text) {
  document.getElementById('loading-text').textContent = text;
  document.getElementById('loading-overlay').classList.add('show');
}

function hideLoading() {
  document.getElementById('loading-overlay').classList.remove('show');
}

/**
 * Abre el modal de contraseña para confirmar la compra.
 * El flujo real de firma ocurre en confirmWithPassword().
 */
function confirmPurchase() {
  const product = _selectedProduct;
  const account = _currentAccount;

  if (!product || !account) {
    showError('error-msg', 'Datos de la compra no disponibles, recargá la página');
    return;
  }

  if (!product.vendor_pubkey) {
    showError('error-msg', 'Este producto no tiene un vendor asignado — no se puede comprar');
    return;
  }

  showPasswordModal();
}

/**
 * Callback del modal: descifra la clave, firma el SPEND y confirma la compra.
 */
async function confirmWithPassword() {
  const password = document.getElementById('modal-password').value;
  if (!password) {
    showError('error-msg', 'Ingresá tu contraseña');
    return;
  }

  const product = _selectedProduct;
  const account = _currentAccount;
  const user = getCurrentUser();

  // Validaciones pre-firma
  if (account.public_key !== user.public_key) {
    closePasswordModal();
    showError('error-msg', 'La cuenta autenticada no coincide con los datos de saldo obtenidos');
    return;
  }

  closePasswordModal();
  showLoading('Descifrando clave privada...');

  // 1. Descifrar clave
  let privateKeyHex;
  try {
    privateKeyHex = await decryptStoredPrivateKey(user.legajo, password);
  } catch (error) {
    hideLoading();
    showError('error-msg', error.message);
    return;
  }

  // 2. Armar signing dict y firmar
  showLoading('Firmando transacción SPEND...');
  const timestamp = Date.now() / 1000;
  // Regla de oro del NCT: siempre pending_nonce, nunca nonce.
  // pending_nonce considera las txs ya enviadas al pool; nonce es
  // el confirmado on-chain y puede causar "nonce already consumed".
  const nonce = account.pending_nonce;
  const amount = Math.trunc(product.price_points);

  const signingBody = {
    sender_pubkey: user.public_key,
    receiver_pubkey: product.vendor_pubkey,
    amount,
    tx_type: 'SPEND',
    concept: product.name,
    nonce,
  };

  let signature;
  try {
    const { signature: sig } = await EduWallet.signTransaction(signingBody, privateKeyHex);
    signature = sig;
  } catch (error) {
    hideLoading();
    showError('error-msg', 'No se pudo firmar la transacción. Verificá tu clave privada.');
    return;
  }

  // 3. Enviar al backend → NCT
  showLoading('Enviando transacción al NCT...');
  try {
    const response = await fetch(`${API_BASE_URL}/purchases`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        product_id: product.id,
        nonce,
        timestamp,
        signature,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      hideLoading();
      window.alert('✅ ¡Compra confirmada!\n\nTx ID: ' + data.nct_transaction_id);
      window.location.href = 'home.html';
    } else {
      hideLoading();
      const detail = data.detail || 'Error al confirmar la compra';
      if (detail.includes('NCT')) {
        throw new Error('El NCT rechazó la transacción. ¿Está corriendo el NCT? Detalle: ' + detail);
      }
      throw new Error(detail);
    }
  } catch (error) {
    hideLoading();
    showError('error-msg', error.message, 8000);
  }
}

window.addEventListener('DOMContentLoaded', initPurchasePage);
