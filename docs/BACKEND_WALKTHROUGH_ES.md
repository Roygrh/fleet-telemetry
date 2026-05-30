# Backend Walkthrough — Guía técnica en español

## Visión general

El backend es una API FastAPI async que expone 6 endpoints REST. Todo pasa por capas bien definidas: la ruta valida el request, el service orquesta la lógica, el repository ejecuta SQL. La base de datos es PostgreSQL, accedida con SQLAlchemy async + asyncpg.

---

## Capa por capa

### `app/main.py` — Punto de entrada

```python
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])
app.include_router(vehicles.router, prefix="/api/vehicles", tags=["vehicles"])
# ...
```

**Qué hace:** registra los 5 routers con prefijo `/api`, configura CORS para permitir el frontend en `:5173`, expone `/health`.

**Por qué existe:** es el lugar donde la app toma forma. El prefijo `/api` es crítico porque el proxy de Vite está configurado para reenviar `/api/*` sin modificaciones al backend. Si los routers no tuvieran ese prefijo, el frontend recibiría 404 en todas las llamadas.

**Cómo explicarlo en entrevista:** "El prefijo `/api` en main.py es una convención de proxy. Vite reenvía todo lo que empiece con `/api` al backend sin reescribir la URL. Si el backend no tiene ese prefijo, no hay match."

---

### `app/core/database.py` — Motor async

Configura el `AsyncEngine` con la URL de PostgreSQL, el `async_sessionmaker`, y la dependencia `get_db` que FastAPI inyecta en cada request.

**Qué hace:** define cómo se crea y se cierra una sesión async por request.

**Por qué existe:** centraliza la configuración de la conexión. Si se necesita cambiar el pool, el timeout, o la URL, hay un único lugar.

**Por qué async:** con SQLAlchemy sync, cada request bloquea un thread. Con async + asyncpg, el event loop de Python puede manejar múltiples requests concurrentes sin threads adicionales. Con 50 vehículos a 1 Hz, eso es relevante.

---

### `app/models/` — ORM Models

Seis modelos usando SQLAlchemy 2.x con la sintaxis `Mapped`/`mapped_column`:

| Archivo | Tabla | Propósito |
|---------|-------|-----------|
| `vehicle.py` | `vehicles` | Estado snapshot actual de cada vehículo |
| `telemetry.py` | `telemetry_events` | Log completo de cada evento recibido |
| `zone.py` | `zone_counters` | Contadores de entrada por zona |
| `anomaly.py` | `anomalies` | Anomalías detectadas y persistidas |
| `mission.py` | `missions` | Misiones activas/canceladas/completadas |
| `maintenance.py` | `maintenance_records` | Registros de mantenimiento abiertos |
| `enums.py` | — | Python enums: `VehicleStatus`, `MissionStatus`, `MaintenanceStatus` |

**Decisión de diseño clave:** todas las FKs van a `vehicles.vehicle_id` (string), no al PK entero. Esto evita un JOIN o lookup extra por cada telemetría recibida, porque el payload ya trae el string `v-01`.

**Por qué separar `enums.py`:** los enums se usan tanto en los modelos ORM como en los schemas Pydantic. Si estuvieran duplicados, las validaciones podrían desincronizarse. Un solo archivo fuente de verdad.

**Cómo explicarlo en entrevista:** "Uso el estilo `Mapped[str]` de SQLAlchemy 2.x. Es type-safe, el editor lo infiere, y evita el boilerplate de `Column(String)`. Los enums están en un módulo separado porque los usan tanto los modelos ORM como los schemas Pydantic."

---

### `app/schemas/` — Validación con Pydantic

Cinco archivos de schemas que definen la forma de requests y responses:

**`schemas/telemetry.py` — El schema más importante del proyecto:**

```python
class TelemetryEventCreate(BaseModel):
    vehicle_id: str     # validado: v-01 a v-50
    battery_pct: float = Field(ge=0.0, le=100.0)
    zone_entered: str | None = None  # validado contra ZONE_SET

    @field_validator("vehicle_id")
    def check_vehicle_id(cls, v): ...

    @field_validator("zone_entered")
    def check_zone(cls, v): ...
```

**Qué hace:** valida el payload antes de que toque la DB. `vehicle_id` debe coincidir con `v-\d{2}` y estar en rango 01-50. `zone_entered` debe ser null o una de las 20 zonas definidas en `constants/zones.py`. `battery_pct` debe estar entre 0 y 100.

