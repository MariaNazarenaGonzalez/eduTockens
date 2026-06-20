/* DEO GLORIA */

// tx-signer.js — Construcción del tx_id para transacciones del NCT (EARN/SPEND).
//
// Replica exactamente `Transaction._signing_dict()` de shared/block.py
// (código fuente real del NCT):
//
//   - tx_id = SHA-256(JSON canónico del signing dict, sort_keys).
//   - `amount` es un entero, nunca float.
//   - `timestamp` NO participa del signing dict ni del hash — el NCT lo
//     fija server-side al recibir el POST.
//
// La FIRMA del tx_id se hace con `signChallengeWithPrivateKey` de
// crypto-auth.js (misma operación: firmar bytes UTF-8 de un string hex
// con Ed25519) — no se duplica esa lógica acá.
//
// Script clásico — se carga con <script src="../js/tx-signer.js">.
// Depende de crypto-auth.js estar cargado antes (usa bytesToHex... no,
// en realidad no depende de sus helpers internos, solo de la firma final
// que hace cada caller).

/**
 * Calcula tx_id = SHA-256(JSON canónico del signing dict).
 *
 * @param {object} txBody - { sender_pubkey, receiver_pubkey, amount,
 *                            tx_type, concept, nonce } — SIN timestamp,
 *                            SIN signature.
 * @returns {Promise<string>} tx_id, 64 hex chars
 */
async function computeTxId(txBody) {
  if (!Number.isInteger(txBody.amount)) {
    throw new Error(
      `amount debe ser un entero (recibido ${txBody.amount}) — el NCT tipa ` +
      'Transaction.amount como int, no float'
    );
  }

  const signingDict = {
    sender_pubkey: txBody.sender_pubkey,
    receiver_pubkey: txBody.receiver_pubkey,
    amount: txBody.amount,
    tx_type: txBody.tx_type,
    concept: txBody.concept,
    nonce: txBody.nonce,
  };

  // IMPORTANTE: no usar JSON.stringify() directamente. Python serializa
  // con json.dumps(..., sort_keys=True), cuyo separador POR DEFECTO es
  // ", " y ": " (CON espacio). JSON.stringify() de JS produce "," y ":"
  // (SIN espacio) — strings distintos producen hashes SHA-256 distintos.
  // Se construye el JSON a mano para igualar byte a byte la salida de
  // Python.
  const json = _canonicalJsonDumps(signingDict);

  const encoded = new TextEncoder().encode(json);
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoded);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Serializa un objeto plano (claves string, valores string|number) imitando
 * byte a byte la salida de `json.dumps(d, sort_keys=True, ensure_ascii=False)`
 * de Python: claves en orden alfabético, separador ", " entre pares,
 * separador ": " entre clave y valor.
 *
 * Solo soporta los tipos que aparecen en un signing dict de transacción
 * (string, integer) — no es un serializador JSON genérico.
 */
function _canonicalJsonDumps(obj) {
  const keys = Object.keys(obj).sort();
  const parts = keys.map((key) => {
    const value = obj[key];
    const serializedValue =
      typeof value === 'number' ? String(value) : JSON.stringify(value);
    return `${JSON.stringify(key)}: ${serializedValue}`;
  });
  return `{${parts.join(', ')}}`;
}