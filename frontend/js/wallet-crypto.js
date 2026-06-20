/* DEO GLORIA */

// wallet-crypto.js — Cifrado local de la clave privada Ed25519.
//
// La clave privada nunca se guarda en texto plano. Se cifra con AES-GCM
// usando una clave derivada (PBKDF2) del MISMO password que el usuario
// usa para autenticarse contra el backend (ver core/security.py:
// verify_password). El backend nunca ve la clave privada ni el material
// derivado — solo el hash bcrypt del password en sí.
//
// La contraseña NUNCA se guarda — se pide cada vez que hace falta cifrar
// o descifrar (login y cada compra), tal como se definió.
//
// Formato persistido en localStorage (por legajo):
//   walletCipher:{legajo} = base64(salt) + ":" + base64(iv) + ":" + base64(ciphertext)
//
// Script clásico — se carga con <script src="../js/wallet-crypto.js">.

const PBKDF2_ITERATIONS = 250000;
const SALT_BYTES = 16;
const IV_BYTES = 12;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _bytesToBase64(bytes) {
  return window.btoa(String.fromCharCode(...new Uint8Array(bytes)));
}

function _base64ToBytes(base64) {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

async function _deriveAesKey(password, saltBytes) {
  const passwordKey = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveKey']
  );

  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: saltBytes,
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    passwordKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

// ---------------------------------------------------------------------------
// Cifrado / descifrado de la clave privada
// ---------------------------------------------------------------------------

/**
 * Cifra `privateKeyHex` con una clave derivada de `password` y lo persiste
 * en localStorage bajo la clave `walletCipher:{legajo}`.
 *
 * @param {string} legajo
 * @param {string} privateKeyHex - 64 hex chars
 * @param {string} password
 */
async function encryptAndStorePrivateKey(legajo, privateKeyHex, password) {
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));

  const aesKey = await _deriveAesKey(password, salt);
  const plaintext = new TextEncoder().encode(privateKeyHex);

  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    aesKey,
    plaintext
  );

  const stored = [
    _bytesToBase64(salt),
    _bytesToBase64(iv),
    _bytesToBase64(ciphertext),
  ].join(':');

  localStorage.setItem(`walletCipher:${legajo}`, stored);
}

/**
 * Descifra la clave privada guardada para `legajo` usando `password`.
 *
 * @param {string} legajo
 * @param {string} password
 * @returns {Promise<string>} privateKeyHex (64 hex chars)
 * @throws {Error} si no hay clave guardada, o si el password es incorrecto
 *                  (AES-GCM falla la verificación de integridad → excepción)
 */
async function decryptStoredPrivateKey(legajo, password) {
  const stored = localStorage.getItem(`walletCipher:${legajo}`);
  if (!stored) {
    throw new Error(
      `No hay una clave privada guardada en este navegador para el legajo ${legajo}`
    );
  }

  const [saltB64, ivB64, ciphertextB64] = stored.split(':');
  const salt = _base64ToBytes(saltB64);
  const iv = _base64ToBytes(ivB64);
  const ciphertext = _base64ToBytes(ciphertextB64);

  const aesKey = await _deriveAesKey(password, salt);

  let plaintext;
  try {
    plaintext = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, aesKey, ciphertext);
  } catch (error) {
    // AES-GCM falla la verificación de tag de integridad si el password
    // (y por lo tanto la clave derivada) es incorrecto.
    throw new Error('Contraseña incorrecta — no se pudo descifrar la clave privada');
  }

  return new TextDecoder().decode(plaintext);
}

/**
 * True si hay una clave privada cifrada guardada para `legajo`.
 */
function hasStoredWallet(legajo) {
  return !!localStorage.getItem(`walletCipher:${legajo}`);
}

/**
 * Elimina la clave privada cifrada guardada para `legajo` (logout/reset).
 */
function clearStoredWallet(legajo) {
  localStorage.removeItem(`walletCipher:${legajo}`);
}
