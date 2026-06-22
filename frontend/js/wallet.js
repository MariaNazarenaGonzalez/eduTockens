/* DEO GLORIA */

/**
 * wallet.js — Billetera blockchain unificada para eduTockens.
 *
 * Encapsula TODA la lógica criptográfica del frontend en una única
 * interfaz pública. El resto de la aplicación (purchase.js, admin.js,
 * auth.js) debe usar EXCLUSIVAMENTE este módulo para:
 *
 *   - Generar claves Ed25519
 *   - Cifrar / descifrar la clave privada (AES-GCM + PBKDF2)
 *   - Firmar transacciones (SPEND, EARN)
 *   - Firmar challenges de autenticación
 *   - Consultar la clave pública almacenada
 *
 * Dependencias (deben cargarse ANTES que este script):
 *   crypto-auth.js   → generateEd25519KeyPairHex, signChallengeWithPrivateKey,
 *                       fetchAuthChallenge
 *   wallet-crypto.js → encryptAndStorePrivateKey, decryptStoredPrivateKey,
 *                       hasStoredWallet, clearStoredWallet
 *   tx-signer.js     → computeTxId
 *
 * Carga:
 *   <script src="../js/crypto-auth.js"></script>
 *   <script src="../js/wallet-crypto.js"></script>
 *   <script src="../js/tx-signer.js"></script>
 *   <script src="../js/wallet.js"></script>
 *
 * Expone el objeto global `EduWallet`.
 *
 * ── Contrato de diseño ──────────────────────────────────────────
 *
 * Esta wallet es el ÚNICO componente del frontend que entiende de
 * blockchain.  El resto del código (páginas, UI, navegación) solo
 * conoce dos conceptos:
 *
 *   1. "Necesito firmar esto" → EduWallet.signTransaction(...)
 *   2. "Necesito autenticarme" → EduWallet.signChallenge(...)
 *
 * Ninguna página debe importar crypto-auth.js, wallet-crypto.js ni
 * tx-signer.js directamente.  Si el NCT cambia su wire format, solo
 * este archivo (y sus dependencias internas) necesita actualizarse.
 */

