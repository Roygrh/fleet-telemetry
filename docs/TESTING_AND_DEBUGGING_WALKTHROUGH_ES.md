# Testing y Debugging Walkthrough — Guía técnica en español

## Estrategia general

El backend tiene 30 tests distribuidos en 4 archivos. Todos corren contra una base de datos PostgreSQL real (`fleet_telemetry_test`). No hay mocks de la DB, no se usa SQLite.

La estrategia central: el test verifica el comportamiento observable del sistema completo (HTTP → service → repository → PostgreSQL → response), no la implementación interna de ninguna función.

---

## Por qué PostgreSQL real y no SQLite o mocks

**SQLite no sirve aquí porque:**
- No tiene `SELECT ... FOR UPDATE` (no soporta row-level locking real).
- `INSERT ... ON CONFLICT DO UPDATE` existe en SQLite pero con semántica diferente en edge cases.
- El test de concurrencia requiere que 20 writers concurrentes sean serializados por el motor de DB, no por Python.

**Los mocks no sirven aquí porque:**
- El test crítico de zona verifica que el conteo sea exactamente 20 bajo 20 requests concurrentes. Un mock que registra las llamadas no puede verificar que no haya race conditions en el SQL real.
- Si se mocking el repository, se está probando que el service llama al repository, no que el sistema funciona correctamente end-to-end.

**La regla de sentido común:** los tests deben fallar si el código está roto, no si el mock está mal configurado. PostgreSQL real cumple eso.

---

## Estructura de los tests

### `test_telemetry.py` — 12 tests

Cubre ingestión y detección de anomalías:

| Test | Qué verifica |
|------|-------------|
| `test_ingest_returns_202_and_event` | El endpoint retorna 202 y el JSON del evento |
| `test_ingest_updates_vehicle_state` | La fila en `vehicles` se actualiza con el nuevo estado |
| `test_no_anomaly_for_normal_telemetry` | Un payload normal no genera anomalías |
| `test_anomaly_low_battery` | `battery_pct: 14.9` genera `LOW_BATTERY` |
| `test_anomaly_battery_at_threshold_is_not_flagged` | `battery_pct: 15.0` no genera `LOW_BATTERY` |
| `test_anomaly_vehicle_fault` | `status: "fault"` genera `VEHICLE_FAULT` |
| `test_anomaly_error_codes_reported` | `error_codes: ["E001"]` genera `ERROR_CODE_REPORTED` |
| `test_anomaly_high_speed` | `speed_mps: 8.1` genera `HIGH_SPEED` |
| `test_anomaly_speed_at_threshold_is_not_flagged` | `speed_mps: 8.0` no genera `HIGH_SPEED` |
| `test_multiple_rules_fire_independently` | `battery: 10.0 + speed: 9.0` genera dos anomalías distintas |
| `test_anomaly_linked_to_telemetry_event` | La FK `anomaly.telemetry_event_id` apunta al evento correcto |
| `test_invalid_vehicle_id_rejected` | `vehicle_id: "v-99"` retorna 422 |
| `test_invalid_zone_rejected` | `zone_entered: "nonexistent_zone"` retorna 422 |

**Por qué probar los valores límite:** `15.0` y `8.0` exactamente. Las reglas son estrictamente `< 15` y `> 8.0`. Si alguien cambia el operador a `<=` accidentalmente, el test falla. Los valores exactos en los bordes son los más importantes de probar.

**Por qué probar el FK de anomalía:** valida que el `session.flush()` después de `telemetry_repo.create()` funciona correctamente. Sin flush, `event.id` sería None y la FK fallaría o apuntaría a nada.

---

### `test_zones.py` — 5 tests

El test más importante del proyecto está aquí:

```python
async def test_concurrent_zone_increments_are_counted_exactly(client, db):
    N = 20
    responses = await asyncio.gather(
        *[client.post("/api/telemetry", json=_BASE_PAYLOAD) for _ in range(N)]
    )
    assert await _zone_count(db) == N  # debe ser exactamente 20
```

**Qué está probando:** que `INSERT ... ON CONFLICT DO UPDATE SET entry_count = entry_count + 1` es realmente atómico bajo concurrencia real.

