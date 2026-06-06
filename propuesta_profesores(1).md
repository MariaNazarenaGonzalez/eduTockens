# Propuesta de Caso de Uso
## Sistema de Puntos Académicos sobre Blockchain Distribuida

**TP Integrador — Blockchain Distribuida y CUDA**

---

## 1. Descripción del dominio

Se propone implementar un **sistema de puntos académicos** como caso de uso sobre la blockchain distribuida desarrollada en el trabajo integrador.

Los estudiantes acumulan puntos al completar actividades evaluativas y de participación. Esos puntos pueden ser gastados en servicios del campus: fotocopiadoras, máquinas expendedoras u otros proveedores habilitados por la institución.

El sistema registra de forma inmutable tanto la emisión como el gasto de puntos. Ningún actor puede alterar el historial retroactivamente ni gastar puntos que no posee.

---

## 2. Actores

| Actor | Rol en el sistema |
|---|---|
| **Sistema Académico** (`ACADEMIC_SYSTEM`) | Único emisor de puntos. Representa a la institución. |
| **Estudiante** (`student:{legajo}`) | Receptor de puntos y emisor de gastos. |
| **Proveedor** (`vendor:{id}`) | Receptor de gastos. Ej: `vendor:FOTOCOPIADORA`, `vendor:MAQUINA_A1`. |

Las transferencias de puntos entre estudiantes están fuera del alcance de esta propuesta. Los puntos son emitidos por mérito académico y solo pueden gastarse en proveedores habilitados.

---

## 3. Actividades que otorgan puntos

Las actividades están organizadas por frecuencia, lo que determina el volumen de transacciones que genera el sistema.

**Evaluaciones formales** (baja frecuencia, alto valor):

- Aprobación de parcial
- Entrega y aprobación de TP integrador
- Entrega de trabajos prácticos por unidad

**Actividades semanales** (frecuencia media):

- Entrega de ejercicios prácticos semanales
- Resolución de problemas en plataforma virtual
- Participación en foros (respuesta a consultas de compañeros)

**Actividades por clase** (alta frecuencia, bajo valor unitario):

- Registro de asistencia
- Participación oral registrada por el docente
- Quiz de inicio o cierre de clase

**Actividades por evento** (frecuencia variable):

- Asistencia a charlas o seminarios
- Participación en hackathons internos
- Corrección de pares (peer review)
- Exposición oral

Esta variedad de frecuencias es relevante para el Pilar 3: permite simular cargas realistas que combinan ráfagas de transacciones de bajo valor (asistencia diaria) con transacciones aisladas de alto valor (aprobación de parcial).

---

## 4. Tipos de transacción

El sistema define dos tipos de transacción:

**EARN** — emisión de puntos:

```
sender:   ACADEMIC_SYSTEM
receiver: student:{legajo}
amount:   puntos otorgados (positivo)
concept:  descripción de la actividad (ej: "PARCIAL1", "ASISTENCIA_2026-06-05")
```

**SPEND** — gasto de puntos:

```
sender:   student:{legajo}
receiver: vendor:{id}
amount:   puntos gastados (positivo)
concept:  descripción del servicio (ej: "FOTOCOPIADORA", "MAQUINA_A1")
```

---

## 5. Validaciones

### 5.1 Validaciones estructurales

Se aplican al recibir cada transacción, antes de ingresarla al sistema:

- El monto debe ser mayor a cero.
- El emisor y el receptor deben ser distintos.
- Para transacciones EARN: el emisor debe ser `ACADEMIC_SYSTEM` y el receptor debe ser un estudiante.
- Para transacciones SPEND: el emisor debe ser un estudiante y el receptor debe ser un proveedor.
- El campo `concept` no debe estar vacío.

### 5.2 Validación de saldo (prevención de doble gasto)

Para transacciones SPEND, el nodo coordinador (NCT) verifica que el estudiante posea saldo suficiente antes de incluir la transacción en un bloque.

Esta validación ocurre al momento de **armar el bloque**, no al recibir la transacción. El motivo es técnico: si la validación ocurriera al recibir el POST, dos solicitudes de gasto concurrentes del mismo estudiante podrían pasar la validación simultáneamente antes de que cualquiera de ellas se confirme en la cadena.

Al armar el bloque, el NCT procesa las transacciones en orden y mantiene un registro interno de los deltas acumulados por el bloque en curso. Esto permite detectar el doble gasto dentro del mismo bloque: si un estudiante tiene 100 puntos y hay dos SPENDs de 80 puntos cada uno en el pool, el primero se incluye y el segundo se descarta con registro en el log.

El saldo de cada estudiante se mantiene como índice derivado en Redis, actualizado cada vez que un bloque es confirmado. La cadena es la fuente de verdad; el índice es un caché de lectura rápida.

---

## 6. Flujos principales

### Emisión de puntos (EARN)

1. El sistema académico envía una transacción EARN al nodo coordinador.
2. El NCT valida la estructura y la ingresa al pool de transacciones pendientes.
3. Al acumularse suficientes transacciones, el NCT forma un bloque y publica la tarea de minado en RabbitMQ.
4. Los workers compiten para resolver el Proof of Work.
5. El primero en encontrar el nonce válido notifica al NCT.
6. El NCT verifica la solución, persiste el bloque en Redis y actualiza el índice de saldos.

