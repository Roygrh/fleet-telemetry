# AI Interaction Log Extended ES

Registro extendido y detallado del uso de IA durante el desarrollo del proyecto `fleet-telemetry`.

Este documento complementa —no reemplaza— a `docs/AI_LOG.md`. El log original sigue siendo válido como resumen de la ejecución en Claude Code, pero muchos de sus prompts aparecen comprimidos a dos o tres líneas. Este archivo reconstruye el proceso real de desarrollo asistido por IA con mayor precisión, usando como fuente principal las versiones finales de los prompts en `PROMPTS_USED.md` (raíz del proyecto) y los resúmenes de ejecución de `docs/AI_LOG.md`.

> Fuentes utilizadas:
> - `PROMPTS_USED.md` (raíz del proyecto): fuente principal de las versiones finales y detalladas de los prompts, refinados antes de enviarse a Claude Code.
> - `docs/AI_LOG.md`: resumen original de la ejecución en Claude Code, con salidas, correcciones y reflexión.
>
> Donde un dato no pudo confirmarse directamente desde estos archivos, se indica explícitamente que fue reconstruido a partir de los logs disponibles y del contexto de la conversación de trabajo.

---

## Visión general

- El challenge permitía e incentivaba el desarrollo asistido por IA. El uso de IA no se ocultó: se documentó de forma trazable.
- El proyecto se desarrolló con un flujo de dos herramientas: **ChatGPT** para planificación, diseño de arquitectura y refinamiento de prompts, y **Claude Code** para implementación, generación de archivos, ejecución de comandos y reporte de resultados.
- El trabajo se dividió **intencionalmente** en etapas pequeñas y controladas, en lugar de pedir la solución completa en un único prompt grande. Cada prompt cubría una capa o una corrección puntual.
- Cada etapa se validó antes de avanzar: Docker Compose, migraciones de Alembic, script de seed, peticiones con `curl`, `pytest` y revisión manual del frontend en el navegador.
- El resultado no fue "código generado automáticamente". Fue un proceso de ingeniería **guiado, revisado, validado y corregido** con criterio senior. La IA actuó como acelerador; las decisiones de arquitectura, la identificación de riesgos y la validación fueron humanas.

---

## Metodología

El método de trabajo siguió siempre el mismo ciclo:

1. **Entender los requerimientos** del challenge (a partir del `README.md` original).
2. **Definir la estructura del proyecto** antes de escribir lógica de negocio.
3. **Dividir la implementación en fases controladas** (estructura → base de datos → servicios/endpoints → tests → frontend → documentación).
4. **Usar Claude Code para una etapa específica por vez**, con un prompt acotado y reglas explícitas de "no hagas X".
5. **Validar cada etapa** con comandos reales antes de pasar a la siguiente.
6. **Usar los errores como retroalimentación** para escribir el siguiente prompt: cada error de ejecución o de tests se convirtió en un prompt de corrección puntual, no en una reescritura amplia.
7. **Documentar** decisiones, supuestos, uso de IA y correcciones a medida que ocurrían.

### Por qué este enfoque fue una decisión senior

- **Redujo el riesgo:** un fallo quedaba contenido en una capa, no contaminaba todo el proyecto.
- **Hizo más fácil revisar el output de la IA:** un diff pequeño es auditable; un diff de todo el proyecto no lo es.
- **Mantuvo la arquitectura intencional:** la separación services/repositories, el contrato `/api`, la estrategia de concurrencia, etc., se decidieron antes de pedir código, no como subproducto del modelo.
- **Evitó una solución monolítica difícil de auditar:** pedir "construye toda la app" habría producido código plausible pero opaco.
- **Permitió avanzar rápido dentro de la restricción de tiempo** típica de un challenge de 48 horas, sin sacrificar control.

---

## Alcance del challenge y restricción de tiempo

Este fue un **take-home challenge con una ventana de tiempo limitada**. La solución se enfocó deliberadamente en entregar una **vertical funcional completa y confiable**, no una plataforma de producción.

Se priorizó:

- una vertical funcional completa (ingesta → detección → persistencia → dashboard);
- arquitectura clara y legible;
- lógica crítica de backend confiable;
- persistencia con PostgreSQL;
- contador de zonas seguro ante concurrencia;
- transición atómica a estado `fault`;
- pruebas automatizadas del backend;
- dashboard en vivo mediante polling;
- ADR y registro de uso de IA.

**No se sobreconstruyó** lo que no correspondía a un challenge local y reproducible. Las siguientes ausencias fueron **trade-offs deliberados, no falta de conocimiento**:

- autenticación;
- autorización por roles;
- despliegue en la nube;
- Kubernetes;
- message broker;
- pipeline CI/CD;
- pruebas automatizadas del frontend;
- política de retención de telemetría;
- stack completo de observabilidad;
- gestor de secretos de producción.

Más abajo, en *Trade-offs y consideraciones de producción*, se explica qué cambiaría cada uno de estos puntos en un escenario real.

---

## Sesiones

Las sesiones siguen el orden cronológico real del desarrollo. Para cada una se usa la versión final del prompt según `PROMPTS_USED.md`. No se duplican prompts casi idénticos: cuando un prompt fue reemplazado por una versión mejor dividida, se documenta solo la versión final útil y se indica que el trabajo se dividió de forma intencional.

### Sesión 1 - Estructura inicial del proyecto

**Fuente de planificación:** Planificación con ChatGPT. La estructura de carpetas, el stack y las reglas ("no crear otra carpeta `fleet-telemetry`", "no sobrescribir `README.md`", "no implementar lógica todavía") se prepararon antes de tocar Claude Code.

