# Registro de Interacciones con IA

Este documento registra todos los prompts relevantes enviados a Claude Code (`claude-sonnet-4-6`) durante el desarrollo del proyecto, junto con los outputs generados, correcciones realizadas y una reflexión final.

---

## Sesión 1 - Estructura del proyecto

**Prompt:**
> Lee el archivo README.md del directorio actual. Úsalo únicamente como contexto para entender los requerimientos del challenge. No implementes todavía la aplicación completa. Tu tarea en este momento es solo crear la estructura inicial del proyecto para un take-home challenge fullstack usando este stack: [detalles del stack y árbol de carpetas proporcionados].

**Output:**
Claude creó todos los archivos de scaffolding en una sola pasada: `docker-compose.yml`, `.env.example`, Dockerfile del backend, `requirements.txt`, configuración inicial de Alembic, esqueleto de la aplicación FastAPI y la base del frontend con React, Vite y TypeScript. Respetó la restricción de no sobrescribir `README.md` y dejó los archivos de lógica de negocio vacíos, con stubs y docstrings.

**Correcciones / redirecciones:** Ninguna en esta etapa.

---

## Sesión 2 - Modelos del backend y capa de base de datos

**Prompt:**
> Implementa únicamente la base de datos del backend. Modelos: Vehicle, TelemetryEvent, ZoneCounter, Anomaly, Mission, MaintenanceRecord. Schemas Pydantic para todos los endpoints. Migración inicial de Alembic escrita manualmente, sin depender de una base de datos en vivo. Script de seed idempotente para 50 vehículos y 20 zonas. No implementes todavía services ni lógica de API.

**Output:**
Claude creó:

- `app/models/enums.py`: enums compartidos de Python (`VehicleStatus`, `MissionStatus`, `MaintenanceStatus`) usados tanto por los modelos ORM como por los schemas Pydantic.
- Seis archivos de modelos (`vehicle.py`, `telemetry.py`, `zone.py`, `anomaly.py`, `mission.py`, `maintenance.py`) usando el estilo `Mapped` y `mapped_column` de SQLAlchemy 2.x, con foreign keys, índices y relaciones.
- Cinco archivos de schemas (`telemetry.py`, `vehicle.py`, `fleet.py`, `zone.py`, `anomaly.py`) con `field_validator` para validar el formato de `vehicle_id` (`v-01` a `v-50`), whitelist de zonas y rango permitido para `battery_pct`.
- `alembic/versions/0001_initial_schema.py`: migración inicial escrita manualmente, creando primero los tipos enum y luego las tablas según el orden de dependencias de foreign keys.
- `seed.py` en la raíz del backend: seed async idempotente usando `ON CONFLICT DO NOTHING`.

**Decisiones clave tomadas:**

- Todas las tablas hijas usan foreign key contra `vehicles.vehicle_id` como string, no contra el primary key entero. Esto evita un lookup extra por cada evento de telemetría, porque el payload ya trae el ID del vehículo como string.
- Se usó `create_type=False` en el enum `vehiclestatus` dentro de `TelemetryEvent` para evitar que PostgreSQL intentara crear el mismo tipo dos veces.
- `ZoneCounter.entry_count` usa `Integer`, no `BigInteger`, porque es suficiente para la escala del prototipo. La limitación quedó documentada en los supuestos.
- El campo `latest_anomaly` en `VehicleResponse` queda por defecto en `None`. La capa de service lo completa; `from_attributes=True` de Pydantic usa ese default si el atributo no existe en el objeto ORM.

**Correcciones / redirecciones:** Ninguna.

---

## Sesión 3 - Lógica de services y endpoints de API

