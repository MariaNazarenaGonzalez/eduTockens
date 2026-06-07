// TODO: Implement product marketplace logic and navigation to purchase confirmation.

requireAuth();

const API_BASE_URL = '/api';

/**
 * Inicializar marketplace
 */
async function initMarketplace() {
  await loadBalance();
  await loadProducts();
}

/**
 * Cargar saldo
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
      document.getElementById('marketplace-balance').textContent = data.balance || 0;
    }
  } catch (error) {
    console.error('Error loading balance:', error);
  }
}

/**
 * Cargar productos disponibles
 */
async function loadProducts() {
  try {
    const token = getToken();
    
    const response = await fetch(`${API_BASE_URL}/products`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });

    if (response.ok) {
      const products = await response.json();
      renderProducts(products);
    }
  } catch (error) {
    console.error('Error loading products:', error);
  }
}

/**
 * Renderizar productos en grid
 */
function renderProducts(products) {
  const grid = document.getElementById('products-grid');
  
  if (!products || products.length === 0) {
    grid.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px; grid-column: 1/-1;">Sin productos disponibles</div>';
    return;
  }

  // Emojis para productos
  const emojis = ['🍕', '☕', '🍰', '🥤', '🍪', '📚', '💻', '⏰'];
  
  grid.innerHTML = products.map((product, idx) => `
    <div class="product-card" onclick="selectProduct(${product.id})">
      <div class="product-img" style="background: linear-gradient(135deg, #EEF2FF, #F5F3FF);">
        ${emojis[idx % emojis.length]}
      </div>
      <div class="product-name" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
        ${product.name}
      </div>
      <div class="product-desc" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
        ${product.description || 'Producto del campus'}
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span class="product-cost">${product.price_points} pts</span>
        <button class="btn btn-primary btn-sm" style="margin: 0;" onclick="event.stopPropagation(); goToPurchase(${product.id})">
          Canjear
        </button>
      </div>
    </div>
  `).join('');
}

/**
 * Seleccionar producto
 */
function selectProduct(productId) {
  // Almacenar producto seleccionado
  sessionStorage.setItem('selected_product_id', productId);
  goToPurchase(productId);
}

/**
 * Navegar a página de compra
 */
function goToPurchase(productId) {
  sessionStorage.setItem('selected_product_id', productId);
  window.location.href = 'purchase.html';
}

/**
 * Navegar a otra página
 */
function goTo(path) {
  window.location.href = path;
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

function requireAuth() {
  if (!getToken()) {
    window.location.href = 'login.html';
  }
}

// Inicializar al cargar
window.addEventListener('DOMContentLoaded', initMarketplace);
