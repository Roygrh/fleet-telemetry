# AI_LOG_EXTENDED_ES

Este documento explica, paso a paso y en orden cronológico, cómo desarrollé el proyecto `fleet-telemetry` apoyándome en herramientas de IA. Está escrito como si se lo explicara a un entrevistador técnico: qué entendí del challenge, qué decisiones tomé, qué prompts usé en cada etapa, qué generó Claude Code, cómo lo validé y qué corregí cuando algo falló.

El flujo de trabajo siempre tuvo tres roles bien diferenciados:

- **ChatGPT**: lo usé para analizar el enunciado, definir arquitectura, dividir el trabajo en etapas pequeñas, refinar cada prompt y razonar sobre los errores.
- **Claude Code**: lo usé para ejecutar los cambios sobre el repositorio, crear y modificar archivos, y correr comandos.
- **Mi criterio técnico**: definió el alcance, revisó cada resultado, validó con comandos reales, diagnosticó los errores y decidió las correcciones, manteniendo todo alineado con el challenge.

Los prompts de ChatGPT aparecen traducidos/redactados en español. Los prompts de Claude Code se incluyen **exactamente** como se usaron (en inglés, sin resumir ni modificar), tal como están registrados en `PROMPTS_USED.md`.

---

## 1. Punto de partida: lectura del challenge

Lo primero que hice fue leer con calma `docs/take_home.txt`. El enunciado pedía construir una *vertical slice* de un sistema de monitoreo de flota para 50 vehículos industriales autónomos que emiten telemetría a 1 Hz cada uno. En concreto, el challenge pedía:

- un **backend en Python** con FastAPI o Django REST (a elección);
- **recepción de eventos de telemetría** vía un endpoint POST, soportando *bursts* de escrituras concurrentes de múltiples vehículos a la vez;
- **persistencia** en SQLite o PostgreSQL, justificando la elección;
- **detección de anomalías en tiempo real**, con mi propia definición de "anomalía" justificada en el ADR;
- un **contador de zonas seguro ante concurrencia**: ~20 zonas hardcodeadas, incrementar `entry_count` cuando llega `zone_entered`, garantizando que **cada** entrada se cuente aunque varios vehículos entren a la misma zona en el mismo instante;
- el endpoint **`GET /zones/counts`**;
- la **transición a `fault`**: al pasar un vehículo a `fault`, cancelar atómicamente su misión activa y crear un registro de mantenimiento, pensando en la concurrencia y la estrategia de aislamiento correcta;
- un endpoint de **anomalías filtrable por vehículo y rango de tiempo**;
- un endpoint de **estado agregado de flota** (conteo por estado de los 50 vehículos) seguro bajo escrituras concurrentes;
- un **dashboard en React + TypeScript** con la lista viva de los 50 vehículos (estado y batería), la anomalía más reciente por vehículo y los contadores de zona actualizándose en vivo;
- **polling o WebSockets**, justificando la elección;
- un **ADR** de una página;
- un **AI Interaction Log**.

El enunciado también fijaba un presupuesto de 5–6 horas y dejaba claro que el ADR y el AI log se valoran tanto como el código. Por eso definí mi alcance desde el principio: por tratarse de un take-home con tiempo limitado, mi meta fue construir una **vertical funcional, testeable y defendible** —los flujos críticos del challenge funcionando de verdad, con persistencia real, concurrencia correcta, tests y dashboard— y **no** una plataforma de producción completa. Cada decisión que tomé después se entiende dentro de esa restricción.

A partir de aquí, el desarrollo avanzó en etapas pequeñas y revisables.

---

## 2. Arquitectura inicial y estructura del proyecto

### Qué requerimiento o problema estaba resolviendo

El challenge pedía un proyecto fullstack completo (backend, frontend, persistencia, documentación). Antes de escribir lógica, necesitaba una estructura clara que separara responsabilidades y permitiera implementar cada parte después sin que el proyecto se convirtiera en una generación masiva e imposible de revisar.

### Por qué tomé esta decisión

Decidí no empezar escribiendo endpoints directamente. El challenge tiene partes delicadas (concurrencia de zonas, transacción de `fault`, agregación segura) y mezclar todo de golpe habría hecho el código difícil de auditar. Opté por una separación por capas en el backend —rutas HTTP, schemas, servicios, repositorios, modelos, configuración y constantes— porque eso permite que la lógica de negocio quede testeable y aislada del acceso a datos. Esa misma separación, más adelante, fue justo lo que hizo fácil intercambiar la sesión async en los tests.

En producción esta estructura escalaría bien sin cambios mayores; a lo sumo partiría de plantillas internas de la organización. Para un challenge, lo importante era fijar el esqueleto y el patrón Controller-Service-Repository antes de cualquier regla de negocio.

### Prompt refinado usado en ChatGPT

Para esta etapa usé dos prompts de planificación en ChatGPT: uno para definir la arquitectura y otro para preparar el prompt concreto de Claude Code.

```text
Quiero analizar el enunciado del challenge antes de empezar a programar y definir una estructura inicial del proyecto que sea clara, mantenible y fácil de defender en una entrevista técnica.

El proyecto debe ser una aplicación fullstack para monitoreo de telemetría de vehículos, con backend en Python usando FastAPI, frontend en React con TypeScript, base de datos PostgreSQL y ejecución local con Docker Compose.

Antes de implementar lógica de negocio, quiero decidir cómo dividir el proyecto en carpetas y responsabilidades.

Necesito una propuesta de estructura que separe claramente:

- backend
- frontend
- documentación
- migraciones
- tests
- configuración Docker
- configuración de entorno

En el backend, quiero una separación por capas que permita distinguir:

- rutas HTTP
- schemas de validación
- servicios de negocio
- repositorios de acceso a datos
- modelos de base de datos
- configuración central
- constantes del dominio

No quiero que todavía se implemente la aplicación completa. Primero quiero entender cómo debería quedar organizada para que el desarrollo posterior sea controlado y no se convierta en una generación grande y difícil de revisar.

Después de definir la estructura, quiero que me prepares el prompt que le enviaré a Claude Code para crear solamente esta estructura inicial, sin lógica de negocio todavía.
```

```text
Ahora quiero preparar el prompt que enviaré a Claude Code para crear la estructura inicial del proyecto.

El prompt debe ser específico y limitado. Debe indicar que ya estoy dentro de la carpeta raíz del proyecto y que Claude Code no debe crear una carpeta adicional con el mismo nombre.

Debe pedir que lea el README o el archivo del challenge solo como contexto, pero sin sobrescribirlo.

La estructura debe estar preparada para:

- backend con FastAPI
- frontend con React, TypeScript y Vite
- PostgreSQL
- Docker Compose
- documentación con ADR y AI_LOG
- carpetas backend para api, core, models, schemas, services, repositories, constants y tests

El prompt debe dejar claro que esta etapa no debe implementar todavía reglas de negocio, endpoints completos, lógica de concurrencia ni dashboard final.

La idea es crear una base ordenada para que luego cada parte del proyecto se implemente con prompts más pequeños y revisables.
```

### Prompt usado en Claude Code

```text
I am already inside the root project folder: fleet-telemetry.

Read the README.md file in the current directory. Use it only as context for the challenge requirements. Do not implement the full application yet.

Your task now is only to create the initial project structure for a fullstack take-home challenge using this stack:
- Backend: Python, FastAPI, SQLAlchemy, PostgreSQL
- Frontend: React, TypeScript, Vite
- Live updates: polling
- Local environment: Docker Compose
- Documentation: docs/ADR.md and docs/AI_LOG.md

Create this structure in the current directory:

.
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/
│   ├── ADR.md
│   └── AI_LOG.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── env.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── telemetry.py
│   │   │   ├── vehicles.py
│   │   │   ├── zones.py
│   │   │   ├── anomalies.py
│   │   │   └── fleet.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   ├── repositories/
│   │   │   └── __init__.py
│   │   └── constants/
│   │       ├── __init__.py
│   │       └── zones.py
│   └── tests/
│       └── __init__.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── components/
        ├── pages/
        ├── services/
        ├── hooks/
        └── types/

Important rules:
- Do not create another fleet-telemetry folder.
- Do not overwrite README.md.
- Do not implement business logic yet.
- Only add minimal functional boilerplate for configuration files (Docker, Vite, TS, package.json, requirements.txt, main.py).
- Keep Python files in api, models, schemas, services, and repositories empty or with basic docstrings explaining the Controller-Service-Repository pattern.
- Add the hardcoded ZONES constant in backend/app/constants/zones.py.
- Docker Compose must include backend, frontend, and postgres services with basic wiring.
- Keep the structure simple, clean, and not overengineered.

After creating the structure, show me:
1. The final folder tree.
2. A short explanation of the main folders.
3. Any assumptions you made.
```

### Qué generó Claude Code

