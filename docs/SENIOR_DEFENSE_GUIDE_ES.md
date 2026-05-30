# Guía de defensa senior — Fleet Telemetry

Esta guía está escrita para explicar el proyecto en una entrevista técnica con confianza. Las respuestas están en primera persona porque deben sonar como propias.

---

## Explicación de 60 segundos

"Construí un sistema de monitoreo en tiempo real para una flota de 50 vehículos autónomos de almacén. El backend es FastAPI con PostgreSQL, el frontend es React con TypeScript. Los vehículos envían telemetría al backend, que detecta anomalías en tiempo real, lleva un conteo concurrentemente seguro de entradas por zona, y maneja transiciones a estado de falla de forma atómica — cancelando misiones activas y creando registros de mantenimiento en una sola transacción. El dashboard hace polling cada 2 segundos y muestra el estado de la flota, batería, anomalías y conteo de zonas."

---

## Explicación técnica de 3 minutos

"Empecé definiendo la estructura del proyecto antes de escribir una sola línea de lógica de negocio. Backend organizado por capas: API routes, schemas Pydantic, services, repositories, modelos ORM. Frontend separado en tipos, servicios de fetch, hooks y componentes. Esta estructura no es burocracia — me permitió auditar el output de la IA en piezas verificables y hacer que cada sesión de trabajo tuviera un scope acotado.

El flujo de ingestión de telemetría es el núcleo del sistema: `POST /api/telemetry` valida el payload con Pydantic (vehicle_id v-01..v-50, battery_pct 0-100, zone válida), persiste el evento, actualiza el snapshot del vehículo, evalúa 4 reglas de anomalía, y si hay zona incrementa el contador — todo en una sola transacción.

El conteo de zonas usa un upsert atómico en SQL: `INSERT ... ON CONFLICT DO UPDATE SET entry_count = entry_count + 1`. No hay read-modify-write en Python. Bajo 20 requests concurrentes al mismo zone, el conteo es exactamente 20. Lo verifiqué con `asyncio.gather`.

La transición a fault usa `SELECT FOR UPDATE` para bloquear la fila del vehículo, luego cancela todas las misiones activas y crea el maintenance record en la misma transacción. Un rollback deja todo sin cambios.

Usé PostgreSQL porque SQLite no tiene row-level locking real, y ese locking es necesario tanto para la fault transition como para el test de concurrencia. Usé polling de 2 segundos en vez de WebSockets porque con 50 vehículos a 1 Hz el lag es imperceptible, y los WebSockets añaden complejidad de reconexión y fanout que no se justifica a esta escala."

---

## Explicación profunda para un reviewer senior

"Hay tres decisiones de concurrencia en este proyecto que vale la pena discutir en detalle.

**Primera — el upsert atómico de zona:**
El enunciado del challenge pide que el conteo sea correcto bajo escrituras concurrentes. La solución naive sería: leer el contador, sumarle 1, escribirlo. Bajo concurrencia, dos transacciones pueden leer el mismo valor antes de que cualquiera escriba. El resultado pierde conteos.

La solución es delegar la atomicidad a PostgreSQL con una sola sentencia: `INSERT ON CONFLICT DO UPDATE SET entry_count = entry_count + 1`. PostgreSQL adquiere un row lock en el `ON CONFLICT DO UPDATE`, serializando los incrementos del mismo `zone_id`. No es necesario ningún lock explícito en la aplicación.

**Segunda — SELECT FOR UPDATE en fault transition:**
La fault transition requiere que tres cosas pasen juntas: vehicle.status = fault, missions.status = cancelled, un nuevo maintenance record. Sin locking, dos PATCH concurrentes para el mismo vehículo podrían crear dos maintenance records o dejar el vehículo con missions no canceladas.

`SELECT ... FOR UPDATE` adquiere un row-level lock en el vehículo específico. El segundo request bloquea hasta que el primero commitea. Después del commit, el segundo request ve el estado actualizado y puede proceder (o decidir no hacer nada si el vehículo ya está en fault).

**Tercera — la infraestructura de tests async:**
Este fue el problema más difícil. pytest-asyncio 0.24+ crea un loop por test por defecto. El pool de asyncpg guarda conexiones ligadas a ese loop. Cuando el siguiente test empieza con un loop nuevo, las conexiones cacheadas apuntan al loop anterior.

La solución tiene dos partes: NullPool en el engine de test (sin caching de conexiones), y un loop compartido para toda la sesión de tests. Adicionalmente, el fixture `db` no mantiene una sesión abierta durante el teardown — es una factory que abre sesiones cortas que se cierran dentro del scope del test. Esto elimina el 'Future attached to different loop' en teardown."

---

## Respuestas a preguntas concretas

### ¿Qué hace este proyecto?

Monitoreo en tiempo real de una flota de vehículos autónomos: ingestión de telemetría, detección de anomalías, conteo de zonas, transición atómica a fault, dashboard con polling.

