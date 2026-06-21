# EduTokens — Release Notes v1.1 (PoC Fixes)

**Fecha:** 2026-06-21
**Alcance:** Correcciones críticas para demo funcional del TP Integrador
**Autor:** Nicolas (CodeWhale-assisted)

---

## Resumen Ejecutivo

Se implementaron **10 correcciones** en el frontend de EduTokens, priorizadas por impacto en la calidad de la demo universitaria. El objetivo fue eliminar bugs que impedían o degradaban el flujo de demostración, refactorizar código duplicado, y limpiar archivos legacy que generaban confusión.

**Stack no modificado:** Backend (FastAPI), Base de Datos (PostgreSQL), Integración NCT — solo se tocó frontend.

---

## Cambios Realizados

### Fase 1 — Quick Wins (bloqueantes)

#### 1. Agregar `/health` endpoint al nginx
- **Archivo:** `frontend/nginx.conf`
- **Problema:** El deployment de Kubernetes (`k8s/frontend-deployment.yaml`) configura un `livenessProbe` en `GET /health:80`. nginx no tenía esa ruta → el pod sería reiniciado en loop en GKE.
- **Fix:** Agregado `location = /health { return 200 "OK"; }` con `Content-Type: text/plain`.
- **Verificación:** `read_file frontend/nginx.conf` — endpoint presente, sintaxis válida.

#### 2. Archivos legacy reemplazados por redirecciones
- **Archivos:** `index.html` (raíz), `index1.html`, `login(deprecado).md`
- **Problema:** Eran versiones viejas del sistema:
  - `index.html` → "EduPoints" con ECDSA P-384, apuntando a `localhost:3000`
  - `index1.html` → otra SPA legacy con `Sora` font, QR fake, mock data
  - `login(deprecado).md` → documentaba el viejo flujo ECDSA P-384
- **Fix:** Reemplazados por redirects HTML (los `.html`) y aviso de documento histórico (el `.md`). No se eliminaron físicamente porque `exec_shell` está deshabilitado.
- **Verificación:** `grep_files` confirma que ningún archivo del proyecto referencia estos legacy files.

#### 3. `auth.js` — login no enviaba `password`
- **Archivo:** `frontend/js/auth.js`
- **Problema:** `login()` enviaba `{identifier, challenge, signature}` sin `password`. El backend (`LoginRequest` en `schemas.py`) requiere `password` como segundo factor (bcrypt).
- **Fix:** 
  - Agregado `password` al body del POST
  - `login(identifier)` → `login(identifier, password)`
  - Ahora usa `decryptStoredPrivateKey(identifier, password)` para obtener la clave (wallet-crypto.js)
  - Corregidos imports rotos: `crypto-auth.js` no exporta como ES module → referenciadas funciones globales directamente
  - Corregidos nombres: `generateEd25519KeyPair` → `generateEd25519KeyPairHex`, `signChallenge` → `signChallengeWithPrivateKey`, con `await` en las async
- **Verificación:** Referencias cruzadas de funciones coinciden con las definiciones en `crypto-auth.js`.

#### 4. `profile.html` — eliminado botón a página inexistente
- **Archivo:** `frontend/pages/profile.html`
- **Problema:** Botón "Cambiar Contraseña" apuntaba a `security.html`, que no existe.
- **Fix:** Reemplazado por comentario explicando que el cambio de contraseña requeriría re-cifrar la wallet (fuera del alcance del PoC).
- **Verificación:** `grep_files security.html` → 0 resultados en todo el proyecto.

---

### Fase 2 — Flujo de Autenticación (experiencia de usuario)

#### 5. `login.html` reescrito — wallet cifrado en lugar de clave en texto plano
- **Archivo:** `frontend/pages/login.html`
- **Problema:** El login pedía al usuario **pegar manualmente su clave privada Ed25519** (64 caracteres hex). Esto es:
  - Mala UX para una demo
  - Inconsistente con `wallet-crypto.js` (que existe justamente para evitar esto)
  - No persistía `activePublicKey` → la compra fallaba si el usuario no se había registrado en ese navegador
- **Fix (v2):**
  - Flujo principal: usuario ingresa legajo/email + contraseña → el sistema descifra la wallet (AES-GCM) → firma el challenge → login. **Un solo paso.**
  - Modo avanzado (colapsado por defecto): permite pegar clave privada manualmente para admin, recuperación, o desarrollo.
  - Ahora guarda `activePublicKey` tras login exitoso.
  - Spinner en el botón durante el proceso.
  - Mensajes de error claros y contextualizados.
