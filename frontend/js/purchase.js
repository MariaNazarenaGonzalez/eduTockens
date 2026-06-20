/* DEO GLORIA */

// purchase.js — Confirmación de compra: arma y firma la transacción SPEND
// client-side (la clave privada del estudiante nunca sale del navegador
// en texto plano — vive cifrada en localStorage y se descifra en memoria
// solo para firmar).
//
// El backend (POST /purchases) NO firma nada por el estudiante — solo
// reenvía esta transacción ya firmada al NCT. El signing dict que se
// construye aquí debe coincidir EXACTAMENTE con lo que el backend
// reconstruye a partir del producto en DB (mismo amount=price_points,
// mismo receiver_pubkey=vendor_pubkey, mismo concept=nombre del producto).
//
// Requiere que se hayan cargado antes: crypto-auth.js (firma Ed25519),
// wallet-crypto.js (descifrado de la clave privada), tx-signer.js
// (cálculo de tx_id y firma de transacciones).

requireAuth();

const API_BASE_URL = '/api';

function getToken() {
  return localStorage.getItem('token');
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = 'login.html';
  }
}

function getCurrentUser() {
  return JSON.parse(localStorage.getItem('user') || '{}');
}

let _selectedProduct = null;
let _currentAccount = null;

/**
 * Inicializa la página: carga el producto seleccionado (sessionStorage,
 * seteado por marketplace.js) y el balance/nonce actual del estudiante.
 */
async function initPurchasePage() {
  const errorEl = document.getElementById('error-msg');
  const productId = sessionStorage.getItem('selected_product_id');

  if (!productId) {
    errorEl.textContent = 'No se seleccionó ningún producto';
    errorEl.classList.add('show');
    return;
  }

  try {
    const user = getCurrentUser();
    const token = getToken();

    const [productRes, balanceRes] = await Promise.all([
      fetch(`${API_BASE_URL}/products/${productId}`, {
        headers: { Authorization: 'Bearer ' + token },
      }),
      fetch(`${API_BASE_URL}/students/${user.legajo}/balance`, {
        headers: { Authorization: 'Bearer ' + token },
      }),
    ]);

    if (!productRes.ok) throw new Error('No se pudo cargar el producto');
    if (!balanceRes.ok) throw new Error('No se pudo cargar el saldo');

    _selectedProduct = await productRes.json();
    _currentAccount = await balanceRes.json(); // { legajo, public_key, balance, nonce }

    renderPurchaseSummary();
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.classList.add('show');
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

/**
 * Pide la contraseña, descifra la clave privada, arma y firma el SPEND,
 * y confirma la compra contra el backend.
 */
async function confirmPurchase() {
  const errorEl = document.getElementById('error-msg');
  const product = _selectedProduct;
  const account = _currentAccount;

  if (!product || !account) {
    errorEl.textContent = 'Datos de la compra no disponibles, recargá la página';
    errorEl.classList.add('show');
    return;
  }

  if (!product.vendor_pubkey) {
    errorEl.textContent = 'Este producto no tiene un vendor asignado — no se puede comprar';
    errorEl.classList.add('show');
    return;
  }

  const user = getCurrentUser();

  // La contraseña se pide en el momento de firmar — nunca se guarda en
  // memoria ni en localStorage (solo el material cifrado de la clave
  // privada persiste, no la contraseña).
  const password = window.prompt('Ingresá tu contraseña para firmar la compra:');
  if (!password) {
    return; // usuario canceló
  }

  let privateKeyHex;
  try {
    privateKeyHex = await decryptStoredPrivateKey(user.legajo, password);
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), 3000);
    return;
  }

  if (account.public_key !== user.public_key) {
    // Salvaguarda: si la pubkey de la sesión no coincide con la cuenta,
    // firmar produciría una transacción que el NCT rechazaría de todos
    // modos (sender_pubkey no correspondería con la clave que firmó).
    errorEl.textContent = 'La cuenta autenticada no coincide con los datos de saldo obtenidos';
    errorEl.classList.add('show');
    return;
  }

  const timestamp = Date.now() / 1000; // segundos, float — va en el wire
  // payload, no participa de la firma
  const nonce = account.nonce;
  const amount = Math.trunc(product.price_points); // entero — Transaction.amount es int

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
    const txId = await computeTxId(signingBody);
    signature = await signChallengeWithPrivateKey(privateKeyHex, txId);
    // Nota: signChallengeWithPrivateKey firma los bytes UTF-8 del string
    // recibido — es la misma operación de firma que usa tx-signer.js,
    // reutilizada acá para no duplicar la llamada a @noble/curves.
  } catch (error) {
    errorEl.textContent = 'No se pudo firmar la transacción';
    errorEl.classList.add('show');
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/purchases`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + getToken(),
      },
      body: JSON.stringify({
        product_id: product.id,
        nonce,
        timestamp,
        signature,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      window.alert('¡Compra confirmada! Tx ID: ' + data.nct_transaction_id);
      window.location.href = 'home.html';
    } else {
      throw new Error(data.detail || 'Error al confirmar la compra');
    }
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), 4000);
  }
}

window.addEventListener('DOMContentLoaded', initPurchasePage);