**Resumen del prompt:** Leer `README.md` solo como contexto y crear únicamente la estructura inicial del proyecto fullstack (FastAPI + SQLAlchemy + PostgreSQL + Alembic en backend; React + TypeScript + Vite en frontend; Docker Compose; `docs/ADR.md` y `docs/AI_LOG.md`). Se entregó el árbol completo de carpetas y archivos. Reglas explícitas: solo boilerplate mínimo en los archivos de configuración, archivos Python de `api/models/schemas/services/repositories` vacíos o con docstrings que expliquen el patrón Controller-Service-Repository, constante `ZONES` hardcodeada, y Docker Compose con `backend`, `frontend` y `postgres`.

**Por qué el prompt se estructuró así:** Empezar por la estructura fija el esqueleto y el contrato del proyecto antes de cualquier lógica. Definir el patrón Controller-Service-Repository desde el inicio obliga a que la lógica posterior caiga en la capa correcta. Pedir solo boilerplate evita que el modelo "adivine" lógica de negocio prematuramente.

**Salida de Claude Code:** Creó todo el scaffold en una sola pasada: `docker-compose.yml`, `.env.example`, `Dockerfile` del backend, `requirements.txt`, setup de Alembic, esqueleto de la app FastAPI, y el shell de React/Vite/TypeScript. Respetó la restricción de no sobrescribir `README.md` y dejó los archivos de lógica vacíos con docstrings.

**Validación realizada:** Revisión del árbol de carpetas generado y verificación de que los archivos de configuración fueran coherentes con el stack.

**Correcciones o problemas:** Ninguno en esta etapa.

**Resultado final:** Estructura base completa y limpia, lista para implementar capa por capa.

---

### Sesión 2 - Base de datos del backend

**Fuente de planificación:** Planificación con ChatGPT. El modelo de datos (seis entidades), las reglas de validación de Pydantic y la decisión de escribir la migración inicial a mano se definieron antes de ejecutar.

**Resumen del prompt:** Implementar solo la base de datos del backend: modelos SQLAlchemy 2.x (`Vehicle`, `TelemetryEvent`, `ZoneCounter`, `Anomaly`, `Mission`, `MaintenanceRecord`) con campos, relaciones, índices y constraints; schemas Pydantic de request/response para todos los endpoints con validaciones (`vehicle_id` con formato `v-01`..`v-50`, `status` válidos, `battery_pct` entre 0 y 100, `zone_entered` null o dentro de las zonas hardcodeadas); configuración de Alembic y migración inicial para PostgreSQL async; y un seed idempotente para 50 vehículos y 20 zonas. Sin servicios ni endpoints todavía.

**Por qué el prompt se estructuró así:** El backend se dividió deliberadamente en *base de datos → servicios → endpoints → tests*. Construir primero el modelo de datos y los schemas fija el contrato de persistencia y de validación antes de escribir lógica de negocio. Pedir la migración inicial a mano (sin autogeneración contra una DB viva) da control total sobre el orden de creación de tipos enum y tablas.

**Salida de Claude Code:**
- `app/models/enums.py` con los enums compartidos (`VehicleStatus`, `MissionStatus`, `MaintenanceStatus`).
- Seis archivos de modelos con estilo `Mapped`/`mapped_column`, FKs, índices y relaciones.
- Cinco archivos de schemas con `field_validator` para formato de `vehicle_id`, whitelist de zonas y rango de `battery_pct`.
- `alembic/versions/0001_initial_schema.py` escrita a mano (enums primero, luego tablas en orden de dependencia de FK).
- `seed.py` idempotente vía `ON CONFLICT DO NOTHING`.

Decisiones técnicas: las tablas hijas referencian `vehicles.vehicle_id` (string) en lugar del PK entero, para evitar un lookup en cada ingesta; `create_type=False` en el enum `vehiclestatus` dentro de `TelemetryEvent` para evitar doble creación del tipo en PostgreSQL; `entry_count` como `Integer` (suficiente para la escala del prototipo).

**Validación realizada:** Revisión del modelo de datos y de las validaciones. La ejecución real de la migración se validó en la sesión siguiente.

**Correcciones o problemas:** En la ejecución posterior la migración falló por duplicación de enums (ver Sesión 3).

**Resultado final:** Modelos, schemas, migración inicial y seed implementados.

---

### Sesión 3 - Corrección de enums duplicados en Alembic

**Fuente de planificación:** Corrección tras un error de ejecución. El prompt nació de un error real al correr la migración, no de planificación previa.

**Resumen del prompt:** La migración falló con `DuplicateObjectError: type "vehiclestatus" already exists`. La migración creaba los tipos enum de PostgreSQL explícitamente, pero las tablas intentaban crearlos de nuevo. Corregir `0001_initial_schema.py` para que cada tipo enum se cree una sola vez, aplicando `create_type=False` donde corresponda en `sa.Enum` dentro de `op.create_table`, para `VehicleStatus`, `MissionStatus` y `MaintenanceStatus`. Sin cambiar lógica de negocio.

**Por qué el prompt se estructuró así:** Es un prompt puntual de corrección dirigido exactamente al archivo y al síntoma. Mantener el alcance mínimo evita que el modelo "arregle" cosas no relacionadas y mantiene el diff auditable.

**Salida de Claude Code:** Ajustó la migración para que el enum se cree una sola vez (la primera tabla crea el tipo; las referencias posteriores usan `create_type=False`).

**Validación realizada:** Re-ejecución de `alembic upgrade` hasta aplicar la migración sin error.

**Correcciones o problemas:** El problema raíz —enums de PostgreSQL creados dos veces— es un patrón conocido de las migraciones generadas/asistidas por IA y exige revisión humana.

**Resultado final:** Migración inicial aplicándose correctamente sobre PostgreSQL.

---