**Prompt:**
> Implementa la lógica de services del backend y los endpoints de API. POST /api/telemetry (ingestión + detección de anomalías + incremento de zona). GET /api/zones/counts (contadores atómicos). GET /api/vehicles + PATCH /api/vehicles/{id}/status (con transacción de fault). GET /api/fleet/state (agregado con GROUP BY). GET /api/anomalies (consulta filtrable). Mantén la lógica de negocio en services y el acceso a base de datos en repositories. Todas las rutas deben estar bajo /api. Sin auth y sin websockets.

**Output:**
Claude creó:

- **6 archivos de repositories** (`vehicle`, `telemetry`, `zone`, `anomaly`, `mission`, `maintenance`): wrappers delgados async sobre SQLAlchemy, sin lógica de negocio.
- **5 archivos de services** (`telemetry`, `vehicle`, `zone`, `fleet`, `anomaly`): toda la orquestación y reglas de negocio viven aquí.
- **5 routers de API** completamente conectados. Antes eran stubs; ahora cada controlador llama a un único método de service.
- Actualización de `main.py` para agregar el prefijo `/api` a todos los routers y hacerlo coincidir con la configuración del proxy de Vite.

**Detalles clave de implementación:**

- El incremento de zona usa una única sentencia `INSERT ... ON CONFLICT DO UPDATE SET entry_count = entry_count + 1`. No hay read-modify-write en Python; PostgreSQL serializa atómicamente los incrementos concurrentes para la misma zona.
- La transición a `fault` usa `SELECT ... FOR UPDATE` para bloquear la fila del vehículo. Luego cancela misiones y crea un registro de mantenimiento dentro de la misma transacción. Un rollback revierte todos los cambios juntos.
- La detección de anomalías evalúa cuatro reglas por cada evento de telemetría: `LOW_BATTERY` menor a 15 %, `VEHICLE_FAULT`, `ERROR_CODE_REPORTED` y `HIGH_SPEED` mayor a 8 m/s. Cada regla activada produce una fila en `anomalies`.
- El estado de flota usa una sola consulta `GROUP BY current_status`. Es una lectura consistente bajo aislamiento `READ COMMITTED` y segura frente a actualizaciones concurrentes de status.
- Se llama `session.flush()` después del `INSERT` de `TelemetryEvent` para que el primary key autogenerado esté disponible dentro de la misma transacción, antes de crear las anomalías que lo referencian como foreign key.

**Supuestos realizados:**

- La ingestión de telemetría actualiza el snapshot del vehículo con estrategia last-write-wins. La tabla `vehicles` es una vista rápida del estado actual; la fuente de verdad histórica es `telemetry_events`.
- El endpoint explícito `PATCH /vehicles/{id}/status` es el único flujo que dispara la cancelación de misiones. La ingestión de telemetría solo actualiza el snapshot del vehículo y registra una anomalía `VEHICLE_FAULT`.
- Si un `vehicle_id` no existe en la base de datos porque no fue sembrado, el `INSERT` en `TelemetryEvent` fallará por la foreign key. El seed es una precondición del sistema, no una preocupación de runtime.

**Correcciones / redirecciones:** Ninguna.

---

## Sesión 4 - Dashboard frontend

*Diferido.* El frontend se implementó en dos sesiones posteriores, las sesiones 7 y 8, después de estabilizar la infraestructura de tests del backend. No hubo un prompt independiente para una "Sesión 4"; el salto en la numeración refleja el orden real en que ocurrió el trabajo.

---

## Sesión 5 - Tests

**Prompt:**
> Agrega tests de backend para: ingestión de telemetría + actualización de estado del vehículo, las cuatro reglas de anomalía, concurrencia del contador de zonas con 20 requests simultáneos, atomicidad de la transición a fault (vehicle + mission + maintenance), y agregación del estado de flota. Usa pytest-asyncio. Los tests deben correr contra una base de datos real de test, no contra mocks.

**Output:**
Claude creó:

- `backend/pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`.
- `backend/tests/conftest.py`: fixtures compartidos: `reset_db` autouse con drop y create de todas las tablas por test, `client` usando `httpx.AsyncClient` con `ASGITransport` y override de `get_db` hacia la base de datos de test, y `db` como sesión async para assertions directas.
- `backend/tests/test_telemetry.py`: 12 tests para ingestión, actualización de estado del vehículo, las cuatro reglas de anomalía con casos límite, múltiples reglas activadas en un mismo evento, relación FK entre anomalía y evento de telemetría, y rechazo de payloads inválidos.
- `backend/tests/test_zones.py`: 5 tests para incremento de contador, zona nula, acumulación secuencial, conteo independiente por zona y test de concurrencia usando `asyncio.gather` con 20 POSTs simultáneos.
- `backend/tests/test_vehicles.py`: 8 tests para PATCH no-fault, 404 con vehículo desconocido, transición a fault actualizando vehículo, misión y mantenimiento, cancelación de todas las misiones activas, y assertion de atomicidad verificando los tres cambios juntos.
- `backend/tests/test_fleet.py`: 4 tests para base vacía, todos los vehículos idle, estados mixtos y actualización visible después de un PATCH.

**Decisiones clave de diseño:**

- Base de datos PostgreSQL real de test (`fleet_telemetry_test`) en lugar de mocks o SQLite. El test de concurrencia de zonas requiere las semánticas reales de atomicidad de PostgreSQL.
- `reset_db` con `drop_all()` y `create_all()` por test para garantizar aislamiento y evitar complicaciones iniciales con TRUNCATE y tipos enum.
- Override de `get_db` configurado a nivel de módulo en `conftest`, de modo que todos los requests HTTP usen la base de datos de test sin tener que parchear cada test.
- `asyncio.gather()` para el test de concurrencia. `httpx.AsyncClient` con `ASGITransport` despacha los 20 requests de forma concurrente en el mismo event loop; cada request obtiene una sesión real de base de datos desde el pool.

**Bugs encontrados y corregidos:** Ninguno. La implementación existente era correcta. Los casos límite se probaron explícitamente: `battery_pct == 15.0` no dispara anomalía y `speed_mps == 8.0` tampoco dispara anomalía.

**Supuestos:**

- La base de datos de test debe existir antes de correr los tests: `docker compose exec postgres createdb -U fleet fleet_telemetry_test`.
- Los tests se ejecutan dentro del contenedor del backend o con las variables `DATABASE_URL` y `TEST_DATABASE_URL` configuradas correctamente.
- `asyncio_mode = auto` evita tener que poner `@pytest.mark.asyncio` en cada función de test.

**Correcciones / redirecciones:** Ninguna.

---

## Sesión 6 - Corrección de infraestructura async de tests

**Prompt:**
> Los tests del backend ya se conectan a la base de datos de test, pero solo el primer test pasa. El resto falla durante reset_db con: RuntimeError: got Future attached to a different loop y también: asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress. Corrige la configuración async de tests en backend/tests/conftest.py. Requisitos: No cambies la lógica de negocio de la aplicación. No cambies endpoints de API. Corrige solo la infraestructura de tests salvo que sea estrictamente necesario. Usa SQLAlchemy NullPool para el engine de test. El TEST_DATABASE_URL por defecto debe funcionar dentro de Docker: postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test. Actualiza pytest.ini si es necesario.

**Output:**
Claude aplicó dos fixes puntuales:

- `backend/pytest.ini`: agregó `asyncio_default_fixture_loop_scope = session` para forzar un único event loop compartido durante toda la sesión de tests.
- `backend/tests/conftest.py`: agregó `poolclass=NullPool` al engine de test, eliminando el cacheo de conexiones entre tests, y cambió el host por defecto de `TEST_DATABASE_URL` de `localhost` a `postgres`, que es el hostname del servicio Docker.