const EduWallet = (() => {
  // -------------------------------------------------------------------
  // Validación de dependencias
  // -------------------------------------------------------------------

  function _require(globalName, scriptFileName) {
    if (typeof window[globalName] !== 'function') {
      throw new Error(
        `EduWallet: ${scriptFileName} debe cargarse antes que wallet.js. ` +
        `Falta la función global ${globalName}().`
      );
    }
  }

  // Se validan en el momento de la carga del script, no lazy.
  // Si falta una dependencia, el error se ve en consola inmediatamente.
  _require('generateEd25519KeyPairHex', 'crypto-auth.js');
  _require('signChallengeWithPrivateKey', 'crypto-auth.js');
  _require('fetchAuthChallenge', 'crypto-auth.js');
  _require('encryptAndStorePrivateKey', 'wallet-crypto.js');
  _require('decryptStoredPrivateKey', 'wallet-crypto.js');
  _require('hasStoredWallet', 'wallet-crypto.js');
  _require('clearStoredWallet', 'wallet-crypto.js');
  _require('computeTxId', 'tx-signer.js');

  // -------------------------------------------------------------------
  // Helpers internos
  // -------------------------------------------------------------------

  /**
   * Normaliza una clave hex: trimmed y lowercase.
   * @param {string} hex
   * @returns {string}
   */
  function _norm(hex) {
    return (hex || '').trim().toLowerCase();
  }

  /**
   * Valida que un string sean 64 caracteres hex.
   * @param {string} hex
   * @returns {boolean}
   */
  function _isValidPubkeyHex(hex) {
    return /^[0-9a-f]{64}$/.test(_norm(hex));
  }

  // -------------------------------------------------------------------
  // 1. Generación de claves
  // -------------------------------------------------------------------

  /**
   * Genera un par de claves Ed25519 nuevo.
   *
   * La clave privada NUNCA se envía al backend.  El caller es responsable
   * de cifrarla con storePrivateKey() y descartar el texto plano.
   *
   * @returns {Promise<{privateKeyHex: string, publicKeyHex: string}>}
   */
  async function generateKeypair() {
    const result = await generateEd25519KeyPairHex();
    return {
      privateKeyHex: _norm(result.privateKeyHex),
      publicKeyHex: _norm(result.publicKeyHex),
    };
  }

  // -------------------------------------------------------------------
  // 2. Almacenamiento cifrado de la clave privada
  // -------------------------------------------------------------------

  /**
   * Cifra `privateKeyHex` con una clave derivada de `password` (PBKDF2 →
   * AES-GCM) y la persiste en localStorage bajo `walletCipher:{legajo}`.
   *
   * @param {string} legajo — identificador del estudiante/admin
   * @param {string} privateKeyHex — 64 hex chars
   * @param {string} password — contraseña del usuario (nunca se guarda)
   * @returns {Promise<void>}
   */
  async function storePrivateKey(legajo, privateKeyHex, password) {
    if (!legajo) throw new Error('storePrivateKey: legajo es requerido');
    if (!_isValidPubkeyHex(privateKeyHex)) {
      throw new Error('storePrivateKey: privateKeyHex debe ser 64 caracteres hex');
    }
    if (!password || password.length < 8) {
      throw new Error('storePrivateKey: password debe tener al menos 8 caracteres');
    }
    await encryptAndStorePrivateKey(legajo, _norm(privateKeyHex), password);
  }

  /**
   * Descifra la clave privada desde localStorage.
   *
   * La clave privada se devuelve en texto plano en MEMORIA.  El caller es
   * responsable de usarla inmediatamente y NO persistirla ni loguearla.
   *
   * @param {string} legajo
   * @param {string} password
   * @returns {Promise<string>} privateKeyHex (64 hex chars)
   * @throws {Error} si no hay wallet guardada o el password es incorrecto
   */
  async function loadPrivateKey(legajo, password) {
    if (!legajo) throw new Error('loadPrivateKey: legajo es requerido');
    if (!password) throw new Error('loadPrivateKey: password es requerido');
    const hex = await decryptStoredPrivateKey(legajo, password);
    return _norm(hex);
  }

  /**
   * Verifica si existe una wallet cifrada para `legajo`.
   * @param {string} legajo
   * @returns {boolean}
   */
  function hasStoredKey(legajo) {
    return hasStoredWallet(legajo);
  }

  /**
   * Elimina la wallet cifrada de localStorage (logout, reset de cuenta).
   * @param {string} legajo
   */
  function clearStoredKey(legajo) {
    clearStoredWallet(legajo);
  }

  // -------------------------------------------------------------------
  // 3. Firma de transacciones blockchain
  // -------------------------------------------------------------------

  /**
   * Construye y firma una transacción para el NCT.
   *
   * Flujo interno:
   *   1. Calcula tx_id = SHA-256(json canónico del signing dict)
   *      usando exactamente el mismo algoritmo que Transaction._signing_dict()
   *      de shared/block.py
   *   2. Firma tx_id con la clave privada Ed25519
   *   3. Devuelve {tx_id, signature} listos para enviar al NCT
   *
   * @param {object} txBody — campos del signing dict del NCT
   * @param {string} txBody.sender_pubkey    — 64 hex
   * @param {string} txBody.receiver_pubkey  — 64 hex
   * @param {number} txBody.amount           — entero positivo
   * @param {string} txBody.tx_type          — "EARN" | "SPEND"
   * @param {string} txBody.concept          — texto libre
   * @param {number} txBody.nonce            — pending_nonce del sender
   * @param {string} privateKeyHex           — clave privada del firmante (64 hex)
   *
   * @returns {Promise<{tx_id: string, signature: string}>}
   */
  async function signTransaction(txBody, privateKeyHex) {
    // --- Validaciones pre-firma ---
    const required = ['sender_pubkey', 'receiver_pubkey', 'amount', 'tx_type', 'concept', 'nonce'];
    for (const field of required) {
      if (txBody[field] === undefined || txBody[field] === null) {
        throw new Error(`signTransaction: falta el campo requerido "${field}"`);
      }
    }

    if (!['EARN', 'SPEND'].includes(txBody.tx_type)) {
      throw new Error(`signTransaction: tx_type debe ser "EARN" o "SPEND", recibido "${txBody.tx_type}"`);
    }

    if (!Number.isInteger(txBody.amount) || txBody.amount <= 0) {
      throw new Error(`signTransaction: amount debe ser un entero positivo, recibido ${txBody.amount}`);
    }

    if (!Number.isInteger(txBody.nonce) || txBody.nonce < 0) {
      throw new Error(`signTransaction: nonce debe ser un entero >= 0, recibido ${txBody.nonce}`);
    }

    if (!_isValidPubkeyHex(privateKeyHex)) {
      throw new Error('signTransaction: privateKeyHex debe ser 64 caracteres hex');
    }

    // --- Calcular tx_id (delega en tx-signer.js — misma lógica que el NCT) ---
    const txId = await computeTxId({
      sender_pubkey: _norm(txBody.sender_pubkey),
      receiver_pubkey: _norm(txBody.receiver_pubkey),
      amount: txBody.amount,
      tx_type: txBody.tx_type,
      concept: txBody.concept,
      nonce: txBody.nonce,
    });

    // --- Firmar tx_id con Ed25519 ---
    const signature = await signChallengeWithPrivateKey(_norm(privateKeyHex), txId);

    return { tx_id: txId, signature };
  }

  // -------------------------------------------------------------------
  // 4. Firma de challenges de autenticación
  // -------------------------------------------------------------------

  /**
   * Obtiene el challenge actual del servidor.
   * @returns {Promise<string>}
   */
  async function fetchChallenge() {
    return fetchAuthChallenge();
  }

  /**
   * Firma un challenge de autenticación con la clave privada.
   *
   * @param {string} challenge — timestamp del servidor como string
   * @param {string} privateKeyHex — 64 hex chars
   * @returns {Promise<string>} signature — 128 hex chars
   */
  async function signChallenge(challenge, privateKeyHex) {
    if (!challenge) throw new Error('signChallenge: challenge es requerido');
    if (!_isValidPubkeyHex(privateKeyHex)) {
      throw new Error('signChallenge: privateKeyHex debe ser 64 caracteres hex');
    }
    return signChallengeWithPrivateKey(_norm(privateKeyHex), challenge);
  }

  // -------------------------------------------------------------------
  // 5. Consulta de clave pública
  // -------------------------------------------------------------------

  /**
   * Devuelve la clave pública Ed25519 asociada a un legajo.
   *
   * Orden de búsqueda:
   *   1. `publicKey:{legajo}` — guardada por auth.js en register()
   *   2. `activePublicKey` — clave de la sesión activa
   *   3. `user.public_key` — del objeto user en localStorage (JWT)
   *
   * @param {string} legajo
   * @returns {string|null} publicKeyHex (64 hex) o null si no se encuentra
   */
  function getPublicKey(legajo) {
    // 1. Clave específica del legajo
    const keyed = localStorage.getItem(`publicKey:${legajo}`);
    if (keyed && _isValidPubkeyHex(keyed)) return _norm(keyed);

    // 2. Clave de la sesión activa
    const active = localStorage.getItem('activePublicKey');
    if (active && _isValidPubkeyHex(active)) return _norm(active);

    // 3. Del objeto user del JWT
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      if (user.public_key && _isValidPubkeyHex(user.public_key)) {
        return _norm(user.public_key);
      }
    } catch {
      // JSON malformado — ignorar
    }

    return null;
  }

  /**
   * Devuelve la clave pública de la sesión activa (sin requerir legajo).
   * @returns {string|null}
   */
  function getActivePublicKey() {
    return getPublicKey(null);
  }

  // -------------------------------------------------------------------
  // API pública
  // -------------------------------------------------------------------

  return {
    // Keypair
    generateKeypair,

    // Almacenamiento cifrado
    storePrivateKey,
    loadPrivateKey,
    hasStoredKey,
    clearStoredKey,

    // Firma
    signTransaction,
    signChallenge,
    fetchChallenge,

    // Clave pública
    getPublicKey,
    getActivePublicKey,
  };
})();