Claude Code creó todo el scaffold en una sola pasada: `docker-compose.yml`, `.env.example`, el `Dockerfile` del backend, `requirements.txt`, la configuración de Alembic, el esqueleto de la app FastAPI y el shell de React/Vite/TypeScript. Respetó las restricciones: no sobrescribió `README.md`, no duplicó la carpeta del proyecto, dejó los archivos de lógica vacíos con docstrings explicando el patrón Controller-Service-Repository, y colocó la constante `ZONES` en `backend/app/constants/zones.py` con las 20 zonas del enunciado. El `docker-compose.yml` quedó con los servicios `backend`, `frontend` y `postgres`.

### Cómo lo validé

Revisé el árbol de carpetas generado y verifiqué que los archivos de configuración fueran coherentes con el stack (Docker, Vite, TS, `requirements.txt`, `main.py`). En esta etapa la validación fue estructural; la ejecución real vino con las siguientes capas.

### Qué tuve que corregir

Nada en esta etapa.

### Resultado de la etapa

Quedó una base ordenada y limpia, con el patrón de capas listo para implementar el backend pieza por pieza.

---

## 3. Base de datos del backend

### Qué requerimiento o problema estaba resolviendo

Varios requerimientos del challenge dependen directamente de un buen modelo de datos: persistir eventos de telemetría, contar zonas, registrar anomalías, mantener el estado actual de cada vehículo y soportar la transición a `fault` (que toca misiones y mantenimiento). Por eso la base de datos era la siguiente capa lógica a construir.

### Por qué tomé esta decisión

Decidí construir primero el modelo de datos y los schemas, antes de cualquier endpoint. Si el modelo está bien, la lógica encaja después con naturalidad; si está mal, todo lo demás se contamina.

Aquí tomé la decisión de **PostgreSQL sobre SQLite**, que el challenge pedía justificar. El enunciado exige manejar *bursts* de escrituras concurrentes (50 vehículos × 1 Hz) y garantizar que cada entrada de zona se cuente. SQLite serializa todas las escrituras a través de un único lock global, lo que convertiría esas 50 escrituras por segundo en una cola. PostgreSQL bloquea a nivel de fila, soporta `SELECT ... FOR UPDATE` y upserts atómicos (`INSERT ... ON CONFLICT`), y tiene un driver async (`asyncpg`). SQLite habría sido más simple de levantar, pero no me permitiría **validar de verdad** el requerimiento de concurrencia, que es el corazón del challenge. Esa es exactamente la clase de decisión que el ADR debía defender.

También elegí escribir la migración inicial **a mano** en lugar de autogenerarla contra una base viva, para tener control total sobre el orden de creación de los tipos enum y de las tablas según sus dependencias de FK.

### Prompt refinado usado en ChatGPT

```text
Ya tengo la estructura inicial del proyecto. Ahora quiero avanzar con la base de datos del backend, pero sin implementar todavía endpoints ni lógica de negocio.

Necesito preparar el siguiente prompt para Claude Code enfocado únicamente en la fundación de datos del backend.

El prompt debe pedir modelos SQLAlchemy, enums, relaciones, constraints, índices, schemas Pydantic necesarios, configuración de Alembic, migración inicial y script de seed.

Los modelos deben representar las entidades principales del challenge:

- vehículos
- eventos de telemetría
- contadores de zonas
- anomalías
- misiones
- registros de mantenimiento

El seed debe inicializar los datos mínimos requeridos por el challenge:

- 50 vehículos
- aproximadamente 20 zonas definidas como constante

El prompt debe dejar claro que esta etapa todavía no debe implementar endpoints, servicios de negocio ni frontend.

La razón de esta división es validar primero el modelo de datos, porque varios requerimientos del challenge dependen de una base sólida: persistencia de eventos, conteo de zonas, anomalías, estado actual de vehículos y transición a fault.
```

### Prompt usado en Claude Code

```text
I am inside the root folder of the project: fleet-telemetry.

The initial structure already exists. Do not recreate the project and do not overwrite README.md.

Now implement only the backend database foundation.

Context:
- Backend: FastAPI, async SQLAlchemy 2.x, PostgreSQL, Alembic.
- Use the existing async SQLAlchemy setup.
- Frontend is not part of this task.
- Do not implement business logic or API endpoints yet.

Implement:

1. SQLAlchemy models

Create models for:
- Vehicle
- TelemetryEvent
- ZoneCounter
- Anomaly
- Mission
- MaintenanceRecord

Vehicle:
- id
- vehicle_id unique
- current_status: idle, moving, charging, fault
- battery_pct
- last_seen_at

TelemetryEvent:
- id
- vehicle_id
- timestamp
- lat
- lon
- battery_pct
- speed_mps
- status
- error_codes as JSON
- zone_entered nullable

ZoneCounter:
- id
- zone_id unique
- entry_count

Anomaly:
- id
- vehicle_id
- timestamp
- anomaly_type
- description
- telemetry_event_id nullable

Mission:
- id
- vehicle_id
- status: active, cancelled, completed
- started_at
- cancelled_at nullable

MaintenanceRecord:
- id
- vehicle_id
- created_at
- reason
- status: open, in_progress, resolved

Use proper relationships, indexes, timestamps, and constraints.

2. Pydantic schemas

Create request and response schemas for:
- telemetry ingestion
- vehicle list
- vehicle status update
- fleet state
- zone counts
- anomaly query response

Validate:
- vehicle_id format like v-01 to v-50
- status values
- battery_pct between 0 and 100
- zone_entered must be null or one of the hardcoded ZONES

3. Alembic

- Configure Alembic correctly with the models.
- Generate the initial migration.
- Make sure it works with PostgreSQL and async SQLAlchemy.

4. Seed data

Create a simple seed mechanism to initialize:
- 50 vehicles from v-01 to v-50
- 20 zone counters from backend/app/constants/zones.py
- optional active missions for vehicles

The seed must be safe to run multiple times.

Important:
- Do not implement API endpoint logic yet.
- Do not implement services yet.
- Do not build frontend.
- Keep the code simple and readable.

After implementation, show:
- changed files
- commands to run migrations
- commands to seed data
- assumptions made

Also append a short entry to docs/AI_LOG.md summarizing this prompt, your output, and assumptions.
```

### Qué generó Claude Code

Creó `app/models/enums.py` con los enums compartidos (`VehicleStatus`, `MissionStatus`, `MaintenanceStatus`); los seis modelos en estilo `Mapped`/`mapped_column` con FKs, índices y relaciones; cinco archivos de schemas Pydantic con `field_validator` para el formato de `vehicle_id` (`v-01`..`v-50`), la whitelist de zonas y el rango de `battery_pct`; la migración `alembic/versions/0001_initial_schema.py` escrita a mano (enums primero, tablas después en orden de dependencia); y un `seed.py` idempotente con `ON CONFLICT DO NOTHING`. Una decisión interesante fue que las tablas hijas referencian `vehicles.vehicle_id` (string) en vez del PK entero, para evitar un lookup en cada ingesta de telemetría.

### Cómo lo validé

Revisé el modelo de datos y las validaciones. La ejecución real de la migración se validó en la siguiente etapa, donde precisamente apareció un problema.

### Qué tuve que corregir

En la ejecución, la migración falló por enums duplicados; eso motivó la etapa siguiente.

### Resultado de la etapa

Modelos, schemas, migración inicial y seed implementados, listos para aplicarse contra PostgreSQL.

---

## 4. Corrección de enums duplicados en Alembic

### Qué requerimiento o problema estaba resolviendo

Para persistir cualquier cosa (telemetría, anomalías, estado de vehículos) primero necesitaba que la migración inicial corriera. Al aplicarla, PostgreSQL devolvió un error de tipo enum duplicado.

### Por qué tomé esta decisión

El error fue `DuplicateObjectError: type "vehiclestatus" already exists`. Mi interpretación: la migración creaba los tipos enum explícitamente al inicio y, además, las tablas volvían a intentar crearlos al usar `sa.Enum`. Decidí abordarlo con un prompt **acotado** que tocara únicamente el archivo de migración, sin permitir cambios en lógica de negocio, endpoints, frontend ni tests. Mantener el alcance mínimo es lo que hace que el diff sea auditable y evita que el modelo "arregle" cosas no relacionadas. Este tipo de detalle —enums de PostgreSQL creados dos veces— es un patrón conocido en migraciones asistidas por IA, y por eso exige revisión humana.

### Prompt refinado usado en ChatGPT

```text
Después de generar la migración inicial con Alembic apareció un error de PostgreSQL relacionado con enums duplicados.

El error indica que el enum vehiclestatus ya existe.

Quiero entender el problema y preparar un prompt específico para Claude Code que corrija solamente la migración.

Mi interpretación es que la migración está creando los tipos enum explícitamente y luego las tablas vuelven a intentar crear esos mismos enums al usar sa.Enum.

Necesito un prompt acotado para corregir únicamente el archivo de migración, evitando que los enums de PostgreSQL se creen dos veces.

El prompt no debe permitir cambios en lógica de negocio, endpoints, frontend ni tests. Solo debe corregir la migración y luego indicar qué comandos debo volver a ejecutar para validar la corrección.
```