### Sesión 4 - Servicios y endpoints del backend

**Fuente de planificación:** Planificación con ChatGPT, con ajuste fino. Las reglas de anomalías, la estrategia atómica de zonas y la transacción de `fault` se definieron antes de pedir el código. En `PROMPTS_USED.md` esta etapa figura como "encontrada parcialmente" en el log, por lo que el detalle se complementó con la conversación de trabajo.

**Resumen del prompt:** Implementar la lógica de servicios y los endpoints, con la lógica de negocio en `services` y el acceso a datos en `repositories`, todas las rutas bajo `/api`. Endpoints: `POST /api/telemetry` (ingesta + detección de anomalías + incremento de zona); `GET /api/zones/counts` (contadores atómicos para las 20 zonas, sin read-modify-write en Python, usando `INSERT ... ON CONFLICT DO UPDATE`); `GET /api/vehicles` y `PATCH /api/vehicles/{id}/status` con transición a `fault` (lock de fila, cancelación de misión activa, creación de registro de mantenimiento, todo en una transacción con rollback); `GET /api/fleet/state` (conteo por estado con `GROUP BY`); `GET /api/anomalies` (con filtros). Reglas de anomalía: `battery_pct < 15` → LOW_BATTERY, `status == fault` → VEHICLE_FAULT, `error_codes` no vacío → ERROR_CODE_REPORTED, `speed_mps > 8` → HIGH_SPEED. Sin auth ni websockets.

**Por qué el prompt se estructuró así:** Separar `services` (orquestación y reglas) de `repositories` (acceso a datos) mantiene la lógica testeable y el acceso a datos reutilizable. Exigir contadores atómicos por SQL (no read-modify-write) es una decisión de correctitud bajo concurrencia tomada de antemano, no delegada al modelo. Forzar `/api` desde el inicio alinea el contrato con el proxy de Vite.

**Salida de Claude Code:**
- 6 repositorios (wrappers async finos, sin lógica de negocio).
- 5 servicios (toda la orquestación y reglas).
- 5 routers (controladores finos, una llamada a servicio por endpoint).
- `main.py` actualizado para montar todos los routers bajo `/api`.

Detalles: incremento de zona con `INSERT ... ON CONFLICT DO UPDATE SET entry_count = entry_count + 1` (serializado por PostgreSQL); `fault` con `SELECT ... FOR UPDATE` y cancelación de misiones + registro de mantenimiento en la misma transacción; detección con cuatro reglas por evento; `fleet/state` con un solo `GROUP BY`; `session.flush()` tras el INSERT de telemetría para disponer del PK al crear la `Anomaly`.

**Validación realizada:** Peticiones `curl` a cada endpoint y verificación del comportamiento (ingesta, anomalías, contadores, transición a `fault`, agregado de flota).

**Correcciones o problemas:** Ninguno en esta etapa. (Supuesto: la ingesta actualiza el estado del vehículo con last-write-wins; la tabla de telemetría es la fuente de verdad y el estado del vehículo es una caché.)

**Resultado final:** Backend funcional completo a nivel de API.

---

### Sesión 5 - Tests del backend

**Fuente de planificación:** Planificación con ChatGPT. La decisión clave —probar contra una base de datos PostgreSQL real en lugar de mocks— se tomó antes de escribir los tests, porque la prueba de concurrencia de zonas exige semántica atómica real de PostgreSQL.

**Resumen del prompt:** Agregar tests de backend para: creación de evento de telemetría + actualización del estado del vehículo; las cuatro reglas de anomalía con casos límite; incremento del contador de zona, incluyendo incrementos concurrentes para la misma zona (el conteo final debe igualar el número de eventos); transición a `fault` atómica (vehículo + misión + mantenimiento); agregación de `fleet/state`. Usar `pytest` + `pytest-asyncio`, `httpx AsyncClient`, y preferir una base de datos de test real.

**Por qué el prompt se estructuró así:** Los tests de backend se priorizaron sobre los de frontend porque ahí vive la lógica crítica (concurrencia, atomicidad, reglas de negocio). Usar PostgreSQL real (no SQLite, no mocks) es la única forma de validar de verdad el contador atómico y `SELECT FOR UPDATE`.

**Salida de Claude Code:**
- `pytest.ini` (`asyncio_mode = auto`).
- `tests/conftest.py` con fixtures compartidas (`reset_db` autouse con drop/create por test, `client` con `ASGITransport` y override de `get_db`, `db` para aserciones).
- `test_telemetry.py` (12 tests), `test_zones.py` (5, incluyendo concurrencia con `asyncio.gather` y 20 POSTs simultáneos), `test_vehicles.py` (8, con atomicidad), `test_fleet.py` (4).

**Validación realizada:** Ejecución de `pytest`. Se probaron casos límite explícitos (batería == 15.0 no marca; velocidad == 8.0 no marca).

**Correcciones o problemas:** El enfoque inicial de `drop_all`/`create_all` por test resultó inestable con asyncpg y disparó una cadena de problemas async (Sesiones 6 a 9). La lógica de negocio era correcta; los fallos fueron de infraestructura de tests.

**Resultado final:** Suite de tests escrita; estabilización del runtime async pendiente.

---

### Sesión 6 - Corrección del setup async de tests con NullPool y TEST_DATABASE_URL

**Fuente de planificación:** Corrección tras un error de ejecución de pruebas. (En `PROMPTS_USED.md` esta etapa figura como "faltante o no completa" en el log; el prompt corresponde a la versión final acordada.)

