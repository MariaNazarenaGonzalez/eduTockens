/* DEO GLORIA */

// crypto-auth.js — Generación de claves y firma Ed25519 para eduTockens.
//
// Migración: ECDSA P-384 (Web Crypto API, claves PEM/DER) → Ed25519
// (@noble/curves, claves hex), para ser compatible con el NCT
// (ver infoIntegracionPilar2conEduTockens.txt y shared/block.py / shared/crypto.py).
//
// Script clásico (NO ES module) — se carga con <script src="../js/crypto-auth.js">,
// igual que el resto del proyecto. @noble/curves se importa dinámicamente
// desde un CDN ESM dentro de un wrapper async, así no se rompe la carga
// síncrona de <script> clásico.
//
// Todas las claves y firmas se manejan como strings hex lowercase:
//   - public key:  64 hex chars (32 bytes)
//   - private key: 64 hex chars (32 bytes)
//   - signature:   128 hex chars (64 bytes)

const NOBLE_ED25519_CDN_URL = 'https://esm.sh/@noble/curves@1.7.0/ed25519';

// Cache del módulo importado dinámicamente, para no re-pedirlo al CDN en
// cada llamada a generar/firmar.
let _ed25519ModulePromise = null;

function _loadEd25519() {
  if (!_ed25519ModulePromise) {
    _ed25519ModulePromise = import(NOBLE_ED25519_CDN_URL).then((mod) => mod.ed25519);
  }
  return _ed25519ModulePromise;
}

// ---------------------------------------------------------------------------
// Helpers hex <-> bytes
// ---------------------------------------------------------------------------

function bytesToHex(bytes) {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function hexToBytes(hex) {
  const clean = hex.trim().toLowerCase();
  const bytes = new Uint8Array(clean.length / 2);
  for (let i = 0; i < clean.length; i += 2) {
    bytes[i / 2] = parseInt(clean.substring(i, i + 2), 16);
  }
  return bytes;
}

// ---------------------------------------------------------------------------
// Generación de claves
// ---------------------------------------------------------------------------

/**
 * Genera un par de claves Ed25519 nuevo.
 * @returns {Promise<{ privateKeyHex: string, publicKeyHex: string }>}
 */
async function generateEd25519KeyPairHex() {
  const ed25519 = await _loadEd25519();
  const privateKey = ed25519.utils.randomPrivateKey(); // Uint8Array(32)
  const publicKey = ed25519.getPublicKey(privateKey); // Uint8Array(32)

  return {
    privateKeyHex: bytesToHex(privateKey),
    publicKeyHex: bytesToHex(publicKey),
  };
}

// ---------------------------------------------------------------------------
// Obtener el challenge del servidor
// ---------------------------------------------------------------------------

/**
 * GET /api/auth/challenge → el timestamp actual del servidor (segundos,
 * entero) como string. NO se persiste en el servidor — la validez se
 * controla por ventana de tiempo en el momento de /login o /register.
 *
 * @returns {Promise<string>} el challenge, tal cual hay que devolverlo firmado
 */
async function fetchAuthChallenge() {
  const response = await fetch('/api/auth/challenge');
  if (!response.ok) {
    throw new Error('No se pudo obtener el desafío del servidor');
  }

  const data = await response.json();
  return data.challenge;
}

// ---------------------------------------------------------------------------
// Firma del challenge
// ---------------------------------------------------------------------------

/**
 * Firma el challenge (string, tal cual fue recibido del servidor — SIN
 * transformarlo) con la clave privada Ed25519 del usuario (hex).
 *
 * IMPORTANTE: se firma el string exacto, codificado a UTF-8 — igual que
 * el NCT hace con tx_id.encode() en Python. No reformatear el challenge
 * antes de firmar.
 *
 * @param {string} privateKeyHex - 64 hex chars
 * @param {string} challenge - el string devuelto por fetchAuthChallenge()
 * @returns {Promise<string>} la firma, 128 hex chars
 */
async function signChallengeWithPrivateKey(privateKeyHex, challenge) {
  const ed25519 = await _loadEd25519();
  const privateKeyBytes = hexToBytes(privateKeyHex);
  const challengeBytes = new TextEncoder().encode(challenge);
  const signature = ed25519.sign(challengeBytes, privateKeyBytes);
  return bytesToHex(signature);
}

/**
 * Verificación local opcional (debugging) — NO reemplaza la verificación
 * del servidor, que es la autoritativa.
 *
 * @param {string} publicKeyHex - 64 hex chars
 * @param {string} challenge
 * @param {string} signatureHex - 128 hex chars
 * @returns {Promise<boolean>}
 */
async function verifyChallengeSignature(publicKeyHex, challenge, signatureHex) {
  const ed25519 = await _loadEd25519();
  const publicKeyBytes = hexToBytes(publicKeyHex);
  const challengeBytes = new TextEncoder().encode(challenge);
  const signatureBytes = hexToBytes(signatureHex);
  return ed25519.verify(signatureBytes, challengeBytes, publicKeyBytes);
}