**Cómo funciona `asyncio.gather` aquí:** lanza 20 requests concurrentes al mismo AsyncClient (que usa ASGITransport). Cada request corre en el mismo event loop pero cada uno obtiene su propia sesión de DB (NullPool garantiza que no se reciclan). Las 20 sesiones se conectan a PostgreSQL y ejecutan el upsert concurrentemente.

**Qué pasaría con un read-modify-write en Python:** si el código fuera `counter.entry_count += 1` con un ORM SELECT previo, algunas transacciones leerían el mismo valor antes de que las otras escribieran. El resultado final sería menor a 20. Este test detectaría esa regresión.

Los otros 4 tests de zonas cubren:
- Que `zone_entered: null` no crea ningún contador.
- Que 5 requests secuenciales acumulan correctamente.
- Que dos zonas distintas se cuentan de forma independiente.

---

### `test_vehicles.py` — 8 tests

Cubre la fault transition:

| Test | Qué verifica |
|------|-------------|
| `test_status_update_to_idle` | Un PATCH no-fault actualiza el status sin efectos secundarios |
| `test_non_fault_patch_creates_no_maintenance_record` | Solo el fault path crea maintenance record |
| `test_unknown_vehicle_returns_404` | Un vehicle no seeded retorna 404 |
| `test_fault_transition_updates_vehicle_status` | El vehicle queda en `fault` en la DB |
| `test_fault_transition_cancels_active_mission` | La misión queda en `cancelled` |
| `test_fault_transition_creates_maintenance_record` | Se crea exactamente 1 maintenance record |
| `test_fault_transition_cancels_all_active_missions` | Si hay 2 misiones activas, ambas se cancelan |
| `test_fault_transition_atomicity` | Todos los cambios son visibles juntos en una sola lectura |

**El más valioso: `test_fault_transition_atomicity`:** abre una sesión limpia después del PATCH y verifica que `vehicle.status == fault`, `mission.status == cancelled`, y `maintenance_records.count == 1` son todos verdaderos al mismo tiempo. Esto valida que el commit único realmente persistió todo junto.

**El más revelador: `test_fault_transition_cancels_all_active_missions`:** siembra 2 misiones activas para el mismo vehículo. Si el service solo cancela la primera (`LIMIT 1`), el test falla. Valida que el `UPDATE ... WHERE vehicle_id = :id AND status = 'active'` cancela todas.

---

### `test_fleet.py` — 4 tests

Más simples, pero validan el `GROUP BY` del endpoint de estado:

- Estado vacío: todos los conteos son 0.
- Todos idle: `idle == N`, `total == N`, el resto 0.
- Mixed: conteo correcto por cada status.
- Live update: después de un PATCH que cambia de idle a fault, `GET /fleet/state` refleja el cambio.

El último test es un integration test completo: verifica que el endpoint de lectura ve los cambios del endpoint de escritura sin inconsistencias.

---

## Los problemas async que aparecieron

Esta fue la parte más difícil del proyecto. Los tests fallaban de formas distintas en distintos momentos.

### Problema 1: "Future attached to a different loop"

**Qué pasaba:** pytest-asyncio 0.24+ crea un nuevo event loop por cada función de test por defecto. El engine de SQLAlchemy tenía un pool de conexiones cuyas conexiones asyncpg estaban ligadas al loop del test 1. Cuando el test 2 empezaba con un nuevo loop, las conexiones del pool intentaban usarse en el loop incorrecto.

**Fix inicial:** `NullPool` en el engine de test. Sin pool, cada `session.execute()` abre y cierra su propia conexión. No hay estado entre tests.

**Fix adicional:** `asyncio_default_fixture_loop_scope = session` en `pytest.ini`. Hace que todos los tests compartan el mismo event loop durante toda la sesión, eliminando el problema de root.

### Problema 2: "another operation is in progress"

**Qué pasaba:** el fixture `reset_db` ejecutaba `Base.metadata.drop_all()` y `Base.metadata.create_all()` antes de cada test. `drop_all` emite múltiples sentencias DDL (DROP TABLE, DROP TYPE...) de forma asíncrona sobre la misma conexión. asyncpg detectaba que una operación todavía estaba "en vuelo" cuando se iniciaba la siguiente.

**Fix:** abandonar `drop_all/create_all` por completo para el reset entre tests. La solución final:

```python
# Una vez al inicio de la sesión de tests (scope="session")
async def _schema():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield

# Antes de cada test (autouse=True)
_TRUNCATE = text(
    "TRUNCATE TABLE maintenance_records, anomalies, missions, "
    "telemetry_events, zone_counters, vehicles RESTART IDENTITY CASCADE"
)

async def reset_db(_schema):
    async with _engine.begin() as conn:
        await conn.execute(_TRUNCATE)
    yield
```

**Por qué TRUNCATE y no DROP/CREATE:** TRUNCATE es una sola sentencia SQL. No hay múltiples DDL en vuelo. asyncpg no puede confundirse. Además, TRUNCATE es más rápido que DROP/CREATE porque no reconstruye el schema.

**Por qué `RESTART IDENTITY`:** resetea los sequences de los `SERIAL`/`BIGSERIAL`. Sin esto, los IDs seguirían contando desde donde los dejó el test anterior. Los tests no deben depender de IDs específicos, pero el reset completo es más limpio.

**Por qué `CASCADE`:** algunas tablas tienen FKs entre ellas (ej. `anomalies` referencia `telemetry_events`). TRUNCATE sin CASCADE fallaría porque la FK constraint bloquea el truncate. Con CASCADE, las tablas se truncan en el orden correcto automáticamente.

### Problema 3: "AsyncSession teardown loop error"

**Qué pasaba:** el fixture `db` original mantenía una `AsyncSession` abierta durante todo el test y la cerraba en el `finally` del teardown. Durante el teardown, intentaba hacer `rollback()` sobre una sesión que ya no tenía un loop válido.

**Fix final — db como factory de sesiones cortas:**

```python
@pytest.fixture
def db():
    @asynccontextmanager
    async def _factory():
        session = _TestSession()
        try:
            yield session
        finally:
            await session.close()  # sin rollback — solo cierra
    return _factory
```

Los tests usan el fixture así:
```python
async def test_algo(client, db):
    async with db() as session:
        row = await session.execute(text("SELECT ..."))
    # la sesión se cierra DENTRO del test, antes del teardown del fixture
```

**Por qué funciona:** la sesión existe solo mientras el `async with db()` está abierto. Cuando el bloque termina, la sesión se cierra. Para el momento del teardown del fixture `db`, no hay ninguna sesión abierta que pueda causar problemas.

---

## La solución final en perspectiva

El setup final no hace los tests menos rigurosos. Los trade-offs son buenos:

| Sacrificio | Ganancia |
|-----------|---------|
| Schema se crea una vez (no por test) | Estabilidad — no hay DDL racing con asyncpg |
| TRUNCATE en vez de DROP/CREATE | Una sola sentencia, 100x más rápido que recrear tablas |
| Sesiones cortas en vez de sesión por test | Sin problemas de teardown en el loop incorrecto |
| Seed manual por módulo de test | Cada módulo controla exactamente qué datos necesita |

Los tests siguen siendo rigurosos porque: usan PostgreSQL real, verifican el estado de la DB directamente con SQL, corren 20 requests concurrentes reales, y validan atomicidad mediante una lectura post-commit en sesión limpia.

---

## Cómo un senior diagnosticaría estos problemas

1. **Empezar por el error más específico:** "Future attached to different loop" → buscar qué objetos asyncio se comparten entre tests. Pool de conexiones = sospechoso principal.

2. **NullPool primero:** es el fix más conservador. Si el error persiste, elimina al pool como causa y mueve la búsqueda.

3. **Leer la docs de pytest-asyncio sobre loop scope:** el comportamiento de "un loop por test" es el default desde 0.21+ y es la causa de la mayoría de los "wrong loop" errors en proyectos async.

4. **Cuando DDL falla:** separar el setup del schema (una vez) del cleanup entre tests (TRUNCATE). DDL en múltiples sentencias sobre una conexión asyncpg es frágil. TRUNCATE es una sentencia.

5. **Cuando teardown falla:** la regla es que los fixtures no deben mantener recursos async que necesiten cleanup. Si no puede cerrar limpiamente, hacer que el test haga el cleanup él mismo.

---

## Comando final y resultado esperado

```bash
docker compose exec backend pytest
```

Resultado esperado:
```
=================== 30 passed in X.Xs ===================
```

Los 30 tests pasan contra PostgreSQL real. No hay mocks. No hay SQLite. No hay flakiness.