### Prompt usado en Claude Code

```text
The Alembic migration failed with:

DuplicateObjectError: type "vehiclestatus" already exists

The migration is creating PostgreSQL enum types explicitly, but the tables also try to create the same enum type again.

Fix backend/alembic/versions/0001_initial_schema.py so PostgreSQL enum types are created only once.

Requirements:
- Keep the explicit enum creation at the beginning, or remove it, but do not create enums twice.
- For every sa.Enum used inside op.create_table, set create_type=False where needed.
- Apply the same fix for VehicleStatus, MissionStatus, and MaintenanceStatus.
- Do not change business logic.
- Do not implement endpoints.
- After fixing, tell me exactly which commands to run again.
```

### Qué generó Claude Code

Ajustó la migración para que cada tipo enum se cree una sola vez: la primera tabla crea el tipo y las referencias posteriores usan `create_type=False`, aplicándolo a `VehicleStatus`, `MissionStatus` y `MaintenanceStatus`.

### Cómo lo validé

Volví a ejecutar `alembic upgrade` hasta que la migración se aplicó sin errores sobre PostgreSQL (dentro de Docker Compose).

### Qué tuve que corregir

La corrección fue puntual y suficiente; no hubo iteraciones adicionales en esta etapa.

### Resultado de la etapa

La migración inicial aplicándose correctamente, con el schema completo creado en PostgreSQL.

---

## 5. Servicios y endpoints del backend

### Qué requerimiento o problema estaba resolviendo

Esta es la etapa que implementa el núcleo del challenge: ingesta de telemetría, detección de anomalías, contador de zonas seguro ante concurrencia, transición atómica a `fault`, estado agregado de flota y consulta filtrada de anomalías. Todos los endpoints del enunciado.

### Por qué tomé esta decisión

Mantuve la lógica de negocio en `services` y el acceso a datos en `repositories`, con rutas finas que solo reciben, validan y delegan. Expuse todo bajo `/api` desde el inicio para alinearlo con el proxy de Vite.

Tres decisiones aquí responden directamente al enunciado:

- **Contador de zonas atómico.** Como el challenge pide garantizar que *cada* entrada de zona se cuente aunque varios vehículos entren al mismo instante, no usé un *read-modify-write* en Python (un `SELECT` + `UPDATE` perdería conteos bajo concurrencia). Usé un único `INSERT ... ON CONFLICT DO UPDATE SET entry_count = entry_count + 1`, dejando que PostgreSQL serialice los incrementos a nivel de fila.
- **Transición a `fault` atómica.** Como el challenge pide cancelar la misión activa y crear el mantenimiento de forma atómica pensando en la concurrencia, concentré esa lógica en un service y una transacción: `SELECT ... FOR UPDATE` para bloquear la fila del vehículo, cancelar misiones activas, crear el registro de mantenimiento y actualizar el estado, todo con un solo commit; si algo falla, rollback de todo.
- **Estado de flota seguro.** El conteo por estado se resuelve con un único `GROUP BY`, una lectura consistente y segura bajo escrituras concurrentes.

Las reglas de anomalía las definí según el enunciado (que pedía justificarlas en el ADR): batería < 15 (riesgo de apagado a mitad de misión), `status == fault` (error explícito), `error_codes` no vacío (error reportado por el dispositivo) y `speed_mps > 8` (exceso del límite seguro de almacén). Dejé fuera autenticación y WebSockets a propósito: no eran parte del challenge y habrían distraído de los flujos principales.

### Prompt refinado usado en ChatGPT

```text
Ya tengo la base de datos, las migraciones y el seed. Ahora quiero preparar el siguiente prompt para Claude Code para implementar la lógica principal del backend y los endpoints requeridos por el challenge.

El backend debe exponer endpoints bajo el prefijo /api y debe mantener una separación clara entre rutas HTTP, servicios de negocio y acceso a datos.

El prompt debe pedir la implementación de:

- POST /api/telemetry
- GET /api/zones/counts
- GET /api/vehicles
- PATCH /api/vehicles/{vehicle_id}/status
- GET /api/fleet/state
- GET /api/anomalies

La lógica de negocio debe estar en services, y el acceso a datos en repositories cuando sea útil. Las rutas deben limitarse a recibir requests, validar datos y delegar trabajo.

La ingesta de telemetría debe:

- persistir el evento
- actualizar el estado actual del vehículo
- detectar anomalías
- incrementar el contador de zona si zone_entered viene informado

Las reglas de anomalía deben incluir:

- batería menor a 15
- estado fault
- error_codes no vacío
- velocidad mayor a 8

El contador de zonas debe ser seguro ante concurrencia usando una operación atómica en PostgreSQL, no un flujo read modify write en Python.

La transición a fault debe hacerse en una transacción: bloquear el vehículo, cancelar misión activa si existe, crear registro de mantenimiento y actualizar estado.

El prompt no debe tocar frontend todavía.
```

### Prompt usado en Claude Code

```text
Now implement the backend service logic and API endpoints.

Do not recreate the database models unless a small fix is necessary.
Do not work on the frontend yet.
Do not overwrite README.md.

Important:
- API routes must be exposed under /api because the frontend Vite proxy is configured for /api.
- Use the existing async SQLAlchemy setup.
- Keep business logic inside services.
- Keep database access inside repositories where useful.

Implement:

1. Telemetry ingestion

Endpoint:
POST /api/telemetry

Logic:
- Validate incoming telemetry payload.
- Save the telemetry event.
- Update the current vehicle state.
- Detect anomalies in real time.
- If zone_entered is not null, increment the zone counter safely.

Anomaly rules:
- battery_pct < 15 means LOW_BATTERY
- status == fault means VEHICLE_FAULT
- error_codes not empty means ERROR_CODE_REPORTED
- speed_mps > 8 means HIGH_SPEED

2. Zone counting

Endpoint:
GET /api/zones/counts

Requirements:
- Return counts for all 20 zones.
- Zone increment must be concurrency-safe.
- Do not use read-modify-write in Python.
- Use atomic PostgreSQL logic, preferably:
  INSERT ON CONFLICT DO UPDATE entry_count = entry_count + 1

3. Vehicle endpoints

Endpoints:
GET /api/vehicles
PATCH /api/vehicles/{vehicle_id}/status

Fault transition logic:
- If vehicle transitions to fault:
  - lock the vehicle row
  - cancel active mission
  - create maintenance record
  - commit everything inside one database transaction
- If any step fails, rollback everything.

4. Fleet state

Endpoint:
GET /api/fleet/state

Logic:
- Return per-status counts across all vehicles.
- Use database GROUP BY.
- Must be safe under concurrent updates.

5. Anomalies

Endpoint:
GET /api/anomalies

Support filters:
- vehicle_id
- since
- until
- limit

6. Keep it simple

Do not implement:
- authentication
- websockets
- background workers
- Kubernetes
- cloud deployment
- frontend logic

After implementation, show:
- changed files
- API endpoints created
- example curl commands
- assumptions made

Also append a short entry to docs/AI_LOG.md summarizing this prompt, your output, and assumptions.
```

### Qué generó Claude Code

Creó 6 repositorios (wrappers async finos, sin lógica de negocio), 5 servicios (toda la orquestación y reglas), y 5 routers (controladores finos, una llamada a servicio cada uno), y actualizó `main.py` para montar todos los routers bajo `/api`. El incremento de zona quedó con el upsert atómico; la transición a `fault` con `SELECT ... FOR UPDATE` y cancelación de misiones + mantenimiento en la misma transacción; el estado de flota con un solo `GROUP BY`; y un `session.flush()` tras el INSERT de telemetría para disponer del PK al crear la anomalía relacionada.

### Cómo lo validé

Probé cada endpoint con peticiones `curl`: ingesté telemetría y verifiqué que se persistiera y actualizara el estado del vehículo, que se generaran las anomalías esperadas, que el contador de zona subiera, que el `PATCH` a `fault` cancelara misiones y creara mantenimiento, y que `GET /api/fleet/state` devolviera el agregado correcto.

### Qué tuve que corregir

Nada en esta etapa. Quedó documentado el supuesto de que la ingesta actualiza el estado del vehículo con *last-write-wins* y que la tabla de telemetría es la fuente de verdad (el estado del vehículo es una caché).

### Resultado de la etapa

Backend funcional completo a nivel de API, cubriendo todos los endpoints del challenge.

---

## 6. Tests del backend

### Qué requerimiento o problema estaba resolviendo

El challenge valora la confiabilidad de los flujos críticos: concurrencia de zonas, atomicidad de `fault`, reglas de anomalía y agregación de flota. Necesitaba tests automatizados que probaran *esa* lógica, no solo respuestas HTTP triviales.

### Por qué tomé esta decisión

Prioricé los tests de backend sobre los de frontend porque ahí vive la lógica crítica (ingesta, anomalías, concurrencia, transacciones y agregación). Y decidí probar contra **PostgreSQL real** (una base de datos de test aislada), no contra mocks ni SQLite: la prueba de concurrencia del contador de zonas y el `SELECT FOR UPDATE` solo se validan de verdad con la semántica atómica real de PostgreSQL. Un mock daría una falsa sensación de seguridad justo en la parte más delicada del challenge.