**Resumen del prompt:** Solo el primer test pasa; el resto falla en `reset_db` con `RuntimeError: got Future attached to a different loop` y `asyncpg ... another operation is in progress`. Corregir solo la infraestructura de tests en `conftest.py`: evitar reusar conexiones asyncpg entre event loops, usar `NullPool`, asegurar cierre de cada `AsyncSession`, conservar soporte de `TEST_DATABASE_URL` con default para Docker (`postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test`), y fijar el loop scope en `pytest.ini`. Sin tocar lógica de negocio ni endpoints.

**Por qué el prompt se estructuró así:** La regla "no cambiar lógica de negocio, corregir solo la infraestructura" es una decisión senior: el fallo era del ciclo de vida de conexiones, no de la lógica. Acotar el alcance impide que el modelo enmascare el problema cambiando el código bajo prueba.

**Salida de Claude Code:**
- `pytest.ini`: `asyncio_default_fixture_loop_scope = session` (un único event loop para toda la sesión).
- `conftest.py`: `poolclass=NullPool` y default de `TEST_DATABASE_URL` con host `postgres`.

Causa raíz: pytest-asyncio creaba un loop por test; el pool de asyncpg cacheaba conexiones ligadas al loop del primer test. `NullPool` + loop de sesión eliminan esa reutilización entre loops.

**Validación realizada:** Re-ejecución de `pytest`.

**Correcciones o problemas:** `NullPool` por sí solo fue **insuficiente**. El error "another operation is in progress" persistía porque `drop_all` emite múltiples DDL sobre la misma conexión mientras asyncpg considera una sentencia previa aún en vuelo. Esto motivó la Sesión 7.

**Resultado final:** Avance parcial; conexiones ya no cruzan loops, pero `drop_all`/`create_all` seguía siendo inestable.

---

### Sesión 7 - Corrección de limpieza de tests con TRUNCATE

**Fuente de planificación:** Corrección tras error de pruebas, encadenada con la sesión anterior.

**Resumen del prompt:** Los tests siguen fallando en `reset_db` durante `await conn.run_sync(Base.metadata.drop_all)` con `asyncpg ... another operation is in progress`. El enfoque de `drop_all`/`create_all` por test es inestable con asyncpg. Refactorizar `conftest.py` para crear el schema una sola vez por sesión y, antes de cada test, limpiar datos con `TRUNCATE ... RESTART IDENTITY CASCADE` en lugar de drop/create. Sembrar la base requerida antes de cada test (vehículos `v-01`..`v-50` y contadores de todas las zonas). Conservar `NullPool` y `TEST_DATABASE_URL`. Sin tocar endpoints ni servicios.

**Por qué el prompt se estructuró así:** `TRUNCATE` es una única sentencia atómica por conexión, sin posibilidad de interleaving a nivel de driver, a diferencia de los múltiples DDL de `drop_all`. Crear el schema una sola vez por sesión separa el coste de DDL de la limpieza de datos por test. La corrección sigue siendo puntual y limitada a la infraestructura.

**Salida de Claude Code:** Reemplazó el `drop_all`/`create_all` por test por creación de schema de alcance de sesión y `TRUNCATE ... RESTART IDENTITY CASCADE` por test; cada módulo siembra sus filas necesarias sobre las tablas recién vaciadas.

**Validación realizada:** Re-ejecución de `pytest`.

**Correcciones o problemas:** Estabilizó la limpieza, pero apareció un nuevo síntoma en el *teardown* del fixture `db` al cerrar/rollback de la `AsyncSession` (Sesión 8).

**Resultado final:** Limpieza de datos estable; pendiente el ciclo de vida de la sesión de aserciones.

---

### Sesión 8 - Corrección del teardown de AsyncSession

**Fuente de planificación:** Corrección tras error de pruebas.

**Resumen del prompt:** Ahora muchos errores ocurren en el teardown del fixture `db`: `RuntimeError: got Future attached to a different loop` en `async with _TestSession() as session`, al cerrar la sesión e intentar rollback. Corregir solo `conftest.py` (y `pytest.ini` si es necesario): hacer que pytest-asyncio use un loop consistente para tests y fixtures async (loop scope `session` para ambos), refactorizar el fixture `db` para evitar `async with` si causa problemas de teardown, usar creación y cierre explícitos (`try/finally` con `rollback()` + `close()`), y asegurar que el `client` cierre en el mismo loop. Conservar `NullPool`, el enfoque `TRUNCATE` y el default de `TEST_DATABASE_URL`.

**Por qué el prompt se estructuró así:** El problema se había desplazado del *setup* al *teardown*: el `async with` cerraba la sesión en un contexto de loop inconsistente. Cambiar a cierre explícito da control sobre cuándo y en qué loop se libera la conexión.

**Salida de Claude Code:** Sustituyó el `async with` del fixture `db` por creación explícita con `try/finally` (rollback + close), y alineó el cierre del `client` en el mismo loop.

**Validación realizada:** Re-ejecución de `pytest`.

**Correcciones o problemas:** Mejoró, pero el rollback durante el teardown de una sesión de larga vida seguía disparando el error de loop en algunos casos. Esto llevó a la solución definitiva (Sesión 9).

**Resultado final:** Teardown más estable, pero aún dependiente de una `AsyncSession` de larga vida.

---

### Sesión 9 - Fixture de base de datos como factory de sesiones cortas

**Fuente de planificación:** Corrección reconstruida desde la conversación de trabajo. (En `PROMPTS_USED.md` esta etapa se marca explícitamente como reconstruida.)

**Resumen del prompt:** Los tests aún fallan en el teardown del fixture `db` (`got Future attached to a different loop` en `await session.rollback()`), con logs de "event loop is closed" al cerrar conexiones asyncpg. Evitar mantener una `AsyncSession` de larga vida durante todo el test. Refactorizar el fixture para que no entregue una sesión persistente que requiera rollback en teardown; preferir un factory que abra una sesión corta por query/aserción y la cierre de inmediato. Actualizar los tests que esperaban `db: AsyncSession`. Conservar `TRUNCATE`, `NullPool` y el default de `TEST_DATABASE_URL`; eliminar el rollback innecesario en teardown.

