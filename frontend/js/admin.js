/* DEO GLORIA */

// admin.js — Panel de administración: estadísticas, emisión de puntos,
// gestión de productos y vendors, logs de compras.
//
// EARN con firma local: la wallet del admin firma en el browser.
//    GET /admin/resolve?legajo= → pubkey
//    GET /admin/account → nonce
//    EduWallet.signTransaction(...) → firma
//    POST /api/transactions/relay → NCT
//
// Dependencias (cargadas antes en el HTML):
//   common.js      — getToken, requireAuth, requireAdmin, getAuthHeaders, showError, showSuccess
//   wallet-crypto.js — decryptStoredPrivateKey, hasStoredWallet
//   wallet.js      — EduWallet.signTransaction, .loadPrivateKey, .getActivePublicKey

requireAuth();
requireAdmin();

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = ['emit', 'products', 'vendors', 'logs'];

function switchTab(tab) {
  TABS.forEach((t) => {
    document.getElementById(`${t}-section`).style.display = t === tab ? 'block' : 'none';
    const tabBtn = document.getElementById(`tab-${t}`);
    tabBtn.classList.toggle('active', t === tab);
  });

  if (tab === 'products') loadProducts();
  if (tab === 'vendors') loadVendors();
  if (tab === 'logs') loadLogs();
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

async function loadStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/admin/stats`, { headers: getAuthHeaders() });
    if (!response.ok) throw new Error('No se pudieron cargar las estadísticas');

    const stats = await response.json();
    document.getElementById('stat-students').textContent = stats.total_students;
    document.getElementById('stat-vendors').textContent = stats.total_vendors;
    document.getElementById('stat-products').textContent = stats.total_products;
    document.getElementById('stat-supply').textContent = stats.total_points_spent;
  } catch (error) {
    console.error('Error loading stats:', error);
  }
}

// ---------------------------------------------------------------------------
// EARN — la wallet del admin firma en el browser
// ---------------------------------------------------------------------------

/** Variables efímeras para el flujo de firma local (se limpian al cerrar). */
let _pendingEarn = null;

/**
 * Abre el modal de contraseña.  Guarda los datos del formulario para usarlos
 * al confirmar.
 */
async function emitPointsSigned() {
  const legajo = document.getElementById('emit-legajo').value.trim();
  const amountStr = document.getElementById('emit-amount').value;
  const concept = document.getElementById('emit-concept').value.trim();

  if (!legajo || !amountStr || !concept) {
    showError('error-msg', 'Completá todos los campos');
    return;
  }

  const amount = parseInt(amountStr, 10);
  if (!Number.isInteger(amount) || amount <= 0) {
    showError('error-msg', 'La cantidad de puntos debe ser un entero positivo');
    return;
  }

  const user = getCurrentUser();

  // ¿Tiene wallet el admin?
  if (!EduWallet.hasStoredKey(user.legajo)) {
    showError('error-msg',
      'No tenés una wallet configurada en este navegador. ' +
      'Generá un par de claves primero (usando la consola o una página de setup). ' +
      'Tu clave pública debe ser la AUTHORITY_PUBKEY del NCT.'
    );
    return;
  }

  _pendingEarn = { legajo, amount, concept };
  document.getElementById('modal-password').value = '';
  document.getElementById('password-modal').style.display = 'flex';
  document.getElementById('modal-password').focus();
}

function closePasswordModal() {
  document.getElementById('password-modal').style.display = 'none';
  _pendingEarn = null;
}

function showLoading(text) {
  document.getElementById('loading-text').textContent = text;
  document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
  document.getElementById('loading-overlay').style.display = 'none';
}

async function confirmEarnWithPassword() {
  const password = document.getElementById('modal-password').value;
  if (!password) {
    showError('error-msg', 'Ingresá tu contraseña');
    return;
  }

  if (!_pendingEarn) {
    closePasswordModal();
    return;
  }

  const { legajo, amount, concept } = _pendingEarn;
  const user = getCurrentUser();
  const adminPubkey = EduWallet.getActivePublicKey() || user.public_key;

  if (!adminPubkey) {
    closePasswordModal();
    showError('error-msg', 'No se encontró tu clave pública. Iniciá sesión de nuevo.');
    return;
  }

  closePasswordModal();
  showLoading('Resolviendo legajo...');

  try {
    // 1. Resolver legajo → pubkey del estudiante
    const resolveRes = await fetch(`${API_BASE_URL}/admin/resolve?legajo=${legajo}`, {
      headers: getAuthHeaders(),
    });
    if (!resolveRes.ok) {
      const err = await resolveRes.json();
      throw new Error(err.detail || 'Legajo no encontrado');
    }
    const { public_key: studentPubkey, student_name } = await resolveRes.json();

    // 2. Nonce del admin desde el NCT
    showLoading('Consultando nonce...');
    const accountRes = await fetch(`${API_BASE_URL}/admin/account`, {
      headers: getAuthHeaders(),
    });
    if (!accountRes.ok) {
      throw new Error('No se pudo consultar la cuenta de autoridad en el NCT');
    }
    const account = await accountRes.json();
    const nonce = account.pending_nonce;

    // 3. Descifrar clave privada del admin
    showLoading('Descifrando clave privada...');
    const privateKeyHex = await EduWallet.loadPrivateKey(user.legajo, password);

    // 4. Firmar EARN
    showLoading('Firmando transacción EARN...');
    const { signature } = await EduWallet.signTransaction(
      {
        sender_pubkey: adminPubkey,
        receiver_pubkey: studentPubkey,
        amount,
        tx_type: 'EARN',
        concept,
        nonce,
      },
      privateKeyHex
    );

    // 5. Enviar al relay
    showLoading('Enviando al NCT...');
    const relayRes = await fetch(`${API_BASE_URL}/transactions/relay`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        sender_pubkey: adminPubkey,
        receiver_pubkey: studentPubkey,
        amount,
        tx_type: 'EARN',
        concept,
        nonce,
        timestamp: Date.now() / 1000,
        signature,
      }),
    });

    const relayData = await relayRes.json();

    if (!relayRes.ok) {
      throw new Error(relayData.detail || 'El NCT rechazó la transacción');
    }

    hideLoading();
    showSuccess('success-msg',
      `✅ Emitidos ${amount} pts a ${student_name} (legajo ${legajo}). TX: ${relayData.tx_id}`
    );
    document.getElementById('emit-legajo').value = '';
    document.getElementById('emit-amount').value = '';
    document.getElementById('emit-concept').value = '';
    loadStats();
  } catch (error) {
    hideLoading();
    showError('error-msg', error.message);
  }
}

// ---------------------------------------------------------------------------
// Vendors
// ---------------------------------------------------------------------------

async function loadVendors() {
  const tbody = document.getElementById('vendors-tbody');
  try {
    const response = await fetch(`${API_BASE_URL}/admin/vendors`, { headers: getAuthHeaders() });
    if (!response.ok) throw new Error('No se pudieron cargar los vendors');

    const vendors = await response.json();
    renderVendors(vendors);
    populateVendorSelect(vendors);
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="2" style="text-align:center; padding:16px; color:var(--error);">${error.message}</td></tr>`;
  }
}