### ¿Cómo abordaste el challenge?

Primero definí la estructura completa del proyecto. Luego implementé en capas: modelos → schemas → services → API → tests → frontend → documentación. Cada capa se revisó antes de pasar a la siguiente.

### ¿Por qué empezaste por la estructura?

Para poder auditar el output de la IA en pedazos pequeños. Si le pides a un LLM que construya todo en un solo prompt enorme, el output es difícil de verificar. Con capas separadas, cada session de trabajo tenía un scope claro y un output verificable.

### ¿Cómo te ayudó la IA y cómo controlaste su output?

Usé Claude Code para generar implementaciones completas en cada capa. El criterio técnico (qué implementar, en qué orden, con qué trade-offs) vino de mi decisión. La IA generó la implementación según especificaciones detalladas.

Lo que requirió corrección fue principalmente la infraestructura de tests async — cuatro rondas de debugging porque las interacciones entre pytest-asyncio, asyncpg y SQLAlchemy async son sutiles. El código de negocio (services, repositories, API) no requirió correcciones.

Lo que verifiqué manualmente: que el ADR describía correctamente los umbrales de anomalía (había una discrepancia con el código real), y el flujo de startup de Docker para documentarlo correctamente.

### ¿Por qué FastAPI?

Porque el proyecto es inherentemente async: 50 vehículos pueden enviar telemetría concurrentemente, y asyncpg permite que FastAPI maneje esos requests sin bloqueo. Con SQLAlchemy sync + threads, el overhead sería mayor. FastAPI también genera documentación Swagger automática, que ayuda en un take-home challenge.

### ¿Por qué PostgreSQL?

Por tres razones técnicas concretas:
1. Row-level locking (`SELECT FOR UPDATE`) para la fault transition.
2. Atomic upsert (`INSERT ON CONFLICT DO UPDATE`) para los contadores de zona.
3. Soporte nativo de asyncpg para el modelo async de FastAPI.

SQLite serializa todas las escrituras a través de un lock global, lo que haría que 50 vehículos concurrentes se queden en cola. Con PostgreSQL, cada vehículo tiene su propio lock de fila.

### ¿Por qué polling en vez de WebSockets?

Porque con 50 vehículos y un lag de 2 segundos, el sistema es perfectamente usable. Los datos cambian varias veces por segundo, así que cualquier snapshot de 2 segundos es razonablemente fresco. WebSockets añaden: reconexión en el cliente, fanout state en el servidor, complejidad de deployment. Para este escenario, el trade-off no se justifica.

El ADR documenta el punto de inflexión: 10,000+ vehículos o latencia sub-segundo.

### ¿Cómo garantizaste el conteo correcto de zonas con escrituras concurrentes?

Con un upsert atómico en PostgreSQL. La sentencia `INSERT ... ON CONFLICT DO UPDATE SET entry_count = entry_count + 1` es una sola operación. PostgreSQL adquiere un row lock durante el `DO UPDATE`, serializando los incrementos concurrentes para la misma zona. No hay read-modify-write en Python.

Lo verifiqué con un test que lanza 20 requests concurrentes via `asyncio.gather` y verifica que el contador sea exactamente 20.

### ¿Cómo manejaste la transición a fault de forma atómica?

`SELECT ... FOR UPDATE` en la fila del vehículo para adquirir el lock. Luego: cancel missions (UPDATE), create maintenance record (INSERT), update vehicle status (UPDATE). Un único `session.commit()` al final. Si cualquier paso falla, el rollback deja todo sin cambios.

### ¿Cómo definiste las anomalías?

Cuatro reglas hardcoded, evaluadas por cada evento de telemetría. Cada regla que dispara crea una fila en la tabla `anomalies`:

- `battery_pct < 15` → LOW_BATTERY
- `status == "fault"` → VEHICLE_FAULT
- `len(error_codes) > 0` → ERROR_CODE_REPORTED
- `speed_mps > 8.0` → HIGH_SPEED

Los umbrales son constantes en el código. En producción estarían en una tabla de configuración con historial de cambios.

### ¿Qué probaron los tests?

30 tests contra PostgreSQL real. Cuatro archivos:
- Ingestión de telemetría y actualización de estado del vehículo.
- Las 4 reglas de anomalía con valores límite exactos (15.0 y 8.0 no disparan).
- Conteo de zonas incluyendo el test de concurrencia (20 requests simultáneos).
- Fault transition: vehicle, mission, maintenance cambian juntos en una transacción.
- Fleet state aggregate con statuses mixtos y live update.

### ¿Cuál fue el problema más difícil?

La infraestructura de tests async. Los tests fallaban con "Future attached to a different loop" y "another operation is in progress" de formas que no eran obvias. Requirió cuatro rondas de debugging:

1. NullPool para evitar que asyncpg cachee conexiones entre loops.
2. Shared event loop para toda la sesión de tests.
3. Reemplazar drop_all/create_all con TRUNCATE (TRUNCATE es una sola sentencia, no DDL múltiple que compite).
4. Refactorizar el fixture `db` como factory de sesiones cortas en vez de sesión larga que sobrevive al teardown.

Cada fix era plausible individualmente pero exponía el siguiente problema. El patrón es: cuando tienes asyncio + asyncpg + SQLAlchemy + pytest, la cadena de interacciones entre librerías es larga, y los errores no indican directamente su causa raíz.

### ¿Qué cambiarías a mayor escala?

Para 10,000+ vehículos:

- **Kafka/Redpanda** entre el endpoint de ingestión y la escritura a DB. Desacopla el throughput HTTP del throughput de la DB.
- **WebSockets o SSE** en el frontend, con un gateway de fanout en el servidor.
- **Redis INCR** para los contadores de zona. Elimina la contención de fila en PostgreSQL bajo 10k eventos/segundo del mismo zone_id.
- **Particionamiento de la tabla `telemetry_events`** por rango de tiempo o hash de vehicle_id.
- **Read replicas** para separar las lecturas del dashboard de las escrituras de ingestión.
- **Job de retención** con TTL configurable para no crecer indefinidamente.

### ¿Qué dejaste fuera deliberadamente?

- **Autenticación:** fuera del scope del spec. Sería el primer ítem en un hardening pass.
- **Retención de telemetría:** la DB crece indefinidamente. No era requerido.
- **Renderizado geoespacial:** el spec pedía conteo de zonas, no un mapa. Un mapa requiere una librería de mapas.
- **Push alerts:** las anomalías se persisten y consultan. No hay webhooks.
- **Validación de coordenadas vs polígono de zona:** se asume que el cliente edge hace esa detección.

---

## Posibles preguntas de seguimiento

**"¿Por qué no usar `asyncio.Lock()` en Python para los contadores de zona?"**

Un Lock de asyncio protege la sección crítica en un solo proceso. Si hay múltiples instancias del backend (horizontal scaling), cada proceso tiene su propio lock y no protegen entre sí. El upsert atómico en PostgreSQL es el único punto de serialización que funciona independientemente del número de instancias del backend.

**"¿El `SELECT FOR UPDATE` no crea un cuello de botella?"**

Solo para el mismo vehículo. Si v-01 y v-02 hacen fault transition simultáneamente, sus locks son en filas diferentes y no se bloquean entre sí. El lock es de fila, no de tabla.

**"¿Qué pasa si la DB cae durante la fault transition?"**

Si la DB cae después del `SELECT FOR UPDATE` pero antes del `COMMIT`, PostgreSQL libera el lock cuando se rompe la conexión y la transacción hace rollback. El estado del vehículo no cambia. La llamada HTTP retorna un error de conexión. Es exactamente el comportamiento correcto.

**"¿Por qué no usar Celery o una task queue para la detección de anomalías?"**

Porque la detección es sincrónica con la ingestión. Si persisto el evento y la anomalía no se detecta (porque falló el worker de Celery), el sistema de monitoreo queda ciego. Al hacerlo en la misma transacción, el commit garantiza que si hay evento, hay anomalía evaluada. El costo es latencia extra por request, que con 50 vehículos es negligible.

**"¿Cómo escalarías el frontend?"**

Para este caso, el frontend es estático y puede servirse desde CDN (S3 + CloudFront o equivalente). El polling HTTP se puede manejar con load balancer estándar porque cada request es stateless. El único cambio sería pasar de polling a SSE/WebSocket si la latencia de 2 segundos dejara de ser aceptable.

**"¿Por qué `last-write-wins` para el estado del vehículo?"**

Porque el estado del vehículo en la tabla `vehicles` es un snapshot de conveniencia, no la fuente de verdad. La tabla `telemetry_events` tiene todos los eventos en orden. Si dos eventos de v-01 llegan simultáneamente, la convención de last-write-wins es correcta porque ambos eventos son válidos y el más reciente refleja el estado actual. El ordering temporal está en el campo `timestamp` del evento.

---

## Lo que más vale resaltar

1. **La decisión de empezar por la estructura.** Demuestra criterio de proceso, no solo conocimiento técnico.

2. **El upsert atómico para zonas.** Es la respuesta correcta al problema de concurrencia, no la respuesta obvia. La respuesta obvia sería un lock de aplicación o una transacción serializable — el upsert es más simple y más eficiente.

3. **La fault transition con SELECT FOR UPDATE.** Demuestra conocimiento de transacciones y locking a nivel de DB.

4. **El debugging de async tests.** Cuatro rondas de debugging con diagnóstico claro de causa raíz demuestra madurez técnica. No es "no funcionaba y lo arreglé" — es saber exactamente por qué falló cada fix.

5. **El uso honesto de IA.** El criterio técnico fue propio. La IA generó código según especificaciones detalladas. Los errores del output se detectaron y corrigieron. El resultado final es auditable.