**Por qué el prompt se estructuró así:** Es la corrección de raíz: en vez de pelear con el ciclo de vida de una sesión larga, se elimina la sesión larga. Una factory de sesiones cortas garantiza que cada conexión se abra y cierre dentro del mismo loop, sin rollback diferido. Que las correcciones de tests fueran prompts puntuales encadenados (no una reescritura amplia) permitió aislar cada causa de forma incremental.

**Salida de Claude Code:** Convirtió `db` en un factory de sesiones de corta vida (abrir/cerrar por query) y ajustó los archivos de test que consumían `db: AsyncSession`.

**Validación realizada:** Ejecución completa de `pytest`: **30 tests pasando**.

**Correcciones o problemas:** Esta fue la última de las cuatro rondas de corrección async (Sesiones 6–9). Lección: gran parte de los errores en tests async provienen del ciclo de vida de conexiones y sesiones, no de la lógica de negocio.

**Resultado final:** Infraestructura de tests estable y determinista; suite verde.

---

### Sesión 10 - Capa de integración API del frontend

**Fuente de planificación:** Planificación con ChatGPT. La separación en capas (types → service → hooks → App de prueba) y la decisión de no construir aún el dashboard se definieron antes de implementar.

**Resumen del prompt:** Implementar la capa de integración API del frontend: tipos TypeScript que reflejen los schemas del backend (`Vehicle`, `VehicleStatus`, `Anomaly`, `FleetState`, `ZoneCount`, `ZoneCountResponse`); `services/api.ts` con `fetch` (sin librerías extra, rutas relativas `/api`, manejo claro de errores HTTP); hooks `usePolling` y `useFleetData` (polling cada 2 s, estados loading/error/data, sin fugas de memoria); y actualizar `App.tsx` solo lo suficiente para demostrar que los datos cargan. No construir aún el dashboard final.

**Por qué el prompt se estructuró así:** El frontend se dividió deliberadamente en *capa de integración API → dashboard visual*. Construir primero los tipos, el service y los hooks fija el contrato con el backend y aísla la lógica de datos de la presentación. Pedir un `App.tsx` mínimo de prueba permite validar la integración antes de invertir en UI.

**Salida de Claude Code:**
- `types/index.ts` con interfaces alineadas a los schemas del backend (incluyendo el envelope `{ zones: ZoneCount[] }`).
- `services/api.ts` con cuatro wrappers tipados de `fetch` y un helper `apiFetch<T>` que lanza en respuestas no-ok.
- `hooks/usePolling.ts` con patrón `useRef` para no reprogramar el intervalo al cambiar la identidad del callback.
- `hooks/useFleetData.ts` que dispara las cuatro fetches en paralelo con `Promise.all`.
- `App.tsx` cableado para mostrar loading/error, conteo de vehículos y JSON de fleet/zonas.
- `vite.config.ts` con corrección del proxy (ver abajo).

**Validación realizada:** Revisión en navegador de que los datos cargan y se actualizan; verificación de que las llamadas llegan al backend.

**Correcciones o problemas:** **Bug del proxy de Vite.** El `vite.config.ts` original tenía un `rewrite` que quitaba `/api` antes de reenviar a `http://backend:8000`, pero el backend expone todo bajo `/api/*`, produciendo 404. Se eliminó el `rewrite` para preservar el prefijo. Lección: el contrato de rutas entre frontend y backend debe verificarse, no asumirse.

**Resultado final:** Capa de datos del frontend funcional, consumiendo el backend real vía polling.

---

### Sesión 11 - Dashboard UI del frontend

**Fuente de planificación:** Planificación con ChatGPT, sobre la capa de integración ya existente.

**Resumen del prompt:** Construir el dashboard React usando la capa de integración ya implementada. Componentes: `FleetSummary`, `VehicleTable` (o tarjetas), `ZoneCounts`, `AnomalyBadge`, `StatusBadge`, `ErrorState`, `LoadingState`. Mostrar el agregado de flota, los 50 vehículos con estado/batería/last_seen/última anomalía (batería null como "No data yet", ordenados por `vehicle_id`), y los contadores de zona (zonas de carga destacadas). Polling cada 2 s con timestamp de "última actualización". Manejar loading/error/empty/normal. CSS plano, sin librería de UI.

**Por qué el prompt se estructuró así:** Es la segunda mitad de la división del frontend: la UI se construye solo después de que la capa de datos está validada, de modo que el dashboard consume un contrato ya probado. Acotar a CSS plano evita dependencias innecesarias en un challenge.

**Salida de Claude Code:**
- `App.css` (stylesheet completo: variables CSS, grid de resumen, tabla con headers sticky, colores de badges, spinner, breakpoints responsive).
- Componentes `LoadingState`, `ErrorState`, `StatusBadge`, `AnomalyBadge`, `FleetSummary`, `VehicleTable`, `ZoneCounts`.
- `useFleetData.ts` ampliado con `lastUpdated: Date | null`.
- `App.tsx` que compone todo: loading → `LoadingState`; error de primera carga → `ErrorState`; estado normal → dashboard con banner de error en línea para fallos de polling posteriores (los datos stale permanecen visibles).

Decisiones: el error de primera carga reemplaza la página; los errores de polling posteriores muestran un banner sobre datos stale (el usuario ve el último estado conocido mientras el backend se recupera). `latest_anomaly` viene directo de `VehicleResponse`, sin join en cliente. Umbral de batería en rojo < 15 % (coincide con la regla LOW_BATTERY).

