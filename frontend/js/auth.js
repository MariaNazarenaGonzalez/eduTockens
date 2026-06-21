/* DEO GLORIA */

/**
 * auth.js — Login, registro y gestión de sesión para eduTockens.
 *
 * Migración Ed25519: la clave privada se genera client-side
 * (crypto-auth.js) y se guarda en localStorage — nunca se envía al
 * backend. El backend solo recibe la clave pública y firmas.
 *
 * Debe cargarse como módulo:
 *   <script type="module" src="js/auth.js"></script>
 */

// NOTA: crypto-auth.js y wallet-crypto.js se cargan como <script> clásico
// (NO como ES modules) — exponen funciones globales. Este módulo las referencia
// directamente del scope global en lugar de importarlas.
//   crypto-auth.js  → generateEd25519KeyPairHex, fetchAuthChallenge, signChallengeWithPrivateKey
//   wallet-crypto.js → decryptStoredPrivateKey, encryptAndStorePrivateKey

const API_BASE_URL = '/api';

// ---------------------------------------------------------------------------
// Token / sesión
// ---------------------------------------------------------------------------

function saveToken(token) {
  localStorage.setItem('token', token);
}

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

// ---------------------------------------------------------------------------
// Claves Ed25519 — generación y almacenamiento local
// ---------------------------------------------------------------------------

/**
 * La clave privada NUNCA sale del navegador. Se guarda en localStorage
 * asociada al legajo, para poder firmar transacciones SPEND más adelante
 * (marketplace) sin tener que volver a pedirla.
 *
 * ADVERTENCIA (documentada como limitación conocida, igual que en el
 * README): localStorage no es un almacenamiento seguro para secretos en
 * un entorno de producción real. Para este PoC es aceptable; en
 * producción se recomendaría WebCrypto con claves no-extraíbles o un
 * wallet externo.
 */
function saveKeyPair(legajo, privateKeyHex, publicKeyHex) {
  localStorage.setItem(`privateKey:${legajo}`, privateKeyHex);
  localStorage.setItem(`publicKey:${legajo}`, publicKeyHex);
  // También se guarda "sin namespacing" para la sesión activa actual,
  // así purchase.js no necesita conocer el legajo para firmar.
  localStorage.setItem('activePrivateKey', privateKeyHex);
  localStorage.setItem('activePublicKey', publicKeyHex);
}

function getActiveKeyPair() {
  const privateKeyHex = localStorage.getItem('activePrivateKey');
  const publicKeyHex = localStorage.getItem('activePublicKey');
  if (!privateKeyHex || !publicKeyHex) {
    return null;
  }
  return { privateKeyHex, publicKeyHex };
}

// ---------------------------------------------------------------------------
// Registro
// ---------------------------------------------------------------------------

/**
 * Genera un keypair Ed25519 nuevo, lo guarda localmente, firma el
 * challenge del servidor y registra al estudiante.
 *
 * @param {string} legajo
 * @param {string} name
 * @param {string} email
 * @returns {Promise<object>} el usuario creado
 */
async function register(legajo, name, email) {
  try {
    const { privateKeyHex, publicKeyHex } = await generateEd25519KeyPairHex();
    const challenge = await fetchAuthChallenge();
    const signature = await signChallengeWithPrivateKey(privateKeyHex, challenge);

    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        legajo,
        name,
        email,
        public_key: publicKeyHex,
        challenge,
        signature,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error en registro');
    }

    // Solo se guarda la clave localmente si el registro fue exitoso —
    // si falla, no queremos una clave "huérfana" sin cuenta asociada.
    saveKeyPair(legajo, privateKeyHex, publicKeyHex);

    return await response.json();
  } catch (error) {
    console.error('Register error:', error);
    throw error;
  }
}

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

/**
 * Firma el challenge del servidor con la clave privada guardada
 * localmente para `identifier` (o la clave activa, si no hay una
 * asociada a ese identifier puntual) y hace login.
 *
 * @param {string} identifier - legajo o email del usuario
 */
async function login(identifier, password) {
  try {
    // La clave privada se descifra con el password (wallet-crypto.js).
    // Si no hay wallet cifrado, se intenta con la clave activa en texto plano
    // (modo legacy — solo para desarrollo).
    let privateKeyHex;
    try {
      privateKeyHex = await decryptStoredPrivateKey(identifier, password);
    } catch {
      privateKeyHex =
        localStorage.getItem(`privateKey:${identifier}`) ||
        localStorage.getItem('activePrivateKey');
    }

    if (!privateKeyHex) {
      throw new Error(
        'No se encontró una clave privada local para este usuario. ' +
        'Registrate primero en este navegador.'
      );
    }

    const challenge = await fetchAuthChallenge();
    const signature = await signChallengeWithPrivateKey(privateKeyHex, challenge);

    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password, challenge, signature }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error en login');
    }

    const data = await response.json();
    saveToken(data.access_token);
    localStorage.setItem('role', data.user.role);
    localStorage.setItem('user', JSON.stringify(data.user));
    localStorage.setItem('activePrivateKey', privateKeyHex);
    localStorage.setItem('activePublicKey', data.user.public_key);

    return data;
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
}

// ---------------------------------------------------------------------------
// Logout / guards
// ---------------------------------------------------------------------------

function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  localStorage.removeItem('user');
  localStorage.removeItem('activePrivateKey');
  localStorage.removeItem('activePublicKey');
  window.location.href = 'login.html';
}

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

export {
  saveToken,
  getToken,
  getAuthHeaders,
  isAuthenticated,
  getUserRole,
  getActiveKeyPair,
  register,
  login,
  logout,
  requireAuth,
  requireAdmin,
};