**Causa raíz:**
`pytest-asyncio` 0.24 crea por defecto un nuevo event loop por cada función de test. El `_engine` compartido usaba el pool interno de asyncpg, que cacheaba conexiones asociadas al event loop del primer test. Cuando el segundo test corría en un loop nuevo, `reset_db` hacía `engine.begin()` y recibía una conexión del loop anterior. Eso causaba el error "Future attached to a different loop". `asyncio_default_fixture_loop_scope = session` elimina la rotación de loops por test, y `NullPool` asegura que SQLAlchemy no cachee conexiones.

**Cambios realizados:**

- `pytest.ini`: `asyncio_default_fixture_loop_scope = session`.
- `conftest.py`: `from sqlalchemy.pool import NullPool`, `create_async_engine(..., poolclass=NullPool)`, host por defecto `localhost` → `postgres`.

**Correcciones / redirecciones:** El fix con `NullPool` por sí solo no fue suficiente. El error de asyncpg "another operation is in progress" seguía apareciendo porque `Base.metadata.drop_all` emite múltiples sentencias DDL sobre la misma conexión, mientras asyncpg todavía considera que una sentencia previa está en vuelo a nivel de driver. Se reemplazó por completo el drop y create por test por una creación de schema con scope de sesión, una vez por ejecución, y un `TRUNCATE … RESTART IDENTITY CASCADE` antes de cada test. `TRUNCATE` es una sola sentencia atómica por conexión, por lo que no genera intercalado a nivel del driver. Los fixtures autouse de cada módulo siembran sus filas necesarias sobre tablas recién vaciadas.

---

## Sesión 7 - Capa de integración API del frontend

**Prompt:**
> Implementa la capa de integración API del frontend: tipos TypeScript, capa de servicios API usando fetch, sin librerías extra, paths relativos /api, hooks usePolling y useFleetData con polling cada 2 segundos, loading/error/data y sin memory leaks, y actualiza App.tsx para comprobar que los datos cargan. No construyas todavía la UI final del dashboard.

**Output:**
Claude creó:

- `frontend/src/types/index.ts`: interfaces TypeScript que reflejan los schemas Pydantic del backend: union type `VehicleStatus`, `Anomaly`, `Vehicle` con `last_seen_at`, `battery_pct` y `latest_anomaly`, `FleetState`, `ZoneCount`, y `ZoneCountResponse` como envelope `{ zones: ZoneCount[] }`.
- `frontend/src/services/api.ts`: cuatro wrappers tipados con `fetch` (`fetchVehicles`, `fetchFleetState`, `fetchZoneCounts`, `fetchAnomalies`). `fetchZoneCounts` desenvuelve el array `zones` del envelope devuelto por el backend. Un helper compartido `apiFetch<T>` lanza error si el status HTTP no es ok.
- `frontend/src/hooks/usePolling.ts`: hook genérico `usePolling(callback, intervalMs)` usando el patrón de `useRef`, para que el interval no se reprograme cada vez que cambia la identidad del callback. Solo cambia si cambia la duración del intervalo. Ejecuta el callback inmediatamente al montar.
- `frontend/src/hooks/useFleetData.ts`: hook `useFleetData()` que dispara los cuatro fetches en paralelo con `Promise.all`; expone `loading`, `error` y los cuatro grupos de datos. `loading` pasa a `false` después de la primera respuesta, sea exitosa o fallida, y se mantiene así en los siguientes polls.
- `frontend/src/App.tsx`: conectado a `useFleetData`; renderiza estados de loading y error, conteo de vehículos, JSON del estado de flota y JSON de conteos por zona.
- `frontend/vite.config.ts`: eliminó el `rewrite` incorrecto que quitaba `/api` antes de reenviar la request. Las rutas del backend viven bajo `/api/*`, por lo que el prefijo debe conservarse.

**Bug corregido:**
El `vite.config.ts` original reescribía `/api/vehicles` como `/vehicles` antes de enviarlo a `http://backend:8000`. El backend expone todas las rutas bajo `/api/*`, por lo que eso producía 404. Se eliminó completamente el `rewrite`; Vite ahora reenvía `/api/*` sin modificarlo hacia `http://backend:8000/api/*`.

