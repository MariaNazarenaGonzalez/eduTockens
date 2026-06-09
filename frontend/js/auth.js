const API_BASE_URL = '/api';

/**
 * Guardar token en localStorage
 */
function saveToken(token) {
  localStorage.setItem('token', token);
}

/**
 * Obtener token desde localStorage
 */
function getToken() {
  return localStorage.getItem('token');
}

/**
 * Obtener headers de autenticación
 */
function getAuthHeaders() {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': 'Bearer ' + token })
  };
}

/**
 * Verificar si el usuario está autenticado
 */
function isAuthenticated() {
  return !!getToken();
}

/**
 * Obtener rol del usuario
 */
function getUserRole() {
  return localStorage.getItem('role');
}

/**
 * Login del usuario
 * @param {string} identifier - Legajo o email del usuario
 * @param {string} password
 */
async function login(identifier, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error en login');
    }

    const data = await response.json();
    saveToken(data.access_token);
    localStorage.setItem('role', data.user.role);
    localStorage.setItem('user', JSON.stringify(data.user));

    return data;
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
}

/**
 * Registro del usuario
 */
async function register(legajo, name, email, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ legajo, name, email, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error en registro');
    }

    return await response.json();
  } catch (error) {
    console.error('Register error:', error);
    throw error;
  }
}

/**
 * Logout del usuario
 */
function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('user');
  window.location.href = 'login.html';
}

/**
 * Proteger rutas - redirigir si no está autenticado
 */
function requireAuth() {
  if (!isAuthenticated()) {
    window.location.href = 'login.html';
  }
}

/**
 * Verificar permisos de administrador
 */
function requireAdmin() {
  if (getUserRole() !== 'admin') {
    window.location.href = 'home.html';
  }
}