### Prompt refinado usado en ChatGPT

```text
Ya tengo el backend implementado. Ahora quiero preparar el prompt para Claude Code para agregar tests automatizados del backend.

Los tests deben enfocarse en la lógica crítica del challenge, no solamente en respuestas HTTP simples.

Deben cubrir:

- creación de eventos de telemetría
- actualización del estado actual del vehículo
- detección de anomalías
- incremento de contadores de zona
- concurrencia cuando varios vehículos entran a la misma zona
- transición a fault
- cancelación de misión activa
- creación de maintenance record
- estado agregado de flota

Quiero usar pytest y pytest-asyncio.

Prefiero probar contra PostgreSQL real o una base de datos de test aislada, porque el challenge tiene requerimientos de concurrencia, transacciones y upserts que no se validan bien con mocks simples.

El prompt debe dejar claro que no debe modificar frontend y que solo debe cambiar implementación si los tests revelan un bug real.

También debe indicar cómo correr los tests y qué archivos fueron creados.
```

### Prompt usado en Claude Code

```text
Now add backend tests for the implemented functionality.

Do not change the main implementation unless tests reveal a necessary bug fix.
Do not work on the frontend.
Do not overwrite README.md.

Add tests for:

1. Telemetry event creation
- POST /api/telemetry creates a telemetry event.
- Vehicle current state is updated.

2. Anomaly detection
Test these cases:
- battery_pct < 15 creates LOW_BATTERY
- status == fault creates VEHICLE_FAULT
- error_codes not empty creates ERROR_CODE_REPORTED
- speed_mps > 8 creates HIGH_SPEED

3. Zone counter increment
- Sending telemetry with zone_entered increments the correct zone.
- Test concurrent increments for the same zone.
- The final count must match the number of submitted events.

4. Fault transition transaction
- PATCH /api/vehicles/{vehicle_id}/status to fault updates vehicle status.
- Active mission is cancelled.
- Maintenance record is created.
- These changes happen atomically.

5. Fleet state aggregation
- GET /api/fleet/state returns correct counts by status.

Requirements:
- Use pytest and pytest-asyncio.
- Use httpx AsyncClient if appropriate.
- Keep tests practical and readable.
- Prefer testing against a test database or isolated transaction setup.
- Document how to run tests.

After implementation, show:
- test files created
- commands to run tests
- any bugs found and fixed
- assumptions made

Also append a short entry to docs/AI_LOG.md summarizing this prompt, your output, and assumptions.
```

### Qué generó Claude Code

Creó `pytest.ini` (`asyncio_mode = auto`), un `tests/conftest.py` con fixtures compartidas, y cuatro archivos de test: `test_telemetry.py` (ingesta, actualización de estado, las cuatro reglas de anomalía con casos límite), `test_zones.py` (incremento y la prueba de concurrencia con `asyncio.gather` y 20 POSTs simultáneos a la misma zona), `test_vehicles.py` (transición a `fault` con verificación de atomicidad sobre vehículo, misión y mantenimiento) y `test_fleet.py` (agregación por estado).

### Cómo lo validé

Ejecuté `pytest` dentro del entorno de Docker. Probé explícitamente los casos límite (batería == 15.0 no marca, velocidad == 8.0 no marca).

### Qué tuve que corregir

La lógica de negocio era correcta, pero el primer enfoque de la infraestructura de tests —`drop_all`/`create_all` antes de cada test— resultó inestable con asyncpg y abrió una cadena de problemas async que resolví en las cuatro etapas siguientes. Esto me lleva a una explicación que conviene dar de una vez, porque atraviesa las etapas 6 a 10.

**Sobre los problemas de tests async (etapas 6 a 10), en simple:** la combinación era pytest + pytest-asyncio + SQLAlchemy async + asyncpg + PostgreSQL real. Los errores **no** eran de lógica de negocio, sino de **ciclo de vida async**. Una conexión async queda asociada a un *event loop* concreto; si otro loop intenta reutilizarla o cerrarla, aparecen errores como `Future attached to a different loop`. Además, hacer `drop_all` y `create_all` antes de cada test era demasiado agresivo y generaba inestabilidad a nivel de driver (`another operation is in progress`), y una fixture que mantenía una `AsyncSession` viva durante todo el test también fallaba al cerrarla. La solución final fue: crear el schema **una sola vez** por sesión, limpiar datos con **TRUNCATE** entre tests, usar **NullPool** para no reutilizar conexiones entre loops, y abrir **sesiones cortas** por consulta. Lo importante es que esto mantuvo los tests fuertes, porque siguieron corriendo contra PostgreSQL real.

### Resultado de la etapa

Suite de tests escrita y cubriendo la lógica crítica; la estabilización del runtime async vino a continuación.

---

## 7. Corrección del setup async de tests con NullPool y TEST_DATABASE_URL

### Qué requerimiento o problema estaba resolviendo

Sin una suite estable no podía validar de forma confiable los requerimientos de concurrencia y atomicidad del challenge. Tras escribir los tests, solo pasaba el primero; el resto fallaba.

### Por qué tomé esta decisión

Los errores (`Future attached to a different loop`, `another operation is in progress`) apuntaban a cómo se creaban, reutilizaban y cerraban las conexiones y sesiones async durante pytest, no a la lógica. Decidí corregir **solo la infraestructura de tests**, sin tocar lógica de negocio ni endpoints —una decisión deliberada: esconder el problema cambiando el código bajo prueba habría invalidado los tests—. Pedí una base de datos de test separada, mantener el soporte de `TEST_DATABASE_URL` (con default apuntando al Postgres de Docker), usar `NullPool` para evitar reusar conexiones asyncpg entre loops, y asegurar el cierre de cada `AsyncSession`. Quería estabilizar **sin** recurrir a mocks, para seguir validando PostgreSQL real.

### Prompt refinado usado en ChatGPT

```text
Los tests del backend fallan después del primer caso con errores relacionados con asyncpg, SQLAlchemy async y el event loop.

Aparecen errores como:

- Future attached to a different loop
- cannot perform operation: another operation is in progress

Quiero preparar un prompt para Claude Code que corrija únicamente la infraestructura de tests.

No quiero que cambie lógica de negocio ni endpoints.

El problema parece estar en cómo se crean, reutilizan o cierran conexiones y sesiones asíncronas durante la ejecución de pytest.

El prompt debe pedir una base de datos separada de tests, mantener soporte para TEST_DATABASE_URL y considerar NullPool para evitar reutilización problemática de conexiones asyncpg entre event loops.

También debe asegurar que las sesiones AsyncSession se cierren correctamente.

La intención es estabilizar los tests sin esconder los problemas usando mocks, porque quiero seguir validando PostgreSQL real.
```

### Prompt usado en Claude Code

```text
The backend tests are now connecting to the test database, but only the first test passes. The rest fail during reset_db with:

RuntimeError: got Future attached to a different loop

and also:

asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress

Fix the async test setup in backend/tests/conftest.py.

Requirements:
- Do not change application business logic.
- Do not change API endpoints.
- Fix only the test infrastructure unless strictly necessary.
- Avoid reusing asyncpg connections across pytest event loops.
- Use SQLAlchemy NullPool for the test engine, or create and dispose the async engine safely per test/session.
- Ensure every AsyncSession is properly closed.
- Ensure reset_db can drop_all and create_all before every test without event loop conflicts.
- Keep TEST_DATABASE_URL support.
- Default TEST_DATABASE_URL should work inside Docker:
  postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test
- Update pytest.ini if needed to set asyncio fixture loop scope explicitly.
- After fixing, tell me the exact command to rerun tests.
```

### Qué generó Claude Code

En `pytest.ini` agregó `asyncio_default_fixture_loop_scope = session` para forzar un único event loop en toda la sesión, y en `conftest.py` añadió `poolclass=NullPool` al engine de test y cambió el host por defecto de `TEST_DATABASE_URL` a `postgres` (el hostname del servicio Docker).

### Cómo lo validé

Volví a correr `pytest`. Las conexiones ya no cruzaban loops.

### Qué tuve que corregir

`NullPool` por sí solo fue **insuficiente**: el error "another operation is in progress" seguía apareciendo porque `drop_all` emite múltiples sentencias DDL sobre la misma conexión mientras asyncpg considera una sentencia previa aún en vuelo. Eso motivó la siguiente etapa.

### Resultado de la etapa

Avance parcial: el cruce de loops quedó resuelto, pero la limpieza con `drop_all`/`create_all` seguía siendo inestable.

---

## 8. Corrección de limpieza de tests con TRUNCATE

### Qué requerimiento o problema estaba resolviendo

El mismo objetivo: una suite estable y determinista para validar concurrencia y atomicidad. El fallo restante estaba en la limpieza de la base entre tests.

### Por qué tomé esta decisión