**Supuestos:**

- Sin autenticación. Todas las llamadas API son públicas.
- Si un poll falla, se muestran los datos anteriores en lugar de limpiar la pantalla. El mensaje de error aparece junto al último estado conocido.
- `loading` es `true` solo hasta la primera respuesta. No vuelve a `true` en cada ciclo de polling.
- No se agregó `AbortController` para cancelar fetches en vuelo al desmontar. Es aceptable para este prototipo y queda como brecha conocida.

---

## Sesión 8 - UI del dashboard en React

**Prompt:**
> Construye la UI del dashboard en React usando la capa de integración API existente. Componentes: FleetSummary, VehicleTable, ZoneCounts, AnomalyBadge, StatusBadge, ErrorState, LoadingState. Muestra el agregado del estado de flota, los 50 vehículos con status/battery/last_seen/latest_anomaly, y conteos por zona. Polling cada 2 segundos. Muestra timestamp de última actualización. Maneja estados loading/error/empty. CSS plano, sin librería de UI.

**Output:**
Claude creó:

- `frontend/src/App.css`: stylesheet completo con custom properties CSS, header oscuro, grid de resumen de flota con 5 cards y borde izquierdo por status, layout de dos columnas para vehículos y zonas, headers sticky en tablas, colores para badges de status y anomalía, animación de spinner, y breakpoints responsive en 960 px y 540 px.
- `frontend/src/components/LoadingState.tsx`: spinner con mensaje "Loading fleet data…".
- `frontend/src/components/ErrorState.tsx`: pantalla completa de error para fallos en la primera carga; muestra descripción y mensaje indicando que se reintentará.
- `frontend/src/components/StatusBadge.tsx`: badge tipo pill con color según `VehicleStatus`; usa clases CSS `status--idle`, `status--moving`, `status--charging`, `status--fault`.
- `frontend/src/components/AnomalyBadge.tsx`: badge con color y etiqueta legible por tipo de anomalía; el tooltip muestra descripción y timestamp. Las clases CSS se basan en el `anomaly_type` en minúsculas.
- `frontend/src/components/FleetSummary.tsx`: fila de 5 tarjetas de resumen: idle, moving, charging, fault y total, con bordes izquierdos por color.
- `frontend/src/components/VehicleTable.tsx`: tabla scrolleable con altura máxima de 660 px, headers sticky, ordenada por `vehicle_id`; muestra `StatusBadge`, batería en rojo si es menor a 15 %, `last_seen_at` formateado, `AnomalyBadge` o "—"; las filas en status fault tienen un fondo rojizo.
- `frontend/src/components/ZoneCounts.tsx`: tabla ordenada por `entry_count` descendente; zonas con `charging` en el nombre resaltadas en azul; nombres de zona humanizados reemplazando underscores por espacios.
- `frontend/src/hooks/useFleetData.ts`: agregó `lastUpdated: Date | null`, actualizado en cada poll exitoso.
- `frontend/src/App.tsx`: compone todos los componentes; loading → `LoadingState`, error en el primer poll → `ErrorState`, estado normal → dashboard completo con banner inline para errores en polls posteriores, manteniendo visibles los datos stale.

**Decisiones clave de diseño:**

- Un error en la primera carga reemplaza la página completa. Un error en un poll posterior muestra solo un banner sobre los datos anteriores. Esto permite que el usuario siga viendo el último estado conocido mientras el backend se recupera.
- `latest_anomaly` viene directamente de `VehicleResponse`, enriquecido por la capa de service. No se necesita hacer un join del lado del cliente contra la lista de anomalías.
- El umbral visual de batería baja es menor a 15 %, igual que la regla `LOW_BATTERY` del backend.
- La tabla de zonas se ordena por `entry_count` descendente para mostrar primero las zonas con más actividad.