### Gasto de puntos (SPEND)

Idéntico al flujo anterior, con la diferencia de que en el paso 3, el NCT verifica el saldo efectivo del estudiante antes de incluir la transacción en el bloque. Si el saldo es insuficiente, la transacción es descartada y registrada en el log.

### Consulta de saldo

El NCT expone un endpoint `GET /balance/{student_id}` que devuelve el saldo confirmado del estudiante consultando el índice en Redis.

---

## 7. Justificación de la blockchain como herramienta para este dominio

**Inmutabilidad del historial académico:** una vez que una emisión de puntos es minada en un bloque, no puede eliminarse ni modificarse sin invalidar todos los bloques posteriores. Esto garantiza que el registro de logros académicos es auditable sin depender de una autoridad centralizada.

**Prevención de doble gasto:** el problema central de este caso de uso es el mismo que resuelve Bitcoin: impedir que un actor gaste recursos que no posee o que ya gastó. La implementación de Proof of Work como mecanismo de consenso es la respuesta directa a este problema, con justificación teórica en el whitepaper de Nakamoto [NAK08].

**Descentralización del registro:** en una base de datos relacional tradicional, un administrador con acceso directo puede modificar el saldo de cualquier estudiante. En la blockchain, modificar un registro requiere rehacer el PoW de ese bloque y de todos los bloques posteriores, lo cual es computacionalmente inviable si la cadena tiene suficiente longitud.

---

## 8. Alineación con los pilares del TP

### Pilar 1 — Minero CUDA

El minero resuelve Proof of Work sobre el fingerprint de cada bloque. El dominio de puntos académicos no impone restricciones sobre el algoritmo de hash ni sobre el minero: el minero CUDA opera sin modificaciones respecto al diseño base.

### Pilar 2 — Infraestructura distribuida

- **NCT:** acumula transacciones del pool, valida saldos al armar bloques, publica tareas en RabbitMQ, verifica soluciones y persiste bloques en Redis.
- **RabbitMQ:** distribuye desafíos de PoW entre workers. Múltiples workers compiten para resolver el bloque que consolida las transacciones pendientes.
- **Redis:** persiste la cadena y el índice de saldos derivado.
- **Pool de transacciones (P5):** fragmenta el espacio de búsqueda del nonce entre workers. La alta frecuencia de transacciones de asistencia y participación motiva naturalmente la necesidad de workers paralelos para mantener tiempos de confirmación razonables.

### Pilar 3 — Despliegue, prueba y escalabilidad

Las pruebas de bulk del enunciado tienen correspondencia directa con el dominio:

- **Volumen de transacciones (1 a 100.000):** simula desde un grupo pequeño hasta una institución completa durante un período académico.
- **Variación de dificultad (1 a 8 caracteres de prefijo):** evalúa el impacto en el tiempo de confirmación de bloques con distintos niveles de seguridad.
- **Tamaño de fragmentación del pool:** determina cuántos workers son necesarios para mantener el throughput bajo carga de asistencia diaria.
- **Ingreso y egreso de nodos GPU:** simula escenarios donde la carga de transacciones aumenta (inicio de cuatrimestre, período de parciales) y la red debe escalar horizontalmente.

El perfil de carga es heterogéneo: muchas transacciones EARN de bajo valor (asistencia diaria) combinadas con pocas transacciones de alto valor (aprobación de parcial) y SPENDs esporádicos. Este patrón es más representativo de un sistema real que un bulk homogéneo y genera comportamientos observables más interesantes en las gráficas del informe.

---

## 9. Alcance y limitaciones conocidas

**Dentro del alcance:**

- Emisión de puntos por el sistema académico.
- Gasto de puntos en proveedores habilitados.
- Prevención de doble gasto por validación de saldo en el NCT.
- Consulta de saldo confirmado por estudiante.
- Auditoría completa de la cadena.

**Fuera del alcance (decisiones de diseño):**

- Transferencias de puntos entre estudiantes.
- Registro y validación de proveedores habilitados (cualquier string `vendor:*` es aceptado).
- Autenticación criptográfica del emisor: cualquier actor puede enviar una transacción EARN con `sender = "ACADEMIC_SYSTEM"`. En producción, esto requeriría firma ECDSA por transacción. Para el TP, se documenta como limitación de seguridad conocida y se menciona la solución correcta en el informe.
- Expiración de puntos.

---

## 10. Referencias

- **[NAK08]** Nakamoto, S. (2008). *Bitcoin: A Peer-to-Peer Electronic Cash System*. https://bitcoin.org/bitcoin.pdf
- **[ANT17]** Antonopoulos, A. M. (2017). *Mastering Bitcoin* (2nd ed.). O'Reilly Media.
- **[POW]** Proof of Work — Bit2Me Academy. https://academy.bit2me.com/que-es-proof-of-work-pow/
- **[MSRBTC]** Bitcoin Transaction Processing — Microsoft Research. https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bitcoin.pdf