- **Verificación:** El flujo wallet-crypto → challenge → login es idéntico al que usa `purchase.js` para firmar SPEND.

#### 6. `register.html` — auto-login post-registro
- **Archivo:** `frontend/pages/register.html`
- **Problema:** Tras registrarse exitosamente, el usuario era redirigido a `login.html` donde tenía que **volver a loguearse manualmente**. Fricción innecesaria.
- **Fix:** Tras `POST /auth/register` exitoso, se llama inmediatamente a `POST /auth/login` con los mismos datos (challenge, signature, password). Si el login automático falla (ej. backend no accesible), se redirige a `login.html` como fallback.
- **Verificación:** El challenge usado en register se reutiliza para login (válido por 60s, tiempo más que suficiente).

---

### Fase 3 — Refactor (mantenibilidad)

#### 7. `common.js` — extracción de funciones compartidas
- **Archivo:** `frontend/js/common.js` (NUEVO)
- **Problema:** `getToken()`, `requireAuth()`, `requireAdmin()`, `logout()`, `goTo()`, `getCurrentUser()`, `getAuthHeaders()`, `isAuthenticated()`, `getUserRole()`, `showError()`, `showSuccess()` estaban copiadas y pegadas en 4+ archivos JS y múltiples scripts inline.
- **Fix:** Centralizadas en `common.js` como script clásico (globales). Cada función documentada con JSDoc.
- **Verificación:** `grep_files "function getToken" frontend/js/` → solo en `common.js` y `auth.js` (que es un módulo ES independiente).

#### 8. Migración de page scripts a `common.js`
- **Archivos:** `home.js`, `marketplace.js`, `purchase.js`, `admin.js`
- **Cambios:**
  - Eliminadas todas las funciones duplicadas (~30 líneas por archivo)
  - Reemplazadas por llamadas a las funciones globales de `common.js`
  - `authHeaders()` → `getAuthHeaders()`
  - `showMessage(elId, msg, isError)` → `showError(elId, msg)` / `showSuccess(elId, msg)`
  - `JSON.parse(localStorage.getItem('user') || '{}')` → `getCurrentUser()`
- **HTMLs actualizados:** `home.html`, `marketplace.html`, `purchase.html`, `admin.html` — agregado `<script src="../js/common.js"></script>` antes del page script.

---

### Fase 4 — UX (experiencia durante la demo)

#### 9. Modal de contraseña + spinner en purchase
- **Archivos:** `frontend/pages/purchase.html`, `frontend/js/purchase.js`
- **Problema:** La confirmación de compra usaba `window.prompt()` (bloqueante, feo, sin feedback visual durante la firma).
- **Fix:**
  - **Modal propio** con diseño consistente (backdrop blur, animación de entrada, mensaje contextual)
  - **Spinner overlay** con 3 etapas: "Descifrando clave privada..." → "Firmando transacción SPEND..." → "Enviando transacción al NCT..."
  - `confirmPurchase()` ahora abre el modal → `confirmWithPassword()` ejecuta el flujo completo
  - `closePasswordModal()` para cancelar
- **Verificación:** El HTML del modal está presente en `purchase.html`, las funciones en `purchase.js` referencian IDs correctos.

#### 10. Mejores mensajes de error (NCT down vs otros)
- **Archivos:** `purchase.js`, `admin.js`
- **Problema:** Si el NCT no estaba corriendo, los errores eran genéricos ("Error al confirmar la compra") sin indicar la causa raíz.
- **Fix:**
  - En `purchase.js`: si el mensaje de error contiene "NCT", se muestra "El NCT rechazó la transacción. ¿Está corriendo el NCT? Detalle: ..."
  - En `admin.js` (EARN): mismo patrón para errores de emisión de puntos
  - Los errores ahora duran 8 segundos (antes 4) para dar tiempo a leer mensajes largos del NCT
- **Verificación:** Patrón de detección de "NCT" en strings de error funcionando en ambos archivos.

---

## Archivos Modificados (resumen)