**Supuestos:**

- No se necesita routing porque el dashboard es una sola pantalla.
- `anomalies` se obtiene en `useFleetData`, pero no se muestra como sección separada. Ya está cubierta a nivel de vehículo mediante `latest_anomaly`.
- El layout responsive colapsa a una sola columna por debajo de 960 px.

---

## Sesión 9 - Documentación final y limpieza

**Prompt:**
> Realiza documentación final y limpieza. Actualiza README.md con overview, stack, arquitectura, comandos de ejecución, ejemplos curl y limitaciones conocidas. Actualiza el ADR para cubrir la decisión de FastAPI, atomicidad del contador de zonas, estrategia de fault transition y corregir el umbral de HIGH_SPEED. Completa el AI_LOG incluyendo esta sesión y la reflexión. Elimina el campo obsoleto `version` de docker-compose.yml. No hagas cambios de features.

**Output:**

- `README.md`: reescritura completa reemplazando el prompt crudo del challenge por overview del proyecto, tabla de stack, diagrama de arquitectura, quick-start en 5 pasos (env → up → migrate → seed → open), instrucciones de tests, tabla completa de referencia de API, ejemplos curl para cada endpoint, árbol de estructura del proyecto y limitaciones conocidas.
- `docs/ADR.md`: reescritura completa cubriendo las seis decisiones: PostgreSQL, FastAPI + async, polling, reglas de anomalía, contador atómico de zonas y transacción de fault. También incluye supuestos, plan de escala y omisiones deliberadas. Se corrigió el umbral de `HIGH_SPEED`, que antes decía `> 3.0 AND status != moving`, cuando el código real usa `> 8.0`.
- `docs/AI_LOG.md`: se completó la Sesión 4 indicando que fue diferida, se completó la Sesión 9 y se escribió la reflexión.
- `docker-compose.yml`: se eliminó el campo obsoleto `version: "3.9"`. Docker Compose V2 lo ignora, pero muestra un warning.

**Bugs detectados durante la revisión:**

- El ADR describía `HIGH_SPEED` como `speed_mps > 3.0 AND status != "moving"`. El código real usa `speed_mps > 8.0`, sin condición adicional. Se corrigió en el ADR.
- El ADR no cubría tres áreas de decisión solicitadas: justificación de FastAPI, atomicidad del contador de zonas y estrategia de transacción para fault. Se agregaron.

**Correcciones / redirecciones:** Ninguna.

---

## Reflexión

- **Dónde la IA fue fuerte:** Generó implementaciones completas y correctas a partir de especificaciones detalladas en una sola pasada. La lógica de negocio, incluyendo upserts atómicos, `SELECT FOR UPDATE`, validadores de Pydantic, reglas de anomalía, tipos TypeScript y patrones de hooks en React, salió correctamente desde el primer intento. También detectó un bug existente antes de tocar esa parte del código: el `rewrite` del proxy de Vite, que habría hecho que todas las llamadas del frontend a la API devolvieran 404.

- **Dónde falló:** La infraestructura async de tests. Lograr que `pytest-asyncio`, `asyncpg` y el engine async de SQLAlchemy convivieran sin errores como "Future attached to a different loop" o "another operation is in progress" requirió cuatro rondas de debugging: (1) agregar `NullPool`, (2) reemplazar `drop_all` y `create_all` por `TRUNCATE`, (3) cambiar de `async with` a `try/finally` explícito, y (4) reemplazar el fixture `db` de sesión larga por una factory que abre y cierra una sesión por consulta. Cada fix era razonable por separado, pero exponía el siguiente problema.

- **Qué requirió doble revisión manual:** El umbral de anomalía del ADR estaba mal: 3.0 vs 8.0 m/s. Se detectó comparando el ADR contra el código real del service durante la revisión final. También fue necesario verificar el flujo de despliegue: las migraciones no se ejecutan automáticamente al iniciar el contenedor, por lo que debían documentarse como paso manual.