Decidí cambiar la estrategia de limpieza: en lugar de borrar y recrear todo el schema antes de cada test, crear el schema **una sola vez** por sesión y, antes de cada test, limpiar los datos con `TRUNCATE ... RESTART IDENTITY CASCADE`. `TRUNCATE` es una única sentencia atómica por conexión, sin posibilidad de *interleaving* a nivel de driver, a diferencia de los múltiples DDL de `drop_all`. Después de truncar, reinsertaba la data base necesaria (los 50 vehículos y las zonas) para que cada test arrancara limpio. Mantuve PostgreSQL real, NullPool y `TEST_DATABASE_URL`, sin tocar lógica ni endpoints.

### Prompt refinado usado en ChatGPT

```text
Los tests siguen fallando durante la limpieza de base de datos entre pruebas.

El problema ocurre cuando se usa drop_all y create_all antes de cada test.

Quiero preparar un prompt para Claude Code que corrija solamente la infraestructura de tests.

En lugar de eliminar y recrear todo el schema antes de cada test, el prompt debe pedir que el schema se cree una sola vez por sesión de tests.

Antes de cada test se debe limpiar la data usando TRUNCATE RESTART IDENTITY CASCADE.

Luego se debe reinsertar la data base necesaria para que cada test arranque limpio, como los 50 vehículos y las zonas.

No debe cambiar lógica de negocio ni endpoints.

Debe mantener:

- PostgreSQL real
- NullPool
- TEST_DATABASE_URL
- aislamiento determinístico entre tests

El objetivo es reducir problemas de ciclo de vida async sin perder rigor en las pruebas.
```

### Prompt usado en Claude Code

```text
The tests still fail in reset_db with:

asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress

The failure happens during:

await conn.run_sync(Base.metadata.drop_all)

Do not change application business logic.
Fix only the test infrastructure.

Current approach using Base.metadata.drop_all/create_all before every test is unstable with asyncpg.

Refactor backend/tests/conftest.py to avoid drop_all/create_all per test.

Requirements:
- Keep TEST_DATABASE_URL support.
- Keep default Docker test URL:
  postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test
- Create the database schema once per test session.
- Before each test, clean data using TRUNCATE ... RESTART IDENTITY CASCADE instead of drop_all/create_all.
- Seed required baseline data before each test when needed:
  - vehicles v-01 to v-50
  - zone counters for all hardcoded zones
- Ensure all AsyncSession instances are properly closed.
- Use NullPool or safe engine disposal.
- Keep tests isolated and deterministic.
- Do not modify API endpoints.
- Do not modify business services.

After fixing, tell me the exact command to rerun the tests.
```

### Qué generó Claude Code

Reemplazó el `drop_all`/`create_all` por test por una creación de schema de alcance de sesión y un `TRUNCATE ... RESTART IDENTITY CASCADE` por test; cada módulo de test siembra sus filas necesarias sobre las tablas recién vaciadas.

### Cómo lo validé

Volví a ejecutar `pytest`. La limpieza de datos quedó estable.

### Qué tuve que corregir

Apareció un nuevo síntoma, ahora en el *teardown* del fixture `db` al cerrar/hacer rollback de la `AsyncSession`. Eso llevó a la siguiente etapa.

### Resultado de la etapa

Limpieza de datos estable; pendiente el ciclo de vida de la sesión usada para aserciones.

---

## 9. Corrección del teardown de AsyncSession

### Qué requerimiento o problema estaba resolviendo

Seguir avanzando hacia una suite verde y determinista. El problema se había desplazado del *setup* al *teardown*.

### Por qué tomé esta decisión

Los errores `Future attached to a different loop` aparecían al cerrar la sesión e intentar el rollback en `async with _TestSession() as session`. Decidí corregir solo `conftest.py` (y `pytest.ini` si hacía falta): hacer que pytest-asyncio usara un loop consistente para tests y fixtures, evitar que una sesión async viviera demasiado o se cerrara desde un loop distinto, y usar cierre explícito de sesiones. Sin tocar lógica de aplicación, endpoints ni frontend.

### Prompt refinado usado en ChatGPT

```text
Los tests mejoraron, pero ahora fallan durante el teardown de la fixture de base de datos.

El error ocurre cuando se intenta cerrar o hacer rollback de una AsyncSession.

Quiero preparar un prompt para Claude Code para corregir backend/tests/conftest.py y pytest.ini si es necesario.

El prompt debe enfocarse solo en infraestructura de tests.

Debe evitar que una sesión async viva demasiado tiempo o se cierre desde un event loop diferente.

Debe usar cierre explícito de sesiones y revisar la configuración de pytest-asyncio para que tests y fixtures usen un ciclo de ejecución consistente.

No debe tocar lógica de aplicación, endpoints ni frontend.
```

### Prompt usado en Claude Code

```text
The tests improved, but now many errors happen during teardown of the db fixture.

Error:

RuntimeError: got Future attached to a different loop

Location:

tests/conftest.py:92
async with _TestSession() as session

The error happens when AsyncSession closes and tries to rollback.

Fix only backend/tests/conftest.py and pytest.ini if needed.
Do not change application logic.
Do not change API endpoints.
Do not change test assertions unless absolutely necessary.

Requirements:
- Make pytest-asyncio use a consistent event loop for both async tests and async fixtures.
- If needed, set both fixture and test loop scope to session in pytest.ini.
- Refactor the db fixture to avoid `async with _TestSession()` if it causes teardown loop issues.
- Use explicit session creation and explicit close:
  session = _TestSession()
  try:
      yield session
  finally:
      await session.rollback()
      await session.close()
- Ensure client fixture also closes cleanly in the same loop.
- Keep NullPool.
- Keep TRUNCATE reset_db approach.
- Keep TEST_DATABASE_URL default as:
  postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test

After fixing, give me the exact command to rerun tests.
```

### Qué generó Claude Code

Sustituyó el `async with` del fixture `db` por creación explícita con `try/finally` (rollback + close) y alineó el cierre del `client` en el mismo loop.

### Cómo lo validé

Volví a correr `pytest`. El teardown mejoró.

### Qué tuve que corregir

Aún así, el rollback durante el teardown de una sesión de larga vida seguía disparando el error de loop en algunos casos. La causa de fondo era mantener una `AsyncSession` viva todo el test; eso me llevó a la solución definitiva.

### Resultado de la etapa

Teardown más estable, pero todavía dependiente de una sesión de larga vida.

---

## 10. Fixture de base de datos como factory de sesiones cortas

### Qué requerimiento o problema estaba resolviendo

Cerrar definitivamente los problemas de ciclo de vida async para tener una suite confiable que respaldara los requerimientos de concurrencia y atomicidad del challenge.

### Por qué tomé esta decisión

En vez de seguir peleando con el ciclo de vida de una sesión larga, decidí **eliminar** la sesión larga. Cambié el fixture `db` para que, en lugar de entregar una `AsyncSession` viva durante todo el test, entregara una *factory*/helper que abre sesiones cortas solo cuando se necesitan para una consulta o aserción, abriéndolas y cerrándolas explícitamente dentro del test. Así cada conexión vive y muere dentro del mismo loop, sin rollback diferido. Que las correcciones fueran prompts puntuales encadenados (y no una reescritura amplia) me permitió aislar cada causa de forma incremental. Mantuve TRUNCATE, NullPool, `TEST_DATABASE_URL` y PostgreSQL real.

### Prompt refinado usado en ChatGPT

```text
Los tests todavía fallan por problemas de event loop al cerrar la sesión de base de datos.

Quiero preparar un prompt para Claude Code que cambie el enfoque de la fixture db.

En lugar de entregar una AsyncSession larga durante todo el test, debe entregar una factory o helper que permita abrir sesiones cortas solo cuando se necesiten para una consulta o una aserción.

Cada sesión debe abrirse, usarse y cerrarse explícitamente dentro del test.

El prompt debe eliminar rollbacks innecesarios durante teardown y mantener:

- TRUNCATE entre tests
- NullPool
- TEST_DATABASE_URL
- PostgreSQL real
- aislamiento entre tests

Si los tests existentes esperan db como AsyncSession, Claude Code debe actualizarlos.

No debe modificar la lógica de negocio.

La intención es mantener pruebas realistas con PostgreSQL, pero evitando errores provocados por sesiones async de vida larga.
```

### Prompt usado en Claude Code

```text
The tests still fail during teardown of the db fixture.

Current error:

RuntimeError: got Future attached to a different loop

Location:

tests/conftest.py:101
await session.rollback()

There are also logs saying the event loop is closed while closing asyncpg connections.

Fix the test infrastructure.

Requirements:
- Do not change application business logic.
- Do not change API endpoints.
- Avoid keeping a long-lived AsyncSession open through the whole test.
- Refactor the db fixture so it does not yield a persistent AsyncSession that needs rollback during teardown.
- Prefer a helper fixture/factory that opens a short-lived AsyncSession per query or per assertion and closes it immediately.
- If test files currently expect `db: AsyncSession`, update the tests accordingly.
- Keep the TRUNCATE reset_db approach.
- Keep NullPool.
- Keep TEST_DATABASE_URL default as:
  postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test
- Remove unnecessary rollback during teardown.
- Ensure all sessions are explicitly closed before the test finishes.
- After fixing, tell me the exact command to rerun tests.
```