**Por qué las validaciones están en el schema y no en el service:** porque FastAPI ejecuta los schemas automáticamente antes de llegar al handler. Si el request es inválido, retorna 422 sin ejecutar código de negocio. No contamina los services con lógica de validación de input.

**Cómo explicarlo en entrevista:** "Si llegas al service, el payload ya es válido. Las validaciones en Pydantic son la frontera del sistema. Todo lo que entra al service es de confianza."

---

### `app/services/` — Lógica de negocio

Cinco servicios. Los dos más importantes:

#### `services/telemetry.py` — Flujo completo de ingestión

```python
async def ingest(session, payload):
    event = await telemetry_repo.create(session, payload)      # 1. persiste el evento
    await vehicle_repo.update_state(session, ...)               # 2. actualiza snapshot
    for rule_type, predicate, describe in _ANOMALY_RULES:      # 3. evalúa 4 reglas
        if predicate(payload):
            await anomaly_repo.create(session, ...)
    if payload.zone_entered:
        await zone_repo.increment(session, payload.zone_entered) # 4. incremento atómico
    await session.commit()
    return event
```

**Todo ocurre en una sola transacción.** Si falla cualquier paso, el commit no ocurre y no queda nada a medias en la DB.

**Por qué `session.flush()` después de crear el evento:** para que el `event.id` sea asignado por PostgreSQL antes del commit. Las anomalías necesitan ese ID como FK. Sin flush, el ID sería None dentro de la transacción todavía abierta.

**Las reglas de anomalía como lista de tuplas:**

```python
_ANOMALY_RULES = [
    ("LOW_BATTERY",        lambda p: p.battery_pct < 15,        lambda p: f"Battery at {p.battery_pct:.1f}%..."),
    ("VEHICLE_FAULT",      lambda p: p.status == VehicleStatus.fault, ...),
    ("ERROR_CODE_REPORTED",lambda p: len(p.error_codes) > 0,    ...),
    ("HIGH_SPEED",         lambda p: p.speed_mps > 8.0,         ...),
]
```

Este patrón es extensible: agregar una regla nueva es agregar una tupla. No hay if/elif encadenados. Cada regla que dispara produce exactamente una fila en `anomalies`.

**Umbrales son exclusivos:** `battery < 15` significa que 15.0 exactamente no dispara anomalía. `speed > 8.0` significa que 8.0 exactamente no dispara. Los tests verifican estos valores límite explícitamente.

#### `services/vehicle.py` — Fault transition atómica

```python
async def update_status(session, vehicle_id, new_status):
    vehicle = await vehicle_repo.get_for_update(session, vehicle_id)  # SELECT FOR UPDATE
    if vehicle is None:
        raise HTTPException(404, ...)
    
    if new_status == VehicleStatus.fault:
        await mission_repo.cancel_active(session, vehicle_id, now)    # cancela misiones
        await maintenance_repo.create(session, vehicle_id, ...)       # crea mantenimiento
    
    vehicle.current_status = new_status
    await session.commit()   # único commit — todo o nada
```

**Por qué SELECT FOR UPDATE:** si dos requests de `PATCH /vehicles/v-01/status` llegan al mismo tiempo, solo uno puede tener el lock. El segundo espera. Sin esto, dos transacciones concurrentes podrían ver el mismo vehicle y cancelar misiones dos veces o crear dos registros de mantenimiento.

**Por qué una sola transacción:** el spec pedía atomicidad explícita. Si se creara el registro de mantenimiento en una transacción y se cancelaran las misiones en otra, un error entre ambas dejaría la DB en estado inconsistente.

**Cómo explicarlo en entrevista:** "SELECT FOR UPDATE es un lock de fila, no de tabla. Solo bloquea ese vehículo específico. El lock se libera cuando la transacción commitea."

---

### `app/repositories/` — Acceso a datos

Seis archivos de repositories. Son wrappers delgados de SQLAlchemy. No tienen lógica de negocio.

**El más importante: `repositories/zone.py`**

```python
async def increment(session, zone_id):
    await session.execute(
        text(
            "INSERT INTO zone_counters (zone_id, entry_count) VALUES (:zone_id, 1) "
            "ON CONFLICT (zone_id) DO UPDATE "
            "SET entry_count = zone_counters.entry_count + 1"
        ),
        {"zone_id": zone_id},
    )
```

**Por qué SQL crudo y no ORM:** esta operación específica requiere `ON CONFLICT DO UPDATE`, que el ORM de SQLAlchemy puede hacer pero es más verboso. Más importante: el SQL aquí expresa la intención exacta — un upsert atómico.

