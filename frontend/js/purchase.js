// TODO: Implement purchase confirmation logic and request submission for buying products.

requireAuth();

const API_BASE_URL = '/api';

/**
 * Inicializar página de compra
 */
async function initPurchase() {
  const productId = sessionStorage.getItem('selected_product_id');
  
  if (!productId) {
    window.location.href = 'marketplace.html';
    return;
  }

  await loadProductDetails(productId);
  await loadBalance();
}

/**
 * Cargar detalles del producto
 */
async function loadProductDetails(productId) {
  try {
    const token = getToken();
    
    const response = await fetch(`${API_BASE_URL}/products/${productId}`, {
      headers: { 'Authorization': 'Bearer ' + token }
    });

    if (response.ok) {
      const product = await response.json();
      
      // Emojis para productos
      const emojis = ['🍕', '☕', '🍰', '🥤', '🍪', '📚', '💻', '⏰'];
      const emoji = emojis[productId % emojis.length];
      
      document.getElementById('product-emoji').textContent = emoji;
      document.getElementById('product-name').textContent = product.name;
      document.getElementById('product-desc').textContent = product.description || 'Producto del campus';
      document.getElementById('product-price').textContent = product.price_points + ' pts';
      
      // Almacenar precio
      sessionStorage.setItem('product_price', product.price_points);
    }
  } catch (error) {
    console.error('Error loading product:', error);
  }
}

/**
 * Cargar saldo actual
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
      const productPrice = parseInt(sessionStorage.getItem('product_price')) || 0;
      const remaining = balance - productPrice;
      
      document.getElementById('current-balance').textContent = balance + ' pts';
      document.getElementById('remaining-balance').textContent = remaining + ' pts';
      
      // Mostrar advertencia si saldo insuficiente
      const warning = document.getElementById('insufficient-warning');
      const button = document.getElementById('confirm-btn');
      
      if (remaining < 0) {
        warning.style.display = 'block';
        button.disabled = true;
        button.style.opacity = '0.5';
        button.style.cursor = 'not-allowed';
      } else {
        warning.style.display = 'none';
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';
      }
    }
  } catch (error) {
    console.error('Error loading balance:', error);
  }
}

/**
 * Confirmar compra
 */
async function confirmPurchase() {
  try {
    const token = getToken();
    const productId = sessionStorage.getItem('selected_product_id');
    
    const response = await fetch(`${API_BASE_URL}/purchases`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
      },
      body: JSON.stringify({ product_id: productId })
    });

    if (response.ok) {
      const data = await response.json();
      
      // Limpiar sessionStorage
      sessionStorage.removeItem('selected_product_id');
      sessionStorage.removeItem('product_price');
      
      // Mostrar mensaje de éxito
      alert('¡Compra realizada exitosamente! Tu saldo ha sido actualizado.');
      window.location.href = 'marketplace.html';
    } else {
      const error = await response.json();
      showError(error.detail || 'Error al procesar la compra');
    }
  } catch (error) {
    console.error('Error confirming purchase:', error);
    showError('Error al procesar la compra');
  }
}

/**
 * Mostrar error
 */
function showError(message) {
  const errorEl = document.getElementById('error-msg');
  errorEl.textContent = message;
  errorEl.classList.add('show');
  setTimeout(() => errorEl.classList.remove('show'), 3000);
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
window.addEventListener('DOMContentLoaded', initPurchase);