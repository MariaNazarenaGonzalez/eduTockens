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
  const logsSection = document.getElementById('logs-section');
  const emitTab = document.getElementById('tab-emit');
  const productsTab = document.getElementById('tab-products');
  const logsTab = document.getElementById('tab-logs');

  if (tab === 'emit') {
    emitSection.style.display = 'block';
    productsSection.style.display = 'none';
    if (logsSection) logsSection.style.display = 'none';

    emitTab.style.color = 'var(--primary)';
    emitTab.style.borderBottomColor = 'var(--primary)';
    productsTab.style.color = 'var(--text-muted)';
    productsTab.style.borderBottomColor = 'transparent';
    if (logsTab) {
      logsTab.style.color = 'var(--text-muted)';
      logsTab.style.borderBottomColor = 'transparent';
    }
  } else if (tab === 'products') {
    emitSection.style.display = 'none';
    productsSection.style.display = 'block';
    if (logsSection) logsSection.style.display = 'none';

    emitTab.style.color = 'var(--text-muted)';
    emitTab.style.borderBottomColor = 'transparent';
    productsTab.style.color = 'var(--primary)';
    productsTab.style.borderBottomColor = 'var(--primary)';
    if (logsTab) {
      logsTab.style.color = 'var(--text-muted)';
      logsTab.style.borderBottomColor = 'transparent';
    }
  } else if (tab === 'logs') {
    emitSection.style.display = 'none';
    productsSection.style.display = 'none';
    if (logsSection) logsSection.style.display = 'block';

    emitTab.style.color = 'var(--text-muted)';
    emitTab.style.borderBottomColor = 'transparent';
    productsTab.style.color = 'var(--text-muted)';
    productsTab.style.borderBottomColor = 'transparent';
    if (logsTab) {
      logsTab.style.color = 'var(--primary)';
      logsTab.style.borderBottomColor = 'var(--primary)';
    }
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
  const overlay = document.createElement('div');
  overlay.style.position = 'fixed';
  overlay.style.top = '0';
  overlay.style.left = '0';
  overlay.style.width = '100%';
  overlay.style.height = '100%';
  overlay.style.background = 'rgba(0,0,0,0.5)';
  overlay.style.zIndex = '1000';
  overlay.style.display = 'flex';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';

  const card = document.createElement('div');
  card.className = 'card';
  card.style.padding = '20px';
  card.style.width = '90%';
  card.style.maxWidth = '400px';
  card.style.maxHeight = '80vh';
  card.style.overflowY = 'auto';

  card.innerHTML = `
    <h3 style="margin-top:0; margin-bottom: 16px;">Crear Producto</h3>
    <form id="create-product-form" enctype="multipart/form-data">
      <div class="input-group">
        <label class="input-label" for="prod-name">Nombre</label>
        <input class="input" type="text" id="prod-name" name="name" required>
      </div>
      <div class="input-group">
        <label class="input-label" for="prod-desc">Descripción</label>
        <textarea class="input" id="prod-desc" name="description" rows="3" style="resize: vertical;"></textarea>
      </div>
      <div class="input-group">
        <label class="input-label" for="prod-price">Puntos</label>
        <input class="input" type="number" id="prod-price" name="price_points" min="1" required>
      </div>
      <div class="input-group">
        <label class="input-label" for="prod-stock">Stock (vacío = ilimitado)</label>
        <input class="input" type="number" id="prod-stock" name="stock">
      </div>
      <div class="input-group">
        <label class="input-label" for="prod-image">Imagen</label>
        <input class="input" type="file" id="prod-image" name="image" accept="image/*">
      </div>
      <p id="prod-error" style="color: var(--error); margin-bottom: 16px; display: none; font-size: 14px;"></p>
      <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
        <button type="button" class="btn btn-outline" id="btn-cancel-prod">Cancelar</button>
        <button type="submit" class="btn btn-primary">Guardar</button>
      </div>
    </form>
  `;

  overlay.appendChild(card);
  document.body.appendChild(overlay);

  document.getElementById('btn-cancel-prod').addEventListener('click', () => {
    document.body.removeChild(overlay);
  });

  document.getElementById('create-product-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);

    const errorEl = document.getElementById('prod-error');
    errorEl.style.display = 'none';

    try {
      const token = getToken();
      const response = await fetch(`${API_BASE_URL}/admin/products`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + token
        },
        body: formData
      });

      if (response.ok) {
        document.body.removeChild(overlay);
        alert('Producto creado');
        await loadProducts();
      } else {
        const error = await response.json();
        errorEl.textContent = error.detail || 'Error al crear producto';
        errorEl.style.display = 'block';
      }
    } catch (err) {
      errorEl.textContent = err.message || 'Error de red';
      errorEl.style.display = 'block';
    }
  });
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
async function showLogs() {
  switchTab('logs');
  const tbody = document.getElementById('logs-tbody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 16px; color: var(--text-muted);">Cargando...</td></tr>';

  try {
    const token = getToken();
    const response = await fetch(`${API_BASE_URL}/admin/logs`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });

    if (response.ok) {
      const logs = await response.json();
      if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 16px; color: var(--text-muted);">Sin registros</td></tr>';
        return;
      }

      tbody.innerHTML = logs.map(log => `
        <tr>
          <td>${log.id}</td>
          <td>${log.user_id}</td>
          <td>${log.product_id}</td>
          <td>${log.points_spent}</td>
          <td>${log.nct_transaction_id || '-'}</td>
          <td>${new Date(log.created_at).toLocaleString()}</td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 16px; color: var(--error);">Error al cargar logs</td></tr>';
    }
  } catch (error) {
    console.error('Error loading logs:', error);
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 16px; color: var(--error);">Error de conexión</td></tr>';
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