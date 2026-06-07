// TODO: Implement admin page JavaScript for point issuance and product management actions.

requireAdmin();

const API_BASE_URL = '/api';

/**
 * Inicializar panel admin
 */
async function initAdmin() {
  await loadStats();
  await loadProducts();
}

/**
 * Cargar estadísticas
 */
async function loadStats() {
  try {
    const token = getToken();
    
    const response = await fetch(`${API_BASE_URL}/admin/stats`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });

    if (response.ok) {
      const stats = await response.json();
      document.getElementById('stat-students').textContent = stats.students || 0;
      document.getElementById('stat-transactions').textContent = stats.transactions || 0;
      document.getElementById('stat-blocks').textContent = stats.blocks || 0;
      document.getElementById('stat-supply').textContent = stats.total_supply || 0;
    }
  } catch (error) {
    console.error('Error loading stats:', error);
  }
}

/**
 * Cambiar tab
 */
function switchTab(tab) {
  const emitSection = document.getElementById('emit-section');
  const productsSection = document.getElementById('products-section');
  const emitTab = document.getElementById('tab-emit');
  const productsTab = document.getElementById('tab-products');
  
  if (tab === 'emit') {
    emitSection.style.display = 'block';
    productsSection.style.display = 'none';
    emitTab.style.color = 'var(--primary)';
    emitTab.style.borderBottomColor = 'var(--primary)';
    productsTab.style.color = 'var(--text-muted)';
    productsTab.style.borderBottomColor = 'transparent';
  } else {
    emitSection.style.display = 'none';
    productsSection.style.display = 'block';
    emitTab.style.color = 'var(--text-muted)';
    emitTab.style.borderBottomColor = 'transparent';
    productsTab.style.color = 'var(--primary)';
    productsTab.style.borderBottomColor = 'var(--primary)';
  }
}

/**
 * Emitir puntos a estudiante
 */
async function emitPoints() {
  const legajo = document.getElementById('emit-legajo').value;
  const amount = parseInt(document.getElementById('emit-amount').value);
  const concept = document.getElementById('emit-concept').value;
  const errorEl = document.getElementById('error-msg');

  if (!legajo || !amount || !concept) {
    errorEl.textContent = 'Por favor completa todos los campos';
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), 3000);
    return;
  }

  try {
    const token = getToken();
    const response = await fetch(`${API_BASE_URL}/admin/earn`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
      },
      body: JSON.stringify({ legajo, amount, concept })
    });

    if (response.ok) {
      alert('Puntos emitidos correctamente');
      document.getElementById('emit-legajo').value = '';
      document.getElementById('emit-amount').value = '';
      document.getElementById('emit-concept').value = '';
      await loadStats();
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Error al emitir puntos');
    }
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.classList.add('show');
    setTimeout(() => errorEl.classList.remove('show'), 3000);
  }
}

/**
 * Cargar productos
 */
async function loadProducts() {
  try {
    const token = getToken();
    
    const response = await fetch(`${API_BASE_URL}/admin/products`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });

    if (response.ok) {
      const products = await response.json();
      renderProductsTable(products);
    }
  } catch (error) {
    console.error('Error loading products:', error);
  }
}

/**
 * Renderizar tabla de productos
 */
function renderProductsTable(products) {
  const tbody = document.getElementById('products-tbody');
  
  if (!products || products.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 16px; color: var(--text-muted);">Sin productos</td></tr>';
    return;
  }

  tbody.innerHTML = products.map(product => `
    <tr>
      <td>${product.name}</td>
      <td>${product.price_points} pts</td>
      <td>${product.stock || '∞'}</td>
      <td>
        <button style="color: var(--primary); background: none; border: none; cursor: pointer; font-size: 11px; font-weight: 500;" onclick="editProduct(${product.id})">Editar</button>
        <span style="margin: 0 4px; color: var(--border);">·</span>
        <button style="color: var(--error); background: none; border: none; cursor: pointer; font-size: 11px; font-weight: 500;" onclick="deleteProduct(${product.id})">Eliminar</button>
      </td>
    </tr>
  `).join('');
}

/**
 * Editar producto
 */
function editProduct(productId) {
  alert('Editar producto: ' + productId);
  // TODO: Implementar modal de edición
}

/**
 * Eliminar producto
 */
async function deleteProduct(productId) {
  if (!confirm('¿Estás seguro de que quieres eliminar este producto?')) {
    return;
  }

  try {
    const token = getToken();
    const response = await fetch(`${API_BASE_URL}/admin/products/${productId}`, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + token }
    });

    if (response.ok) {
      alert('Producto eliminado');
      await loadProducts();
    }
  } catch (error) {
    console.error('Error deleting product:', error);
  }
}

/**
 * Mostrar formulario de creación de producto
 */
function showCreateProduct() {
  alert('Crear nuevo producto');
  // TODO: Implementar modal de creación
}

/**
 * Mostrar formulario de emisión
 */
function showEarnForm() {
  switchTab('emit');
}

/**
 * Mostrar productos
 */
function showProducts() {
  switchTab('products');
}

/**
 * Mostrar logs
 */
function showLogs() {
  alert('Ver logs del sistema');
  // TODO: Implementar página de logs
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

// Funciones de autenticación
function getToken() {
  return localStorage.getItem('token');
}

function requireAdmin() {
  if (localStorage.getItem('role') !== 'admin') {
    window.location.href = 'home.html';
  }
}

function goTo(path) {
  window.location.href = path;
}

// Inicializar al cargar
window.addEventListener('DOMContentLoaded', initAdmin);