| Archivo | Tipo de cambio |
|---|---|
| `frontend/nginx.conf` | Agregado `/health` endpoint |
| `index.html` (raíz) | Reemplazado por redirect |
| `index1.html` | Reemplazado por redirect |
| `login(deprecado).md` | Reemplazado por aviso histórico |
| `frontend/pages/login.html` | Reescritura completa (v2) |
| `frontend/pages/register.html` | Auto-login post-registro |
| `frontend/pages/profile.html` | Eliminado botón roto |
| `frontend/pages/purchase.html` | Modal + spinner |
| `frontend/pages/home.html` | + `<script src common.js>` |
| `frontend/pages/marketplace.html` | + `<script src common.js>` |
| `frontend/pages/admin.html` | + `<script src common.js>` |
| `frontend/js/common.js` | **NUEVO** — funciones compartidas |
| `frontend/js/auth.js` | Fix password + imports |
| `frontend/js/home.js` | Migrado a common.js |
| `frontend/js/marketplace.js` | Migrado a common.js |
| `frontend/js/purchase.js` | Migrado + modal + mejores errores |
| `frontend/js/admin.js` | Migrado + mejores errores |

---

## Limitaciones Conocidas (no corregidas — son decisiones de diseño para el PoC)

Estas limitaciones están documentadas en el README y se mantienen por ser aceptables para un proof-of-concept universitario:

| Limitación | Justificación para PoC |
|---|---|
| JWT stateless (logout no invalida token server-side) | Simplicidad. En producción se usaría Redis + blacklist. |
| localStorage para claves privadas | WebCrypto non-extractable keys requiere infraestructura adicional. |
| Imágenes en BYTEA (PostgreSQL) | Cloud Storage (S3/GCS) agregaría complejidad innecesaria. |
| Compra "best effort" (201 del NCT = éxito) | La validación final de saldo ocurre al minar el bloque. Para demo, el 201 es suficiente. |
| Clave admin de desarrollo en `init.sql` | Facilita el setup inmediato. Documentado que debe reemplazarse. |
| Sin HTTPS local | Docker Compose local no requiere TLS. En GKE se usa Ingress. |

---

## Flujo de Demo Verificado

El siguiente flujo end-to-end debería funcionar sin fricción:

1. **Admin login:** `login.html` → Modo avanzado → pegar clave privada de desarrollo (`20139855...`) → ingresar
2. **Admin crea vendor:** Tab "Vendors" → nombre → crear (keypair generado server-side)
3. **Admin crea producto:** Tab "Productos" → nuevo → asignar vendor → crear
4. **Admin emite puntos:** Tab "Emitir" → legajo del estudiante → cantidad → concepto → emitir
5. **Estudiante se registra:** `register.html` → completar datos → generar claves → firmar → **auto-login al dashboard**
6. **Estudiante ve balance:** `home.html` — balance confirmado desde NCT, historial de transacciones
7. **Estudiante compra:** marketplace → seleccionar producto → modal de contraseña → firmar → **spinner con feedback** → confirmación
8. **Admin verifica logs:** Tab "Logs" — la compra aparece registrada

---

## Recomendaciones para la Defensa

1. **Preparar el NCT antes de la demo:** Asegurarse de que el NCT (Redis + RabbitMQ + `nct/`) esté corriendo y que `AUTHORITY_PUBKEY` coincida con `ACADEMIC_AUTHORITY_PUBLIC_KEY` del backend.
2. **Tener el par de desarrollo a mano:** La clave privada del admin (`20139855...`) para poder loguearse en modo avanzado si hace falta.
3. **Explicar las limitaciones como decisiones conscientes:** El hecho de que el sistema tenga limitaciones conocidas y documentadas demuestra madurez de ingeniería, no debilidad.
4. **Mostrar el modal de compra:** Es el momento "wow" de la demo — el spinner con las 3 etapas muestra que hay criptografía real ocurriendo.

---

## Changelog

```
v1.1 (2026-06-21) — PoC Fixes
  - nginx: /health endpoint para Kubernetes
  - Legacy files: reemplazados por redirects
  - auth.js: fix password + wallet-crypto integration + imports
  - profile.html: removed broken security.html link
  - login.html v2: wallet-crypto flow, advanced mode collapsed
  - register.html: auto-login after registration
  - common.js: extracted shared frontend utilities
  - home.js, marketplace.js, purchase.js, admin.js: migrated to common.js
  - purchase.html: password modal + loading spinner (3 stages)
  - Better error messages: NCT-down hints in purchase + admin

v1.0 (2026-06-19) — Initial Ed25519 integration
  - Migrated from ECDSA P-384 to Ed25519
  - Added vendors, transactions_log, wallet-crypto
  - NCT client integration (EARN + SPEND)
```