function renderVendors(vendors) {
  const tbody = document.getElementById('vendors-tbody');
  if (!vendors || vendors.length === 0) {
    tbody.innerHTML = '<tr><td colspan="2" style="text-align:center; padding:16px; color:var(--text-muted);">Sin vendors</td></tr>';
    return;
  }

  tbody.innerHTML = vendors.map((v) => `
    <tr>
      <td>${v.name}</td>
      <td class="mono" style="font-size: 10px; word-break: break-all;">${v.public_key}</td>
    </tr>
  `).join('');
}

function populateVendorSelect(vendors) {
  const select = document.getElementById('product-vendor');
  if (!select) return;

  const currentValue = select.value;
  select.innerHTML = '<option value="">Seleccionar vendor...</option>' +
    vendors.map((v) => `<option value="${v.id}">${v.name}</option>`).join('');
  select.value = currentValue;
}

async function submitCreateVendor() {
  const name = document.getElementById('vendor-name').value.trim();
  if (!name) {
    showError('error-msg', 'Ingresá un nombre para el vendor');
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/admin/vendors`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ name }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Error al crear el vendor');

    showSuccess('success-msg', `Vendor "${data.name}" creado`);
    document.getElementById('vendor-name').value = '';
    loadVendors();
    loadStats();
  } catch (error) {
    showError('error-msg', error.message);
  }
}

// ---------------------------------------------------------------------------
// Products
// ---------------------------------------------------------------------------

async function loadProducts() {
  const tbody = document.getElementById('products-tbody');
  try {
    const response = await fetch(`${API_BASE_URL}/admin/products`, { headers: getAuthHeaders() });
    if (!response.ok) throw new Error('No se pudieron cargar los productos');

    const products = await response.json();
    renderProductsTable(products);
    populateVendorSelectFromProducts(products);
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:16px; color:var(--error);">${error.message}</td></tr>`;
  }
}

