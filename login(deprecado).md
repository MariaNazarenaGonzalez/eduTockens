# Login y registro con clave publica

Este proyecto reemplaza el login por contraseña por un flujo de desafio firmado.
El backend guarda la clave publica del usuario y verifica que el navegador pueda
firmar el desafio actual con la clave privada correspondiente.

## Flujo de registro

1. El usuario completa legajo, nombre y email.
2. El navegador puede generar un par de claves ECDSA P-384, o el usuario puede pegar una clave publica PEM generada externamente.
3. El frontend solicita `GET /api/auth/challenge`.
4. El sistema devuelve un desafio con fecha, hora y minuto actual del servidor: `YYYY-MM-DD HH:MM`.
5. El usuario firma ese texto con su clave privada.
6. El frontend envia a `POST /api/auth/register`:

```json
{
  "legajo": "12345678",
  "name": "Nombre Apellido",
  "email": "usuario@example.com",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----...",
  "challenge": "2026-06-16 14:35",
  "signature": "3064..."
}
```

El backend valida la firma antes de crear el usuario. Asi confirma que la clave publica registrada corresponde a la clave privada usada por el usuario.

## Flujo de login

1. El usuario ingresa legajo o email.
2. El frontend solicita `GET /api/auth/challenge`.
3. El usuario pega una firma hexadecimal del desafio, o pega su clave privada en el apartado opcional para firmar desde el navegador.
4. El frontend envia a `POST /api/auth/login`:

```json
{
  "identifier": "12345678",
  "challenge": "2026-06-16 14:35",
  "signature": "3064..."
}
```

5. El backend busca la clave publica guardada para ese usuario, verifica la firma ECDSA y, si es valida, emite el JWT usado por el resto del sistema.

## Criptografia usada

- Algoritmo de clave: ECDSA
- Curva: P-384
- Hash de firma: SHA-1, para mantener compatibilidad con el ejemplo original
- Formato de clave publica: PEM `SubjectPublicKeyInfo`
- Formato de clave privada opcional en frontend: PEM `PKCS8`
- Formato de firma enviado al backend: ASN.1 DER codificado en hexadecimal

El frontend usa WebCrypto para generar claves, importar la clave privada PKCS8 y firmar el desafio. WebCrypto devuelve la firma ECDSA en formato crudo `r || s`; por compatibilidad con el backend se transforma a DER hexadecimal antes de enviar.

## Desafio

El desafio no se persiste en base de datos. Se deriva del reloj del servidor con precision de minuto (`YYYY-MM-DD HH:MM`) y el backend acepta el minuto actual, el anterior y el siguiente para tolerar pequeños desfasajes durante el envio.

## Admin de desarrollo

El `db/init.sql` crea un usuario administrador con clave publica de desarrollo. Para ingresar como admin en un entorno recien inicializado, firmar el desafio con esta clave privada de desarrollo:

```pem
-----BEGIN PRIVATE KEY-----
MIG2AgEAMBAGByqGSM49AgEGBSuBBAAiBIGeMIGbAgEBBDDYFYpEjkxrbcVa3beu
hIGItwEm3y2ZCpgbdIQB0nsPwPzns4VGbBpxXlGFQvw76kmhZANiAATVYyzz6Iub
TcbwVPB05ZV63YaC0ka5UjHNDBE7wZmq3fBRSY6QPFE2tZFgF0CXL7hICnzsIFl4
Ey1+4YlBnwYRttftcZOH4ika9pNYAEnD5H4tFK1Ei+iei5Q37s9i7SU=
-----END PRIVATE KEY-----
```

Esta clave es solo para desarrollo local y debe reemplazarse en cualquier entorno compartido o productivo.
