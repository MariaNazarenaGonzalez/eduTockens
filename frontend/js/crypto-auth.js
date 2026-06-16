async function fetchAuthChallenge() {
  const response = await fetch('/api/auth/challenge');
  if (!response.ok) {
    throw new Error('No se pudo obtener el desafio del servidor');
  }

  const data = await response.json();
  return data.challenge;
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach(byte => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

function base64ToArrayBuffer(base64) {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

function pemToArrayBuffer(pem) {
  const base64 = pem
    .replace(/-----BEGIN [^-]+-----/g, '')
    .replace(/-----END [^-]+-----/g, '')
    .replace(/\s/g, '');
  return base64ToArrayBuffer(base64);
}

function arrayBufferToPem(buffer, label) {
  let base64 = arrayBufferToBase64(buffer);
  const lines = [];
  while (base64.length > 0) {
    lines.push(base64.substring(0, 64));
    base64 = base64.substring(64);
  }
  return `-----BEGIN ${label}-----\n${lines.join('\n')}\n-----END ${label}-----`;
}

function bytesToHex(bytes) {
  return Array.from(bytes)
    .map(byte => byte.toString(16).padStart(2, '0'))
    .join('');
}

function derLength(hex) {
  return (hex.length / 2).toString(16).padStart(2, '0');
}

function trimIntegerHex(hex) {
  while (hex.startsWith('00') && hex.length > 2) {
    hex = hex.substring(2);
  }

  if (parseInt(hex.substring(0, 2), 16) > 127) {
    hex = `00${hex}`;
  }

  return hex;
}

function ecdsaRawSignatureToDer(signature) {
  const signHex = bytesToHex(new Uint8Array(signature));
  const coordinateLength = signHex.length / 2;
  const r = trimIntegerHex(signHex.substring(0, coordinateLength));
  const s = trimIntegerHex(signHex.substring(coordinateLength));
  const payload = `02${derLength(r)}${r}02${derLength(s)}${s}`;
  return `30${derLength(payload)}${payload}`;
}

async function generateEcdsaKeyPairPem() {
  const keypair = await window.crypto.subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-384' },
    true,
    ['sign', 'verify']
  );

  const publicKey = await window.crypto.subtle.exportKey('spki', keypair.publicKey);
  const privateKey = await window.crypto.subtle.exportKey('pkcs8', keypair.privateKey);

  return {
    publicKeyPem: arrayBufferToPem(publicKey, 'PUBLIC KEY'),
    privateKeyPem: arrayBufferToPem(privateKey, 'PRIVATE KEY'),
  };
}

async function signChallengeWithPrivateKey(privateKeyPem, challenge) {
  const privateKey = await window.crypto.subtle.importKey(
    'pkcs8',
    pemToArrayBuffer(privateKeyPem),
    { name: 'ECDSA', namedCurve: 'P-384' },
    false,
    ['sign']
  );

  const encodedChallenge = new TextEncoder().encode(challenge);
  const signature = await window.crypto.subtle.sign(
    { name: 'ECDSA', hash: { name: 'SHA-1' } },
    privateKey,
    encodedChallenge
  );

  return ecdsaRawSignatureToDer(signature);
}