### Qué generó Claude Code

Convirtió `db` en un factory de sesiones de corta vida (abrir/cerrar por consulta) y ajustó los archivos de test que esperaban `db: AsyncSession`, eliminando el rollback innecesario en teardown.

### Cómo lo validé

Ejecuté la suite completa: **30 tests pasando**, de forma estable y repetible.

### Qué tuve que corregir

Esta fue la última de las cuatro rondas async (etapas 7 a 10). La lección que me quedó: gran parte de los errores en tests async vienen del ciclo de vida de conexiones y sesiones, no de la lógica de negocio.

### Resultado de la etapa

Infraestructura de tests estable y determinista, con los 30 tests en verde, validando concurrencia, atomicidad, reglas de anomalía y agregación contra PostgreSQL real.

---

## 11. Integración API del frontend

### Qué requerimiento o problema estaba resolviendo

El challenge pide un dashboard React + TypeScript que muestre datos en vivo. Antes de construir la UI, necesitaba una capa de integración que consumiera el backend de forma verificable.

### Por qué tomé esta decisión

Dividí el frontend en dos: primero la capa de integración (tipos, service, hooks) y después el dashboard visual. Construir primero los tipos y el service fija el contrato con el backend y aísla la lógica de datos de la presentación; un `App.tsx` mínimo de prueba me permite confirmar que los datos cargan antes de invertir en UI.

Aquí materialicé la decisión de **polling sobre WebSockets**, que el challenge permitía justificar. Con 50 vehículos emitiendo a 1 Hz, los datos cambian varias veces dentro de cualquier intervalo de 2 segundos, así que un polling cada 2 s es suficiente y mucho más simple: no necesita lógica de reconexión ni estado de *fanout* en el servidor. El trade-off es explícito: si el requerimiento fuera menor latencia (sub-segundo) o muchísimos más vehículos, evaluaría Server-Sent Events o WebSockets. Para esta escala y alcance, polling era la elección correcta. Las llamadas usan rutas relativas `/api` para funcionar con el proxy de Vite.

### Prompt refinado usado en ChatGPT

```text
Ya tengo el backend funcionando y los tests pasando. Ahora quiero preparar el prompt para Claude Code para implementar la integración del frontend con el backend.

No quiero construir todavía el dashboard final. Primero quiero una capa de integración simple y verificable.

El prompt debe pedir:

- tipos TypeScript
- services/api.ts
- hooks de polling
- hook useFleetData
- integración básica en App.tsx para comprobar que los datos cargan

El frontend debe consumir estos endpoints:

- GET /api/vehicles
- GET /api/fleet/state
- GET /api/zones/counts
- GET /api/anomalies

Debe usar rutas relativas con /api para funcionar con el proxy de Vite.

Debe implementar polling cada 2 segundos, porque el challenge permite polling o WebSockets y, para esta escala y alcance, polling es suficiente y más simple.

Debe manejar loading, error y data.

No debe modificar backend.
```

### Prompt usado en Claude Code

```text
Now implement the frontend API integration layer.

Context:
- Backend is already implemented and tested.
- Backend endpoints are exposed under /api.
- Frontend is React + TypeScript + Vite.
- Do not modify backend files.
- Do not overwrite README.md.
- Do not build the final dashboard UI yet.
- Keep the implementation simple, readable, and practical.

Use the existing frontend structure. Place files here:

- TypeScript types in frontend/src/types/
- API service in frontend/src/services/api.ts
- Polling hooks in frontend/src/hooks/
- Reusable UI components in frontend/src/components/
- Main screen composition in frontend/src/App.tsx

Do not create a second React project.
Do not move the frontend root.
Do not modify backend files.

Implement:

1. TypeScript types

Create types for:
- Vehicle
- VehicleStatus
- Anomaly
- FleetState
- ZoneCount
- ZoneCountResponse

Use the backend response shapes already implemented.

2. API service layer

Create a frontend API service that calls:

GET /api/vehicles
GET /api/fleet/state
GET /api/zones/counts
GET /api/anomalies

Requirements:
- Use fetch, no extra libraries.
- Centralize API calls in frontend/src/services/api.ts.
- Handle HTTP errors clearly.
- Use relative /api paths so Vite proxy works.

3. Polling hooks

Create reusable hooks:

- usePolling
- useFleetData

useFleetData should periodically load:
- vehicles
- fleet state
- zone counts
- anomalies

Requirements:
- Poll every 2 seconds.
- Expose loading, error, and data states.
- Avoid memory leaks by cleaning intervals.
- Do not implement websockets.
- Keep polling choice consistent with the ADR.

4. App integration

Update App.tsx only enough to prove data loads.
For now, show:
- loading state
- error state
- count of vehicles
- fleet state JSON
- zone count JSON

Do not create the final dashboard layout yet.

After implementation, show:
- changed files
- what each file does
- how to run the frontend
- any assumptions made

Also append a short entry to docs/AI_LOG.md summarizing this prompt, output, and assumptions.
```

### Qué generó Claude Code

Creó `types/index.ts` con interfaces alineadas a los schemas del backend (incluido el envelope `{ zones: ZoneCount[] }`), `services/api.ts` con cuatro wrappers tipados de `fetch` y un helper `apiFetch<T>` que lanza ante respuestas no-ok, `hooks/usePolling.ts` con patrón `useRef` para no reprogramar el intervalo al cambiar la identidad del callback, `hooks/useFleetData.ts` que dispara las cuatro fetches en paralelo con `Promise.all`, y un `App.tsx` mínimo que muestra loading/error, conteo de vehículos y el JSON de flota y zonas. También ajustó `vite.config.ts` (lo detallo en la siguiente etapa).

### Cómo lo validé

Abrí el frontend en el navegador y confirmé que los datos cargaban y se refrescaban cada 2 segundos, y que las llamadas llegaban realmente al backend.

### Qué tuve que corregir

El ajuste relevante fue el del proxy de Vite, que detallo enseguida como su propia etapa por su importancia.

### Resultado de la etapa

Capa de datos del frontend funcional, consumiendo el backend real vía polling.

---

## 12. Validación o corrección del proxy de Vite

### Qué requerimiento o problema estaba resolviendo

Antes de construir el dashboard final quería asegurarme de que el contrato de rutas entre frontend y backend fuera correcto. Si las llamadas no llegan a los endpoints reales, el dashboard del challenge (lista de vehículos, estado de flota, zonas, anomalías) simplemente no tendría datos.

> Nota: en `PROMPTS_USED.md` esta verificación no figura como un prompt independiente de Claude Code; el ajuste del proxy ocurrió como parte de la implementación de la capa de integración. Esta etapa se reconstruyó desde el contexto disponible y se documenta por separado por su importancia.

### Por qué tomé esta decisión

El backend expone todas sus rutas bajo `/api`, y el frontend llama rutas relativas como `/api/vehicles` que Vite reenvía al backend en desarrollo. El problema, en simple: el frontend llamaba a `/api/vehicles`; el proxy de Vite reenvía esas rutas al backend; pero si el proxy **quitaba** el prefijo `/api` (con un `rewrite`), el backend recibía `/vehicles`, y `/vehicles` no existe → 404. Por eso el proxy debía **conservar** `/api`. Esto era crítico porque el dashboard depende de `/api/vehicles`, `/api/fleet/state`, `/api/zones/counts` y `/api/anomalies`. La lección que me llevo: el contrato de rutas entre frontend y backend hay que verificarlo, no asumirlo.

### Prompt refinado usado en ChatGPT

```text
Antes de construir el dashboard final, quiero revisar el contrato entre frontend y backend.

El backend expone las rutas bajo el prefijo /api.

El frontend usa Vite proxy durante desarrollo y las llamadas del frontend usan rutas relativas como /api/vehicles.

Quiero asegurarme de que el proxy no elimine el prefijo /api al reenviar la request al backend, porque si lo elimina, el backend recibiría rutas como /vehicles y esas rutas no existen.

Prepara una instrucción clara para Claude Code para revisar vite.config.ts y corregirlo si es necesario.

No debe tocar backend.

Debe mantener las llamadas del frontend usando rutas relativas /api.

La idea es asegurar que el dashboard consuma realmente los endpoints correctos del backend.
```

### Prompt usado en Claude Code

Esta verificación no tuvo un prompt independiente de Claude Code en `PROMPTS_USED.md`; el ajuste del proxy se aplicó dentro del prompt de la capa de integración del frontend (etapa 11). Por lo tanto, **esta etapa se reconstruyó desde el contexto disponible**: la instrucción efectiva fue revisar `vite.config.ts`, eliminar el `rewrite` que quitaba `/api` y conservar el prefijo intacto, sin tocar el backend.

### Qué generó Claude Code