function renderProductsTable(products) {
  const tbody = document.getElementById('products-tbody');
  if (!products || products.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:16px; color:var(--text-muted);">Sin productos</td></tr>';
    return;
  }

  tbody.innerHTML = products.map((p) => `
    <tr>
      <td>${p.name}</td>
      <td>${p.price_points} pts</td>
      <td>${p.stock ?? '∞'}</td>
      <td style="font-size: 10px;">${p.vendor_pubkey ? p.vendor_pubkey.slice(0, 8) + '...' : '—'}</td>
      <td>
        <button class="btn btn-ghost" style="font-size: 11px; padding: 4px 8px; margin: 0; color: var(--error);" onclick="deleteProductAction(${p.id})">Eliminar</button>
      </td>
    </tr>
  `).join('');
}

function populateVendorSelectFromProducts(products) {
  // Ya se llena en loadVendors
}

function showCreateProduct() {
  document.getElementById('create-product-form').style.display = 'block';
}

async function submitCreateProduct() {
  const name = document.getElementById('product-name').value.trim();
  const description = document.getElementById('product-description').value.trim();
  const priceStr = document.getElementById('product-price').value;
  const stockStr = document.getElementById('product-stock').value;
  const vendorId = document.getElementById('product-vendor').value;

  if (!name || !priceStr || !vendorId) {
    showError('error-msg', 'Completá nombre, precio y vendor');
    return;
  }

  const pricePoints = parseInt(priceStr, 10);
  if (!Number.isInteger(pricePoints) || pricePoints <= 0) {
    showError('error-msg', 'El precio debe ser un entero positivo');
    return;
  }

  const payload = {
    name,
    description: description || null,
    price_points: pricePoints,
    stock: stockStr ? parseInt(stockStr, 10) : null,
    vendor_id: parseInt(vendorId, 10),
  };

  try {
    const response = await fetch(`${API_BASE_URL}/admin/products`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Error al crear el producto');

    showSuccess('success-msg', `Producto "${data.name}" creado`);
    document.getElementById('product-name').value = '';
    document.getElementById('product-description').value = '';
    document.getElementById('product-price').value = '';
    document.getElementById('product-stock').value = '';
    document.getElementById('create-product-form').style.display = 'none';
    loadProducts();
    loadStats();
  } catch (error) {
    showError('error-msg', error.message);
  }
}

async function deleteProductAction(productId) {
  if (!window.confirm('¿Eliminar este producto?')) return;

  try {
    const response = await fetch(`${API_BASE_URL}/admin/products/${productId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });

    if (!response.ok && response.status !== 204) {
      const data = await response.json();
      throw new Error(data.detail || 'Error al eliminar el producto');
    }

    showSuccess('success-msg', 'Producto eliminado');
    loadProducts();
    loadStats();
  } catch (error) {
    showError('error-msg', error.message);
  }
}

// ---------------------------------------------------------------------------
// Logs (compras de todos los estudiantes)
// ---------------------------------------------------------------------------

async function loadLogs() {
  const tbody = document.getElementById('logs-tbody');
  try {
    const response = await fetch(`${API_BASE_URL}/admin/purchases`, { headers: getAuthHeaders() });
    if (!response.ok) throw new Error('No se pudieron cargar los logs');

    const logs = await response.json();
    renderLogsTable(logs);
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:16px; color:var(--error);">${error.message}</td></tr>`;
  }
}

function renderLogsTable(logs) {
  const tbody = document.getElementById('logs-tbody');
  if (!logs || logs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:16px; color:var(--text-muted);">Sin compras registradas</td></tr>';
    return;
  }

  tbody.innerHTML = logs.map((log) => `
    <tr>
      <td>${log.id}</td>
      <td>${log.product_name}</td>
      <td>${log.points_spent} pts</td>
      <td class="mono" style="font-size: 10px;">${log.nct_transaction_id || '—'}</td>
      <td>${new Date(log.purchased_at).toLocaleString('es-AR')}</td>
    </tr>
  `).join('');
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

window.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadVendors();
});
