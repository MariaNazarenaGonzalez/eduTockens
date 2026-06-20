/* DEO GLORIA */

// admin.js — Panel de administración: estadísticas, emisión de puntos,
// gestión de productos y vendors, logs de compras.
//
// EARN no se firma client-side: el admin no posee (ni necesita) la clave
// privada de ACADEMIC_SYSTEM — esa vive únicamente en el backend
// (env/secret). El admin solo manda { legajo, amount, concept } y el
// backend arma y firma la transacción EARN completa.

requireAuth();
requireAdmin();

const API_BASE_URL = '/api';

function getToken() {
  return localStorage.getItem('token');
}

function getUserRole() {
  return localStorage.getItem('role');
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = 'login.html';
  }
}

function requireAdmin() {
  if (getUserRole() !== 'admin') {
    window.location.href = 'home.html';
  }
}

function authHeaders() {
  return {
    'Content-Type': 'application/json',
    Authorization: 'Bearer ' + getToken(),
  };
}

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('user');
  window.location.href = 'login.html';
}

function goTo(path) {
  window.location.href = path;
}

function showMessage(elId, message, isError) {
  const el = document.getElementById(elId);
  el.textContent = message;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), isError ? 4000 : 3000);
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = ['emit', 'products', 'vendors', 'logs'];

function switchTab(tab) {
  TABS.forEach((t) => {
    document.getElementById(`${t}-section`).style.display = t === tab ? 'block' : 'none';
    const tabBtn = document.getElementById(`tab-${t}`);
    if (t === tab) {
      tabBtn.style.color = 'var(--primary)';
      tabBtn.style.borderBottom = '2px solid var(--primary)';
    } else {
      tabBtn.style.color = 'var(--text-muted)';
      tabBtn.style.borderBottom = '2px solid transparent';
    }
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
    const response = await fetch(`${API_BASE_URL}/admin/stats`, { headers: authHeaders() });
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
// EARN
// ---------------------------------------------------------------------------

async function emitPoints() {
  const legajo = document.getElementById('emit-legajo').value.trim();
  const amountStr = document.getElementById('emit-amount').value;
  const concept = document.getElementById('emit-concept').value.trim();

  if (!legajo || !amountStr || !concept) {
    showMessage('error-msg', 'Completá todos los campos', true);
    return;
  }

  const amount = parseInt(amountStr, 10);
  if (!Number.isInteger(amount) || amount <= 0) {
    showMessage('error-msg', 'La cantidad de puntos debe ser un entero positivo', true);
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/admin/earn`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ legajo, amount, concept }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Error al emitir puntos');

    showMessage('success-msg', `Puntos emitidos. TX: ${data.tx_id}`, false);
    document.getElementById('emit-legajo').value = '';
    document.getElementById('emit-amount').value = '';
    document.getElementById('emit-concept').value = '';
    loadStats();
  } catch (error) {
    showMessage('error-msg', error.message, true);
  }
}

// ---------------------------------------------------------------------------
// Vendors
// ---------------------------------------------------------------------------

async function loadVendors() {
  const tbody = document.getElementById('vendors-tbody');
  try {
    const response = await fetch(`${API_BASE_URL}/admin/vendors`, { headers: authHeaders() });
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
    showMessage('error-msg', 'Ingresá un nombre para el vendor', true);
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/admin/vendors`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ name }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Error al crear el vendor');

    showMessage('success-msg', `Vendor "${data.name}" creado`, false);
    document.getElementById('vendor-name').value = '';
    loadVendors();
    loadStats();
  } catch (error) {
    showMessage('error-msg', error.message, true);
  }
}

// ---------------------------------------------------------------------------
// Productos
// ---------------------------------------------------------------------------

function showCreateProduct() {
  const form = document.getElementById('create-product-form');
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
  if (form.style.display === 'block') {
    loadVendors(); // asegura que el select de vendors esté actualizado
  }
}

async function loadProducts() {
  const tbody = document.getElementById('products-tbody');
  try {
    const response = await fetch(`${API_BASE_URL}/admin/products`, { headers: authHeaders() });
    if (!response.ok) throw new Error('No se pudieron cargar los productos');

    const products = await response.json();
    renderProductsTable(products);
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
      <td>${p.stock === null || p.stock === undefined ? '∞' : p.stock}</td>
      <td>${p.vendor_id ?? '—'}</td>
      <td>
        <button class="btn btn-outline btn-sm" style="margin: 0;" onclick="deleteProductAction(${p.id})">🗑️</button>
      </td>
    </tr>
  `).join('');
}

async function submitCreateProduct() {
  const name = document.getElementById('product-name').value.trim();
  const description = document.getElementById('product-description').value.trim();
  const priceStr = document.getElementById('product-price').value;
  const stockStr = document.getElementById('product-stock').value;
  const vendorId = document.getElementById('product-vendor').value;

  if (!name || !priceStr || !vendorId) {
    showMessage('error-msg', 'Completá nombre, precio y vendor', true);
    return;
  }

  const price_points = parseInt(priceStr, 10);
  if (!Number.isInteger(price_points) || price_points <= 0) {
    showMessage('error-msg', 'El precio debe ser un entero positivo', true);
    return;
  }

  const payload = {
    name,
    description: description || null,
    price_points,
    stock: stockStr ? parseInt(stockStr, 10) : null,
    vendor_id: parseInt(vendorId, 10),
  };

  try {
    const response = await fetch(`${API_BASE_URL}/admin/products`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Error al crear el producto');

    showMessage('success-msg', `Producto "${data.name}" creado`, false);
    document.getElementById('product-name').value = '';
    document.getElementById('product-description').value = '';
    document.getElementById('product-price').value = '';
    document.getElementById('product-stock').value = '';
    document.getElementById('create-product-form').style.display = 'none';
    loadProducts();
    loadStats();
  } catch (error) {
    showMessage('error-msg', error.message, true);
  }
}

async function deleteProductAction(productId) {
  if (!window.confirm('¿Eliminar este producto?')) return;

  try {
    const response = await fetch(`${API_BASE_URL}/admin/products/${productId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });

    if (!response.ok && response.status !== 204) {
      const data = await response.json();
      throw new Error(data.detail || 'Error al eliminar el producto');
    }

    showMessage('success-msg', 'Producto eliminado', false);
    loadProducts();
    loadStats();
  } catch (error) {
    showMessage('error-msg', error.message, true);
  }
}

// ---------------------------------------------------------------------------
// Logs (compras de todos los estudiantes)
// ---------------------------------------------------------------------------

async function loadLogs() {
  const tbody = document.getElementById('logs-tbody');
  try {
    const response = await fetch(`${API_BASE_URL}/admin/purchases`, { headers: authHeaders() });
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
  loadVendors(); // para poblar el <select> de productos desde el arranque
});