Eliminó del `vite.config.ts` el `rewrite` que reescribía `/api/vehicles` → `/vehicles` antes de reenviar a `http://backend:8000`. Tras el cambio, Vite reenvía `/api/*` tal cual a `http://backend:8000/api/*`.

### Cómo lo validé

Verifiqué en el navegador (y en la pestaña de red) que las peticiones llegaban a `/api/...` y devolvían 200 con datos reales, en lugar de 404.

### Qué tuve que corregir

La corrección fue justamente eliminar el `rewrite`; con eso el contrato quedó correcto.

### Resultado de la etapa

El frontend consumiendo de verdad los endpoints `/api/*` del backend, listo para construir la UI encima.

---

## 13. Dashboard UI del frontend

### Qué requerimiento o problema estaba resolviendo

El challenge pide un dashboard que muestre la lista viva de los 50 vehículos con estado y batería, la anomalía más reciente por vehículo y los contadores de zona actualizándose en vivo. Esta etapa construye esa interfaz sobre la capa de integración ya validada.

### Por qué tomé esta decisión

Construí la UI solo después de tener la capa de datos probada, para que el dashboard consumiera un contrato ya verificado. Usé CSS plano sin librerías de UI externas: en un challenge, agregar una librería de componentes solo añade peso y dependencias sin aportar a lo que se evalúa. La UI debía ser simple, profesional y legible, y sobre todo demostrar que no está *hardcodeada*, sino consumiendo datos reales del backend con polling cada 2 segundos.

### Prompt refinado usado en ChatGPT

```text
Ya tengo la capa de integración del frontend con el backend. Ahora quiero preparar el prompt para Claude Code para construir el dashboard visual.

Debe usar los hooks, services y tipos existentes.

El dashboard debe mostrar lo que pide el challenge:

- resumen del estado agregado de flota
- lista de 50 vehículos
- estado actual de cada vehículo
- batería actual
- última anomalía por vehículo
- contadores de entrada por zona
- timestamp de última actualización

Debe crear componentes separados y simples, por ejemplo:

- FleetSummary
- VehicleTable o VehicleList
- ZoneCounts
- StatusBadge
- AnomalyBadge
- LoadingState
- ErrorState

Debe seguir usando polling cada 2 segundos.

No debe usar librerías UI externas.

No debe modificar backend.

Debe mantener una UI simple, profesional y legible, suficiente para demostrar que el frontend no está hardcodeado y que consume datos reales del backend.
```

### Prompt usado en Claude Code

```text
Now build the React dashboard UI using the frontend API integration already implemented.

Context:
- Backend is working.
- Frontend API service and polling hooks already exist.
- Do not modify backend files.
- Do not overwrite README.md.
- Keep the dashboard simple, clean, and readable.
- No authentication.
- No websockets.
- Use polling.

Implement the dashboard:

1. Main layout

Update App.tsx and create components as needed.

Suggested components:
- FleetSummary
- VehicleList
- VehicleCard or VehicleTable
- ZoneCounts
- AnomalyBadge
- StatusBadge
- ErrorState
- LoadingState

2. Fleet summary

Show current aggregate fleet state:

- idle
- moving
- charging
- fault
- total

Use GET /api/fleet/state through the existing hook.

3. Vehicle list

Show all vehicles with:

- vehicle_id
- current_status
- battery_pct
- last_seen_at
- latest anomaly if available

Requirements:
- Make status visually easy to identify.
- Show null battery as "No data yet".
- Sort vehicles by vehicle_id.
- Keep it readable for 50 vehicles.

4. Latest anomaly per vehicle

Use the vehicle response if it already includes latest_anomaly.
If not available, use the anomalies endpoint data already loaded by the hook.

Show:
- anomaly type
- message or reason
- timestamp

5. Zone counts

Show all zone counters from GET /api/zones/counts.

Requirements:
- Display zone_id and entry_count.
- Sort by entry_count descending or zone_id ascending.
- Make charging zones easy to notice.

6. Polling behavior

Use the existing polling hook.
Dashboard should update every 2 seconds.
Show a small "last updated" timestamp.

7. UX states

Handle:
- loading
- error
- empty data
- normal state

8. Styling

Use plain CSS or simple CSS modules.
No UI library.
Keep it professional and lightweight.

After implementation, show:
- changed files
- components created
- how the dashboard uses polling
- how to run frontend and backend together
- any assumptions made

Also append a short entry to docs/AI_LOG.md summarizing this prompt, output, and assumptions.
```

### Qué generó Claude Code

Creó `App.css` (stylesheet completo con variables CSS, grid de resumen, tabla con headers sticky, colores de badges, spinner y breakpoints responsive) y los componentes `LoadingState`, `ErrorState`, `StatusBadge`, `AnomalyBadge`, `FleetSummary`, `VehicleTable` y `ZoneCounts`. Amplió `useFleetData.ts` con `lastUpdated: Date | null` y compuso todo en `App.tsx`: loading → `LoadingState`; error de primera carga → `ErrorState`; estado normal → dashboard con banner de error en línea para fallos de polling posteriores (los datos *stale* permanecen visibles mientras el backend se recupera). La anomalía más reciente viene directo de `VehicleResponse`, sin necesidad de un *join* en el cliente.

### Cómo lo validé

Revisé el dashboard en el navegador con los 50 vehículos, y validé el polling cada 2 segundos observando que el timestamp de "última actualización" cambiaba y que los datos se refrescaban en vivo.

### Qué tuve que corregir

Nada relevante en esta etapa.

### Resultado de la etapa

Dashboard en vivo completo y funcional, cubriendo lo que pide el challenge: flota agregada, lista de vehículos con estado/batería/última anomalía y contadores de zona.

---

## 14. Documentación final y cleanup

### Qué requerimiento o problema estaba resolviendo

El challenge valora el ADR y el AI log tanto como el código, y pide un README que explique cómo correr el proyecto. Esta etapa trata la documentación como un entregable de primera clase y deja el repositorio listo para entrega.

### Por qué tomé esta decisión

Dejé la documentación y el cleanup para el final a propósito: solo entonces reflejan el estado real del código. Pedí actualizar `README.md`, `docs/ADR.md` y `docs/AI_LOG.md`, con instrucciones claras para levantar Docker Compose, correr migraciones, sembrar datos, ejecutar tests y probar endpoints con `curl`, y con la explicación de las decisiones técnicas principales (FastAPI, PostgreSQL, polling, reglas de anomalía, contador de zonas concurrency-safe, transición `fault` atómica y limitaciones). Insistí en mantenerlo honesto, sin inventar detalles, porque la documentación debe corresponder al código. También pedí limpiar detalles obsoletos, como el campo `version` de `docker-compose.yml`.

### Prompt refinado usado en ChatGPT

```text
Ya tengo backend, tests y frontend funcionando. Ahora quiero preparar un prompt para Claude Code para hacer documentación final y limpieza del proyecto.

El prompt debe revisar y actualizar:

- README.md
- docs/ADR.md
- docs/AI_LOG.md

Debe agregar instrucciones claras para:

- levantar Docker Compose
- ejecutar migraciones
- ejecutar seed
- correr tests
- abrir backend
- abrir frontend
- probar endpoints con curl

Debe explicar las decisiones técnicas principales:

- FastAPI
- PostgreSQL
- polling
- reglas de anomalías
- contador de zonas seguro ante concurrencia
- transición fault atómica
- limitaciones del proyecto

También debe limpiar detalles obsoletos o confusos, como el campo version de docker-compose si existe.

No debe cambiar lógica de negocio salvo que encuentre un bug evidente.

La intención es dejar el proyecto listo para entrega, con documentación suficiente para que un revisor pueda levantarlo, probarlo y entender las decisiones.
```

### Prompt usado en Claude Code

```text
Now perform final documentation and cleanup for the fullstack take-home project.

Context:
- Backend is implemented and tested.
- Frontend dashboard is implemented.
- Docker Compose is available.
- Do not change business logic unless you find a clear bug.
- Do not add unnecessary features.
- Keep the project suitable for a take-home challenge submission.

Tasks:

1. README.md

Update README.md with:

- project overview
- tech stack
- architecture summary
- how to run with Docker Compose
- how to run backend migrations
- how to seed data
- how to run backend tests
- how to open the API docs
- how to open the frontend dashboard
- example curl commands for main endpoints
- known limitations

Make sure commands are correct for this project.

2. ADR

Review docs/ADR.md and update it so it clearly explains:

- PostgreSQL decision
- FastAPI decision
- polling over websockets
- anomaly detection rules
- concurrency-safe zone counter
- fault transition transaction strategy
- what would change at larger scale
- what was deliberately left out

Keep it around one page if possible.

3. AI_LOG

Review docs/AI_LOG.md and make sure it includes:

- meaningful prompts used
- summary of outputs
- corrections made
- final reflection with 3 to 5 bullets

Do not invent fake details.
Keep it honest.

4. Cleanup

Check for:

- obsolete Docker Compose version warning
- unused files
- broken commands
- missing env documentation
- unclear comments
- obvious formatting issues

If docker-compose.yml still has the obsolete version field, remove it.

5. Final verification commands

Provide the exact commands to verify:

- containers start
- migrations run
- seed runs
- backend tests pass
- frontend opens
- API health works

After cleanup, show:
- files changed
- final run commands
- final project status
- any remaining limitations
```

