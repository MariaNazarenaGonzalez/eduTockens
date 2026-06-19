# Integración eduTockens ↔ NCT (Pilar 2)

Este paquete contiene los archivos nuevos/modificados para conectar eduTockens
al NCT real, migrando la autenticación y las transacciones de ECDSA P-384/PEM
a Ed25519 hex (compatible con `shared/block.py` y `shared/crypto.py` del NCT).

## Qué se hizo

| Archivo | Cambio |
|---|---|
| `db/init.sql` | `users.public_key` (sin password), tabla `vendors` nueva, `products.vendor_id`, tabla `transactions_log` nueva, `roles` solo `student`/`admin` |
| `backend/core/crypto.py` | **Nuevo.** Ed25519: firmar, verificar, generar keypair, `compute_tx_id` (replica `Transaction._signing_dict()` de `shared/block.py`) |
| `backend/core/config.py` | + `nct_base_url` (puerto 8080), `academic_authority_private_key/public_key`, `auth_challenge_window_seconds` |
| `backend/core/security.py` | **Nuevo.** Challenge timestamp (stateless), verificación de firma, JWT |
| `backend/models/models.py` | `User.public_key`, `Vendor` (nuevo), `Product.vendor_id`, `TransactionLog` (nuevo) |
| `backend/schemas/schemas.py` | Esquemas de auth/vendor/product/purchase/earn actualizados |
| `backend/services/nct_client.py` | **Reescrito completo.** `sender_pubkey`/`receiver_pubkey`/`tx_type`/`nonce`/`signature`, `emit_earn` (firma el backend), `submit_signed_spend` (reenvía firma del cliente) |
| `backend/routers/*.py` | `auth`, `admin` (+ vendors, earn), `products` (+ `vendor_pubkey` embebido), `purchases` (reenvío de SPEND firmado), `students` (balance+nonce, historial local), `users` |
| `frontend/js/crypto-auth.js` | Ed25519 vía CDN ESM (`esm.sh/@noble/curves`), reemplaza ECDSA P-384/WebCrypto |
| `frontend/js/auth.js` | Genera/guarda keypair en localStorage, firma el challenge |
| `frontend/js/tx-signer.js` | **Nuevo.** `computeTxId`/`signTxId` — replica byte a byte la serialización de Python |
| `frontend/js/purchase.js` | Arma y firma el SPEND client-side antes de `POST /purchases` |
| `frontend/js/admin.js` | EARN, vendors, productos, stats (sin firma client-side — el backend firma EARN) |

## ⚠️ Coordinación obligatoria con el NCT

La clave pública en `ACADEMIC_AUTHORITY_PUBLIC_KEY` (backend eduTockens) y
`AUTHORITY_PUBKEY` (NCT, `nct/.env`) **deben ser exactamente la misma clave**.
Si no coinciden, **todo EARN será rechazado** con
`"EARN sender_pubkey does not match AUTHORITY_PUBKEY"`.

Variables de entorno nuevas a configurar en el backend (`.env`):

```env
NCT_BASE_URL=http://nct:8080
ACADEMIC_AUTHORITY_PRIVATE_KEY=<64 hex chars — NUNCA commitear, NUNCA loguear>
ACADEMIC_AUTHORITY_PUBLIC_KEY=<64 hex chars — debe == AUTHORITY_PUBKEY del NCT>
AUTH_CHALLENGE_WINDOW_SECONDS=60
```

El par de desarrollo usado en el seed de `init.sql` (admin):

```
private (.env del backend, no commitear): 20139855d1c596f918cdbefa75108b469fcd96e9c597b014385ab9b33e7503f7
public  (ya en init.sql y AUTHORITY_PUBKEY del NCT): 4bda9548d161d7edf80fc1ac34a09e4c609db55bfa5a58fe44c000ddae936a74
```

Generar un par propio para cualquier entorno que no sea desarrollo local:

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
priv = Ed25519PrivateKey.generate()
print(priv.private_bytes_raw().hex())
print(priv.public_key().public_bytes_raw().hex())
```

## Pendiente de tu lado (no incluido en este paquete)

1. **HTML**: las páginas que cargan `auth.js`/`crypto-auth.js`/`purchase.js`/`admin.js`
   necesitan `<script type="module" src="js/auth.js"></script>` — son ES modules,
   `<script>` plano no alcanza.
2. **`register.html`/`login.html`**: ajustar los formularios para llamar a
   `register(legajo, name, email)` / `login(identifier)` (las nuevas firmas
   de `auth.js` — ya no piden password ni manejan PEM).
3. **`home.js`**: aún no se tocó — debe consumir `GET /students/{legajo}/balance`
   (ahora trae `nonce` también) y `GET /students/{legajo}/transactions`.
4. **`marketplace.js`**: aún no se tocó — debe mostrar `vendor_pubkey` no es
   necesario en la grilla, solo en el detalle/compra.
5. Probar contra una instancia real del NCT (Redis + RabbitMQ levantados) —
   todo lo de este paquete se validó con mocks (`respx`) y interoperabilidad
   criptográfica JS↔Python directa, pero no contra el NCT corriendo de verdad.

## Validado

- `compute_tx_id` (Python) y `computeTxId` (JS) producen el **mismo SHA-256**
  byte a byte, incluyendo casos límite (acentos, comillas, montos extremos).
- Firmas generadas en JS verifican correctamente desde Python con las mismas
  primitivas Ed25519 que usaría el NCT.
- `emit_earn` arma el payload completo (consulta nonce, firma, estructura)
  correctamente contra un NCT mockeado.
- `submit_signed_spend` reenvía y propaga errores 400 del NCT correctamente.
- La app FastAPI completa (18 endpoints) carga sin errores de import.
- Todo el SQL, Python y JS pasan validación sintáctica.

## Decisiones de diseño confirmadas (no asumidas)

- Migración: eduTockens → Ed25519 (NCT no se toca).
- Auth: challenge = timestamp del servidor, stateless, ventana de 60s hacia atrás.
- Login: por `identifier` (legajo o email) — el backend busca la pubkey en su DB.
- EARN: firmado por el backend (clave de autoridad vive en env/secret).
- SPEND: firmado client-side por el estudiante; backend solo reenvía.
- Vendor: entidad nueva, creada por el admin; backend genera keypair y
  descarta la privada; el producto referencia un `vendor_id`.
- Historial de transacciones: tabla local (`transactions_log`), no se lee
  `/chain` del NCT en cada request.
- Confirmación de compra: "best effort" — un 201 del NCT se considera éxito;
  no se espera a que la tx sea minada; no se duplica la validación de saldo
  en el backend (se delega 100% al NCT).