**Validación realizada:** Revisión en navegador del dashboard con los 50 vehículos, y **validación del polling cada 2 s** (timestamp de última actualización cambiando, datos refrescándose).

**Correcciones o problemas:** Ninguno relevante en esta etapa.

**Resultado final:** Dashboard en vivo completo y funcional.

---

### Sesión 12 - Documentación final y limpieza

**Fuente de planificación:** Planificación con ChatGPT. La documentación y el cleanup se dejaron deliberadamente para el final, una vez estable el código.

**Resumen del prompt:** Documentación y limpieza finales: reescribir `README.md` (overview, stack, arquitectura, comandos de ejecución, migraciones, seed, tests, docs de API, ejemplos `curl`, limitaciones conocidas); actualizar `docs/ADR.md` para cubrir PostgreSQL, FastAPI, polling sobre WebSockets, reglas de anomalía, contador de zonas concurrency-safe, estrategia de transacción de `fault`, qué cambiaría a mayor escala y qué se dejó fuera deliberadamente; completar `docs/AI_LOG.md` con prompts, salidas, correcciones y reflexión honesta; y limpieza (eliminar el campo `version` obsoleto de `docker-compose.yml`). Sin cambios de features.

**Por qué el prompt se estructuró así:** La documentación se deja al final porque solo entonces refleja el estado real del código. Pedir explícitamente "no inventar detalles" y "mantenerlo honesto" es una decisión de trazabilidad: la documentación debe corresponder al código.

**Salida de Claude Code:**
- `README.md` reescrito por completo (overview, tabla de stack, diagrama de arquitectura, quick-start de 5 pasos, instrucciones de test, tabla de referencia de API, ejemplos `curl`, árbol del proyecto, limitaciones).
- `docs/ADR.md` reescrito cubriendo las seis decisiones, supuestos, plan de escala y omisiones deliberadas.
- `docs/AI_LOG.md` completado (Sesión 4 como diferida, Sesión 9, reflexión).
- `docker-compose.yml` sin el campo `version: "3.9"` obsoleto.

**Validación realizada:** Verificación de que los comandos documentados (containers, migraciones, seed, tests, frontend, health) sean correctos.

**Correcciones o problemas:** Durante la revisión se detectó que el ADR describía el umbral HIGH_SPEED como `> 3.0 AND status != moving`, cuando el código real usa `> 8.0` incondicional; se corrigió en el ADR. También faltaban tres de las áreas de decisión solicitadas (rationale de FastAPI, atomicidad del contador de zonas, estrategia de transacción de `fault`); se agregaron. Lección: la documentación generada con IA debe contrastarse con el código.

**Resultado final:** Documentación completa y coherente con el código; proyecto listo para entrega.

---

### Sesión 13 - Consolidación de prompts en PROMPTS_USED.md

**Fuente de planificación:** Trabajo de trazabilidad posterior al cierre funcional.

**Resumen:** Se consolidaron en `PROMPTS_USED.md` (raíz del proyecto) las versiones finales y útiles de todos los prompts, junto con una tabla de validación que indica el estado de cada prompt en el log exportado de Claude Code (`logs-fleet-telemetry.txt`): encontrados, parcialmente encontrados, faltantes o reconstruidos desde la conversación. Este documento es la fuente principal de los prompts detallados usados en este `AI_LOG_EXTENDED_ES.md`.

**Por qué se hizo:** El `AI_LOG.md` original comprimía los prompts a resúmenes breves que no reflejaban su nivel real de detalle y preparación. Consolidar las versiones finales preserva la trazabilidad real del proceso. La tabla de validación es honesta sobre qué pudo confirmarse en el log y qué se reconstruyó.

**Resultado final:** `PROMPTS_USED.md` disponible como fuente detallada y auditable de prompts.

---

### Sesión 14 - Documentación de estudio del proyecto (opcional)

**Fuente de planificación:** Prompt opcional preparado tras el cierre funcional, para estudio y defensa técnica del proyecto. No forma parte de la implementación.

**Resumen del prompt:** Crear documentación de estudio en español dentro de `docs/`: `PROJECT_MAP_ES.md`, `BACKEND_WALKTHROUGH_ES.md`, `FRONTEND_WALKTHROUGH_ES.md`, `TESTING_AND_DEBUGGING_WALKTHROUGH_ES.md` y `SENIOR_DEFENSE_GUIDE_ES.md`. Estilo conciso y técnico, conectando la implementación con decisiones, trade-offs y razonamiento senior; explicando tanto qué hace el proyecto como por qué se construyó así. Documentación pura, sin cambios al código.

**Salida de Claude Code:** Los cinco documentos de estudio en `docs/`, cubriendo arquitectura, walkthrough de backend y frontend, estrategia de tests y debugging async, y guía de defensa en entrevista (respuestas de 60 s, 3 min y deep technical, con follow-ups).

**Validación realizada:** Revisión de coherencia con el código fuente.

**Correcciones o problemas:** Supuesto documentado: el número final de tests (30) se tomó de la documentación existente. Documentación pura, sin cambios al código.

**Resultado final:** Set de documentos de estudio disponible junto al log de IA.

---

## Correcciones importantes asistidas por IA

### 1. Duplicación de enums en Alembic

- **Problema:** los tipos enum de PostgreSQL se creaban dos veces (una explícitamente al inicio de la migración, otra al crear las tablas).
- **Error:** `DuplicateObjectError: type "vehiclestatus" already exists`.
- **Solución:** permitir que la primera tabla cree el enum y usar `create_type=False` en las referencias posteriores, aplicándolo a `VehicleStatus`, `MissionStatus` y `MaintenanceStatus`.
- **Lección senior:** las migraciones generadas o asistidas con IA deben revisarse cuidadosamente, en especial cuando usan enums de PostgreSQL.

