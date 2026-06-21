/* DEO GLORIA */

/**
 * common.js — Utilidades compartidas del frontend de eduTockens.
 *
 * Centraliza funciones duplicadas que antes estaban copiadas en cada
 * page script (home.js, marketplace.js, purchase.js, admin.js, etc.).
 *
 * Carga: <script src="../js/common.js"></script> (clásico, NO módulo).
 * Debe cargarse ANTES de los scripts específicos de cada página.
 *
 * Funciones expuestas como globales:
 *   API_BASE_URL             — "/api"
 *   getToken()               — JWT desde localStorage
 *   getAuthHeaders()          — { Content-Type, Authorization }
 *   isAuthenticated()         — true si hay token
 *   getUserRole()             — "student" | "admin" | null
 *   getCurrentUser()          — objeto user desde localStorage
 *   requireAuth()             — redirige a login.html si no hay token
 *   requireAdmin()            — redirige a home.html si no es admin
 *   logout()                  — borra sesión y redirige a login.html
 *   goTo(path)                — navegación SPA-style
 *   showError(elId, message)  — muestra mensaje de error temporal
 *   showSuccess(elId, message)— muestra mensaje de éxito temporal
 */

const API_BASE_URL = '/api';

// ---------------------------------------------------------------------------
// Token / sesión
// ---------------------------------------------------------------------------

function getToken() {
  return localStorage.getItem('token');
}

function getAuthHeaders() {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: 'Bearer ' + token }),
  };
}

function isAuthenticated() {
  return !!getToken();
}

function getUserRole() {
  return localStorage.getItem('role');
}

function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || '{}');
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Guards
// ---------------------------------------------------------------------------

function requireAuth() {
  if (!isAuthenticated()) {
    window.location.href = 'login.html';
  }
}

function requireAdmin() {
  if (getUserRole() !== 'admin') {
    window.location.href = 'home.html';
  }
}

// ---------------------------------------------------------------------------
// Sesión
// ---------------------------------------------------------------------------

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('user');
  localStorage.removeItem('activePrivateKey');
  localStorage.removeItem('activePublicKey');
  window.location.href = 'login.html';
}

// ---------------------------------------------------------------------------
// Navegación
// ---------------------------------------------------------------------------

function goTo(path) {
  if (path.startsWith('#')) {
    // Navegación interna — delegada al page script
    return;
  }
  window.location.href = path;
}

// ---------------------------------------------------------------------------
// Feedback visual
// ---------------------------------------------------------------------------

function showError(elId, message, durationMs = 5000) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = message;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), durationMs);
}

function showSuccess(elId, message, durationMs = 3000) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = message;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), durationMs);
}