### Qué generó Claude Code

Reescribió `README.md` (overview, tabla de stack, diagrama de arquitectura, quick-start de 5 pasos, instrucciones de test, tabla de referencia de API, ejemplos `curl`, árbol del proyecto y limitaciones); reescribió `docs/ADR.md` cubriendo las decisiones (PostgreSQL, FastAPI + async, polling, reglas de anomalía, contador atómico, transacción de `fault`), supuestos, plan de escala y omisiones deliberadas; completó `docs/AI_LOG.md`; y eliminó el campo `version: "3.9"` obsoleto de `docker-compose.yml`.

### Cómo lo validé

Verifiqué que los comandos documentados fueran correctos: arranque de contenedores, migraciones, seed, ejecución de tests, apertura del frontend y health del API. Durante la revisión contrasté el ADR contra el código y corregí el umbral de `HIGH_SPEED` (el ADR describía una condición distinta a la real `> 8.0`), además de completar áreas de decisión que faltaban. Es justo la clase de detalle que la documentación generada con IA necesita que un humano verifique contra el código.

### Qué tuve que corregir

El umbral de `HIGH_SPEED` en el ADR y algunas áreas de decisión incompletas; ambos ajustados durante la revisión.

### Resultado de la etapa

Documentación completa y coherente con el código, y el proyecto listo para entrega.

---

## 15. Documentación de estudio del proyecto

### Qué requerimiento o problema estaba resolviendo

Esta etapa no corresponde a un requerimiento del challenge, sino a mi propia preparación: generar documentación adicional para estudiar y defender el proyecto en una entrevista técnica. Es documentación pura, sin cambios al código.

### Por qué tomé esta decisión

Quería un set de documentos que explicaran la arquitectura, el flujo de backend y frontend, la estrategia de tests y el razonamiento técnico detrás de las decisiones (por qué PostgreSQL, por qué polling, cómo se resolvió la concurrencia del contador, cómo se logró la transición atómica a `fault`, qué se dejó fuera por ser un challenge y qué cambiaría a mayor escala). Tener esto escrito me permite reconstruir y defender el proyecto con rapidez.

### Prompt refinado usado en ChatGPT

```text
Quiero generar documentación adicional para estudiar y defender el proyecto en una entrevista técnica.

Prepara un prompt para Claude Code que cree documentos dentro de docs.

Esta tarea debe ser solo documentación. No debe modificar código.

Debe crear documentos como:

- PROJECT_MAP.md
- BACKEND_WALKTHROUGH.md
- FRONTEND_WALKTHROUGH.md
- TESTING_AND_DEBUGGING_WALKTHROUGH.md
- SENIOR_DEFENSE_GUIDE.md

La documentación debe explicar:

- arquitectura del proyecto
- flujo del backend
- flujo del frontend
- estrategia de pruebas
- problemas encontrados
- decisiones técnicas senior
- por qué se eligió PostgreSQL
- por qué se eligió polling
- cómo se resolvió la concurrencia del contador de zonas
- cómo se resolvió la transición atómica a fault
- qué se dejó fuera por ser un challenge
- qué cambiaría a mayor escala

Debe ser documentación concisa, específica para este proyecto y útil para preparar una defensa técnica.
```

### Prompt usado en Claude Code

```text
You are inside the root folder of the existing fleet-telemetry project.

Do not modify application code.
Do not modify backend logic.
Do not modify frontend logic.
Do not modify tests.
Your task is documentation only.

Goal:
Create a concise but complete technical walkthrough that helps a senior engineer understand and defend this project end to end.

Create these files inside docs:

1. docs/PROJECT_MAP.md
2. docs/BACKEND_WALKTHROUGH.md
3. docs/FRONTEND_WALKTHROUGH.md
4. docs/TESTING_AND_DEBUGGING_WALKTHROUGH.md
5. docs/SENIOR_DEFENSE_GUIDE.md

Requirements for docs/PROJECT_MAP.md:
- Explain the project goal in plain terms.
- Explain the runtime architecture.
- Explain the main request flows.
- Include a simple diagram using text or Mermaid.
- Explain which files matter most and which files are secondary.
- Explain the recommended reading order for understanding the project quickly.

Requirements for docs/BACKEND_WALKTHROUGH.md:
- Explain the backend by layers:
  - main
  - api routes
  - schemas
  - services
  - repositories
  - models
  - constants
  - migrations
  - seed script
- For each important backend file, explain:
  - what it does
  - why it exists
  - what part of the challenge requirement it satisfies
- Explain the complete telemetry ingestion flow.
- Explain anomaly detection.
- Explain zone counter concurrency safety.
- Explain the fault transition transaction.
- Explain why PostgreSQL was used instead of SQLite.
- Explain what parts are intentionally simple because this is a take-home challenge.

Requirements for docs/FRONTEND_WALKTHROUGH.md:
- Explain the frontend architecture:
  - App.tsx
  - hooks
  - services
  - types
  - components
  - CSS
- Explain how polling works.
- Explain how the frontend consumes backend data.
- Explain how each dashboard section maps to backend endpoints.
- Explain how loading, error, and stale data behavior works.
- Explain the Vite proxy and why /api must not be stripped.

Requirements for docs/TESTING_AND_DEBUGGING_WALKTHROUGH.md:
- Explain the backend test strategy.
- Explain what each test file validates.
- Explain why tests use PostgreSQL instead of mocks or SQLite.
- Explain the async testing issues that appeared:
  - asyncpg event loop conflicts
  - drop_all/create_all instability
  - long-lived AsyncSession fixture problem
- Explain the final solution:
  - schema once
  - TRUNCATE between tests
  - db fixture as async session factory
  - short-lived sessions
- Explain why this final test setup is still rigorous.
- Include the final test command and expected result: 30 passed.

Requirements for docs/SENIOR_DEFENSE_GUIDE.md:
- Write this as an interview preparation guide.
- Include concise answers to questions like:
  - What does this project do?
  - Why FastAPI?
  - Why PostgreSQL?
  - Why polling instead of WebSockets?
  - How did you guarantee zone counts under concurrent writes?
  - How did you handle fault transitions atomically?
  - How did you define anomalies?
  - What would you change at larger scale?
  - What did you deliberately leave out?
  - What were the hardest issues and how did you solve them?
- Include a short “60 second explanation” of the whole project.
- Include a “deep technical explanation” for a senior reviewer.
- Include possible follow-up questions and strong answers.

Style requirements:
- Be concise.
- Avoid generic explanations.
- Focus on this project specifically.
- Do not explain basic FastAPI, React, or Docker concepts unless they are directly relevant to this project.
- Do not repeat the same explanation across documents unless needed.
- Explain repeated code patterns once, then reference the pattern.
- Make it easy to study quickly.

Also append a short entry to docs/AI_LOG.md summarizing:
- this prompt
- the files created
- what each document is for
- any assumptions made

At the end, show:
- files created
- files changed
- any assumptions
- recommended reading order
```

### Qué generó Claude Code

Creó los cinco documentos de estudio dentro de `docs/` (en este proyecto existen como las versiones en español: `PROJECT_MAP_ES.md`, `BACKEND_WALKTHROUGH_ES.md`, `FRONTEND_WALKTHROUGH_ES.md`, `TESTING_AND_DEBUGGING_WALKTHROUGH_ES.md` y `SENIOR_DEFENSE_GUIDE_ES.md`), cubriendo arquitectura, walkthrough de backend y frontend, estrategia de tests y debugging async, y una guía de defensa en entrevista.

### Cómo lo validé

Revisé que los documentos fueran coherentes con el código fuente y con el resto de la documentación (mismo conteo de 30 tests, mismas decisiones técnicas).

### Qué tuve que corregir

Nada de código: es documentación pura. El único supuesto documentado fue tomar el número de 30 tests de la documentación existente.

### Resultado de la etapa

Un set de documentos de estudio que complementa el ADR y el AI log, útil para entender y defender el proyecto de punta a punta.

---

## Cierre

Al final, el uso de IA no reemplazó el criterio técnico. ChatGPT me ayudó a planificar y a dividir el trabajo en etapas pequeñas y revisables; Claude Code me ayudó a ejecutar los cambios rápidamente, crear archivos y correr comandos; y la validación manual, los tests contra PostgreSQL real y las correcciones puntuales fueron lo que mantuvo el proyecto alineado con los requerimientos del challenge. La parte donde la IA más necesitó dirección fue la infraestructura async de tests, que tomó cuatro rondas de diagnóstico y corrección humana. Trabajar por capas, validando cada una antes de avanzar, fue lo que permitió entregar una vertical funcional, testeable y defendible dentro del tiempo del challenge.