### 2. Infraestructura de tests async

- **Problema:** la combinación pytest-asyncio + asyncpg + SQLAlchemy async generó errores de event loop y de ciclo de vida de conexiones (`got Future attached to a different loop`, `another operation is in progress`).
- **Secuencia de solución (cuatro rondas encadenadas):**
  1. `NullPool` para el engine de test + loop de sesión y `TEST_DATABASE_URL` apuntando al Postgres de Docker.
  2. Schema creado una sola vez por sesión + `TRUNCATE ... RESTART IDENTITY CASCADE` entre tests (en lugar de `drop_all`/`create_all`).
  3. Teardown con cierre explícito de la `AsyncSession` (`try/finally`) en lugar de `async with`.
  4. Fixture `db` convertido en factory de sesiones de corta vida (abrir/cerrar por query), eliminando la sesión de larga vida y el rollback diferido.
- **Lección senior:** muchos errores en tests async provienen del ciclo de vida de conexiones y sesiones, no de la lógica de negocio. Cada fix fue plausible pero expuso el siguiente problema; resolverlo exigió diagnóstico humano de causa raíz, no solo aceptar la primera sugerencia.

### 3. Problema con el proxy de Vite

- **Problema:** el proxy del frontend eliminaba `/api` (vía `rewrite`) antes de reenviar al backend.
- **Detalle:** las rutas reales del backend viven bajo `/api/*`, por lo que el rewrite producía 404.
- **Solución:** eliminar el `rewrite` para conservar el prefijo `/api`.
- **Lección senior:** el contrato de rutas entre frontend y backend debe verificarse explícitamente, no asumirse.

### 4. Diferencia entre AI_LOG y los prompts reales

- **Problema:** `docs/AI_LOG.md` contenía resúmenes comprimidos (prompts de 2–3 líneas) que no representaban completamente la estrategia real de prompts, que fue más detallada y preparada.
- **Solución:** crear este `AI_LOG_EXTENDED_ES.md` usando `PROMPTS_USED.md` (versiones finales) y los logs disponibles, sin modificar ni reemplazar el `AI_LOG.md` original.
- **Lección senior:** la trazabilidad del uso de IA debe reflejar la guía real del desarrollo, no solo resúmenes demasiado abreviados.

---

## Trade-offs y consideraciones de producción

El diseño actual es suficiente y correcto para la escala del challenge. Lo siguiente describe qué cambiaría en un escenario real.

### Si la flota creciera significativamente

Para miles o decenas de miles de vehículos se evaluaría:

- un message broker (Kafka, Redpanda, AWS Kinesis o Pub/Sub) para desacoplar la ingesta;
- un pipeline de ingesta asíncrono;
- particionamiento de la tabla `telemetry_events`;
- políticas de retención para el historial de telemetría;
- procesamiento por lotes o en streaming;
- réplicas de lectura para las consultas del dashboard;
- Redis u otro mecanismo de contadores atómicos para escenarios de altísima frecuencia.

### Si se necesitara menor latencia

- Se eligió polling cada 2 s por simplicidad y por el alcance del challenge.
- WebSockets o Server-Sent Events serían mejores para actualizaciones subsegundo.
- En producción podría usarse un modelo push en lugar de polling.

### Si se desplegara en la nube

- AWS ECS o EKS para el backend y los contenedores;
- RDS PostgreSQL como base de datos administrada;
- S3 + CloudFront para servir el frontend como assets estáticos (si se compila estático);
- Secrets Manager o Parameter Store para secretos;
- CloudWatch u OpenSearch para logs;
- load balancer delante del backend;
- red privada entre servicios.

No se implementó porque el challenge priorizaba reproducibilidad local.

### Si se necesitara CI/CD

- GitHub Actions o GitLab CI;
- linting;
- tests del backend;
- build del frontend;
- build de imágenes Docker;
- validación de migraciones;
- stages de despliegue;
- configuración por ambiente;
- creación automática de la base de datos de tests.

### Si se necesitara seguridad

- autenticación y autorización;
- rate limiting;
- hardening de inputs;
- API keys o JWT;
- manejo seguro de secretos;
- política CORS por ambiente.

### Si se necesitara observabilidad

- logs estructurados;
- métricas;
- trazas distribuidas;
- health checks;
- dashboards para latencia del API, tasa de errores, rendimiento de base de datos y throughput de ingesta.

### Por qué no se incluyó todo eso

Este fue un take-home challenge de tiempo limitado. El objetivo era entregar una vertical funcional, entendible y testeable, no una plataforma completa de producción. El proyecto priorizó la **corrección de los flujos críticos de negocio** por encima de la amplitud de infraestructura. Cada omisión fue un trade-off consciente.

---

## Razonamiento senior detrás de decisiones principales

**Empezar por la estructura del proyecto.** Por qué: fija el esqueleto y el patrón Controller-Service-Repository antes de cualquier lógica. Trade-off: invertir tiempo en scaffold antes de ver funcionalidad. En producción: igual, pero con plantillas/cookiecutter de la organización.

**Usar FastAPI.** Por qué: async nativo, validación con Pydantic integrada y documentación OpenAPI automática, ideales para una API de telemetría. Trade-off: ecosistema más nuevo que frameworks síncronos clásicos. En producción: se mantiene; se sumaría tuning de workers/uvicorn-gunicorn.

**Usar PostgreSQL en lugar de SQLite.** Por qué: la prueba de concurrencia de zonas y `SELECT FOR UPDATE` requieren semántica atómica real que SQLite no ofrece igual. Trade-off: necesita un servicio aparte (resuelto con Docker Compose). En producción: RDS/instancia administrada.