**Por qué no hacer SELECT + UPDATE en Python:**

```python
# MAL: no es atómico bajo concurrencia
counter = await session.get(ZoneCounter, zone_id)
counter.entry_count += 1
await session.flush()
```

Si dos requests hacen este READ al mismo tiempo antes de que el otro haga el WRITE, ambos leen el mismo valor, ambos lo incrementan en 1, y solo uno de los dos incrementos queda registrado. Con el upsert atómico, PostgreSQL serializa los incrementos del mismo `zone_id` a nivel de fila. No hay read-modify-write en Python.

**`repositories/vehicle.py` — `get_for_update`:**

```python
async def get_for_update(session, vehicle_id):
    result = await session.execute(
        select(Vehicle).where(Vehicle.vehicle_id == vehicle_id).with_for_update()
    )
    return result.scalar_one_or_none()
```

Esto genera `SELECT ... FOR UPDATE` en el SQL ejecutado. La clave es que es el repository quien tiene esta variante, y el service elige cuándo usarla.

---

### `app/constants/zones.py` — Las 20 zonas

```python
ZONES = ["inbound_dock_a", "inbound_dock_b", ..., "maintenance_bay"]
ZONE_SET = frozenset(ZONES)
```

**Por qué `frozenset`:** la validación del schema hace `v not in ZONE_SET`. Un `frozenset` hace ese lookup en O(1). Una lista lo haría en O(n).

**Por qué hardcoded:** el spec no menciona zonas configurables. En producción estarían en la DB o en configuración. Para el challenge, el spec las da fijas y el seed las inicializa en `zone_counters`.

---

### `alembic/versions/0001_initial_schema.py` — La migración

La migración crea los tipos enum de PostgreSQL primero (`vehiclestatus`, `missionstatus`, `maintenancestatus`) y luego las tablas en orden de dependencia de FKs.

**El bug que apareció:** al definir el enum `VehicleStatus` en SQLAlchemy, la migración lo intentaba crear dos veces: una al declarar el tipo y otra dentro de `op.create_table`. El fix fue pasar `create_type=False` en las referencias secundarias.

**Por qué hand-written y no autogenerada:** `alembic revision --autogenerate` requiere una DB en vivo. Para un take-home reproducible en Docker desde cero, la migración hand-written permite un startup limpio.

---

### `seed.py` — El script de seed

Inserta los 50 vehículos (`v-01` a `v-50`) y los 20 contadores de zona con `ON CONFLICT DO NOTHING`, lo que hace el script idempotente. Se puede correr múltiples veces sin duplicar datos.

**Por qué es necesario:** el schema tiene FK en `telemetry_events.vehicle_id` → `vehicles.vehicle_id`. Si se ingesta telemetría para un vehículo no seeded, PostgreSQL lanza una violación de FK. El seed no es opcional.

---

## Flujo completo de telemetría

```
POST /api/telemetry (JSON payload)
│
├─ FastAPI router: extrae payload, llama service
│
├─ Schema Pydantic: valida vehicle_id, battery_pct, zone_entered
│   └─ 422 si inválido, cortocircuito
│
└─ TelemetryService.ingest(session, payload)
    ├─ telemetry_repo.create() → INSERT + flush → event.id disponible
    ├─ vehicle_repo.update_state() → UPDATE vehicles SET ... last-write-wins
    ├─ Para cada regla en _ANOMALY_RULES:
    │   └─ si predicate(payload): anomaly_repo.create() → INSERT anomaly con FK a event
    ├─ si zone_entered:
    │   └─ zone_repo.increment() → INSERT ON CONFLICT DO UPDATE (atómico)
    └─ session.commit() → todo persiste o nada persiste
         └─ Response 202 con el evento creado
```

---

## Qué es intencionalmente simple por ser un take-home

- **Sin auth:** endpoints públicos. En producción sería OAuth2 o JWT.
- **Sin message broker:** ingestión directa a PostgreSQL. Con 10k vehículos, se necesitaría Kafka entre el endpoint HTTP y la escritura.
- **Sin retención:** los eventos crecen indefinidamente. En producción, un job de pruning por TTL.
- **Sin validación geoespacial:** el backend no valida que las coordenadas lat/lon estén dentro del polígono de la zona. Asume que el cliente edge hace esa detección.
- **Umbrales hardcoded:** en producción estarían en una tabla de configuración con historial de cambios.
- **Seed manual:** en producción sería parte del pipeline de deployment.