- **Qué tuve que corregir o redirigir:** Casi exclusivamente la infraestructura de tests, en cuatro rondas. También hubo una redirección relacionada con el proxy de Vite: el bug del `rewrite` venía del scaffolding y Claude lo detectó al implementar la capa de API. El resto, modelos, services, repositories, endpoints y componentes React, no requirió correcciones.

- **Evaluación general:** La IA fue altamente efectiva para generación de código y arquitectura en un proyecto fullstack bien especificado. El principal modo de falla fue la sutileza de infraestructura y configuración, especialmente comportamiento async que depende de la interacción entre versiones de librerías. Ahí, el primer fix de la IA suele ir en la dirección correcta, pero puede quedar incompleto. Para un take-home challenge con tiempo limitado, la asistencia de IA hizo viable entregar una aplicación completa, testeada y documentada. El valor humano estuvo en revisar la corrección de los artefactos generados, comparar documentación contra código real y reconocer cuándo un fix todavía no resolvía el problema de fondo.

---

## Sesión 10 - Guía técnica de estudio en español

**Prompt (resumen):**
> Crea una guía técnica de nivel senior en español para entender, explicar y defender este proyecto en una entrevista técnica. Lee toda la documentación existente, código backend, código frontend y tests. Crea cinco documentos dentro de docs/: PROJECT_MAP_ES.md, BACKEND_WALKTHROUGH_ES.md, FRONTEND_WALKTHROUGH_ES.md, TESTING_AND_DEBUGGING_WALKTHROUGH_ES.md, SENIOR_DEFENSE_GUIDE_ES.md. Estilo: español conciso, técnico y directo. Conecta la implementación con decisiones técnicas, trade-offs y razonamiento senior. Explica tanto qué hace el proyecto como por qué se construyó de esta manera.

**Archivos creados:**

- `docs/PROJECT_MAP_ES.md`: arquitectura, objetivo del challenge, decisión de comenzar por la estructura, secuencia de desarrollo, diagrama y orden de lectura recomendado.
- `docs/BACKEND_WALKTHROUGH_ES.md`: walkthrough por capas del backend: main, core, models, schemas, services, repositories, constants, migrations y seed. Incluye flujo completo de telemetría, upsert atómico, `SELECT FOR UPDATE` y qué se dejó intencionalmente simple por ser un take-home.
- `docs/FRONTEND_WALKTHROUGH_ES.md`: arquitectura del frontend, por qué se separó en capas, cómo funciona el polling, bug del proxy de Vite, comportamiento de loading/error/stale data y cómo explicarlo en entrevista.
- `docs/TESTING_AND_DEBUGGING_WALKTHROUGH_ES.md`: estrategia de tests, por qué PostgreSQL real, qué valida cada archivo de test, los tres problemas async que aparecieron y sus fixes (`NullPool`, `TRUNCATE`, `db` como factory), y diagnóstico de causa raíz.
- `docs/SENIOR_DEFENSE_GUIDE_ES.md`: guía de defensa en entrevista con respuestas de 60 segundos, 3 minutos y explicación técnica profunda; incluye preguntas concretas y follow-up questions con respuestas fuertes.

**Supuestos realizados:**

- El número final de tests es 30, tal como documentan el README y el AI_LOG. No se ejecutaron los tests para confirmarlo; se confió en la documentación existente.
- La guía asume que el lector tiene acceso al código fuente para validar los fragmentos citados.
- Los documentos están escritos en primera persona para que puedan usarse directamente en una entrevista sin reformular demasiado.
- Se asumió que `asyncio_default_fixture_loop_scope = session` sigue en `pytest.ini`, tal como fue configurado en la Sesión 6; no se verificó el archivo al momento de redactar.

**Correcciones / redirecciones:** Ninguna. Fue una sesión de documentación pura, sin cambios al código.