**Usar SQLAlchemy async.** Por qué: coherente con FastAPI async y con ingesta concurrente. Trade-off: mayor complejidad en el ciclo de vida de conexiones (visible en los tests). En producción: mismo enfoque, con pooling ajustado (no `NullPool`).

**Usar migraciones con Alembic.** Por qué: cambios de schema versionados y reproducibles. Trade-off: las migraciones asistidas por IA necesitan revisión (caso de los enums). En producción: igual, integradas en CI/CD.

**Separar `seed.py` de las migraciones.** Por qué: las migraciones definen estructura; el seed carga datos de ejemplo idempotentes. Mezclarlos acopla datos de prueba al schema. Trade-off: un paso manual extra. En producción: seeds solo para datos de referencia, no de ejemplo.

**Separar `services` y `repositories`.** Por qué: la lógica de negocio queda testeable y el acceso a datos reutilizable. Trade-off: más archivos/indirección. En producción: el mismo patrón escala bien.

**Usar polling en lugar de WebSockets.** Por qué: simple, robusto y suficiente para el refresco de un dashboard de flota cada 2 s. Trade-off: mayor latencia y más requests. En producción: WebSockets/SSE o push si se requiere baja latencia.

**Priorizar tests de backend sobre tests de frontend.** Por qué: la lógica crítica (concurrencia, atomicidad, reglas) vive en el backend. Trade-off: el frontend se valida manualmente. En producción: se añadirían tests de componentes y E2E.

**Usar PostgreSQL real en tests en lugar de mocks.** Por qué: solo así se valida de verdad el contador atómico y los locks. Trade-off: tests más lentos y con dependencia de infraestructura. En producción: igual, en un Postgres efímero de CI.

**Usar Docker Compose para reproducibilidad.** Por qué: un solo comando levanta backend, frontend y Postgres de forma idéntica en cualquier máquina. Trade-off: no es orquestación de producción. En producción: ECS/EKS/Kubernetes.

**Dividir los prompts de IA en etapas.** Por qué: reduce riesgo, hace el output auditable y mantiene la arquitectura intencional. Trade-off: más iteraciones que un único prompt. En producción/equipo: el mismo principio aplica a PRs pequeños y revisables.

---

## Reflexión final

- **La IA fue buena en** generar implementaciones completas y correctas a partir de especificaciones detalladas: lógica de negocio (upserts atómicos, `SELECT FOR UPDATE`, validadores Pydantic, reglas de anomalía), tipos TypeScript y patrones de hooks de React salieron correctos en una sola pasada; incluso detectó el bug del `rewrite` del proxy de Vite.
- **Falló o necesitó corrección en** la infraestructura async de tests (cuatro rondas) y en sutilezas de configuración: la primera solución solía ser direccionalmente correcta pero incompleta, y la migración con enums duplicados.
- **Requirió revisión técnica humana** el contraste de la documentación con el código (umbral HIGH_SPEED 3.0 vs 8.0), el diagnóstico de causa raíz de los errores de event loop, y la decisión de cuándo una corrección era insuficiente.
- **Dividir los prompts mejoró el control:** etapas pequeñas hicieron cada diff auditable, contuvieron los fallos a una capa y mantuvieron la arquitectura intencional en lugar de delegada al modelo.
- **Las pruebas, `curl` y la validación en navegador fueron esenciales:** convirtieron "parece correcto" en "está verificado" y fueron la base para escribir los prompts de corrección a partir de errores reales.
- **En una siguiente iteración se mejoraría** la cobertura de tests del frontend, se añadiría CI/CD con base de datos de tests automática, y se reconsideraría push/WebSockets si el requisito de latencia lo justificara.

---

## Estado final del proyecto

- Backend completado.
- PostgreSQL y migraciones completadas.
- Seed completado.
- Tests de backend completados, con **30 pruebas pasando**.
- Dashboard frontend completado.
- Polling del dashboard validado (cada 2 s, con timestamp de última actualización).
- ADR completado.
- `docs/AI_LOG.md` original conservado, sin modificar ni reemplazar.
- `docs/AI_LOG_EXTENDED_ES.md` creado (este documento).
- `PROMPTS_USED.md` disponible en la raíz del proyecto como fuente detallada de prompts.

---

## Apéndice: trazabilidad de este documento

- **Archivos leídos:** `docs/AI_LOG.md`, `PROMPTS_USED.md` (raíz del proyecto).
- **Archivos creados:** `docs/AI_LOG_EXTENDED_ES.md`.
- **Archivos modificados:** ninguno (no se modificó código, lógica de backend/frontend, tests, ni el `AI_LOG.md` original).
- **Resumen de lo agregado a `docs/AI_LOG_EXTENDED_ES.md`:** visión general del flujo ChatGPT + Claude Code + criterio humano; metodología por fases; alcance y restricción de tiempo del challenge; 14 sesiones cronológicas con fuente de planificación, resumen del prompt, razonamiento, salida de Claude Code, validación, correcciones y resultado; cuatro correcciones importantes asistidas por IA; trade-offs de producción; razonamiento senior por decisión; reflexión final; y estado final del proyecto.
- **Supuestos realizados:**
  - El conteo de 30 tests pasando se tomó de `docs/AI_LOG.md` y `PROMPTS_USED.md`; no se reejecutó la suite al redactar este documento.
  - Las sesiones 4, 6 y 9 se complementaron con la conversación de trabajo donde `PROMPTS_USED.md` indica que el log estaba "parcialmente encontrado", "faltante" o "reconstruido"; esto se señaló en cada sesión correspondiente.
  - `PROMPTS_USED.md` se encontró únicamente en la raíz del proyecto (no en `docs/`), por lo que se usó esa ubicación como fuente detallada de prompts.
