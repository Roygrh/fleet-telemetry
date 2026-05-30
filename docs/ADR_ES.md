# Registro de Decisiones de Arquitectura

Decisiones clave tomadas durante la construcción del Fleet Telemetry Monitoring Service.

---

## Decisión 1 - PostgreSQL sobre SQLite

**Elegido por:** bloqueo a nivel de fila (`SELECT ... FOR UPDATE`), upserts atómicos (`INSERT ... ON CONFLICT`) y soporte async mediante `asyncpg`.

SQLite serializa todas las escrituras usando un único lock global. Con 50 vehículos enviando telemetría a 1 Hz, eso significa hasta 50 escrituras concurrentes por segundo. Ese lock global convertiría las escrituras en una cola. PostgreSQL, en cambio, puede bloquear a nivel de fila, por lo que la escritura de telemetría de cada vehículo puede manejarse de forma independiente.

---

## Decisión 2 - FastAPI y SQLAlchemy async

El modelo async de FastAPI encaja directamente con `asyncpg`, que es un driver nativo para event loop. Cada request HTTP obtiene una sesión async no bloqueante, y los 50 vehículos pueden ser atendidos de forma concurrente sin depender de un thread pool. Además, el estilo `Mapped` y `mapped_column` de SQLAlchemy 2.x permite definir modelos con mejor tipado y menos boilerplate.

La lógica de negocio vive en los services, mientras que el acceso a base de datos queda aislado en funciones delgadas de repository. Esta separación fue importante porque hizo más simple cambiar la sesión async durante la configuración de tests.

---

## Decisión 3 - Polling sobre WebSockets

El polling cada 2 segundos desde el cliente es suficiente para esta escala. Con 50 vehículos emitiendo datos a 1 Hz, la información cambia varias veces dentro de cada intervalo de polling. Para un operador de almacén, una latencia de 2 segundos es aceptable y prácticamente imperceptible.

WebSockets agregarían lógica de reconexión en el cliente, estado de fanout en el servidor y mayor complejidad de despliegue. En este escenario no se justifica ese costo. El trade-off queda explícito: si el sistema creciera a 10,000 o más vehículos, o si se necesitara latencia menor a un segundo, se debería cambiar a Server-Sent Events o WebSockets.

---

## Decisión 4 - Reglas de detección de anomalías

Se evalúan cuatro reglas por cada evento de telemetría. Cada regla que se activa genera una fila persistida en la tabla de anomalías.

| Regla | Condición | Justificación |
|---|---|---|
| `LOW_BATTERY` | `battery_pct < 15` | Riesgo de apagado durante una misión |
| `VEHICLE_FAULT` | `status == "fault"` | Error explícito de hardware o software |
| `ERROR_CODE_REPORTED` | `len(error_codes) > 0` | Error reportado directamente por el dispositivo |
| `HIGH_SPEED` | `speed_mps > 8.0` | Supera el límite seguro de velocidad en almacén |

Los umbrales están definidos como constantes hardcoded. En un sistema productivo, deberían almacenarse en una configuración administrable.

---

## Decisión 5 - Contador atómico de zonas

Los contadores de entrada por zona usan una única sentencia SQL:

```sql
INSERT INTO zone_counters (zone_id, entry_count) VALUES (:zone, 1)
ON CONFLICT (zone_id) DO UPDATE
  SET entry_count = zone_counters.entry_count + 1
```

No hay una operación de lectura, modificación y escritura en Python. PostgreSQL serializa los incrementos concurrentes sobre la misma fila a nivel del motor de almacenamiento, por lo que el contador permanece exacto aunque varios vehículos entren a la misma zona al mismo tiempo. Una solución ingenua con `SELECT` seguido de `UPDATE`, bajo carga concurrente, podría perder incrementos.

---

## Decisión 6 - Transición a fault mediante SELECT FOR UPDATE

`PATCH /vehicles/{id}/status` con `status=fault` se ejecuta de forma atómica:

1. `SELECT ... FOR UPDATE`: bloquea la fila del vehículo para que ninguna escritura concurrente pueda intercalarse.
2. `UPDATE missions SET status='cancelled'`: cancela todas las misiones activas del vehículo.
3. `INSERT INTO maintenance_records`: crea el registro de mantenimiento con el motivo correspondiente.
4. `UPDATE vehicles SET current_status='fault'`: actualiza el estado actual del vehículo.
5. Un único `COMMIT`: los tres cambios se persisten juntos o no se persiste ninguno.

Si ocurre un rollback en cualquiera de los pasos, las tablas de vehículos, misiones y registros de mantenimiento quedan sin cambios parciales.

---

## Restricciones poco claras y supuestos

1. **Modelo de misión**: el enunciado menciona una "misión activa", pero no proporciona un schema. Se asumió una tabla `missions` con `vehicle_id`, `status` (`active`, `cancelled`, `completed`) y `started_at`.
2. **Geometría de zonas**: se asume que el cliente edge detecta los límites de zona. El backend solo cuenta eventos `zone_entered`; no valida coordenadas contra polígonos de zona.
3. **Tamaño de la flota**: se fija en 50 vehículos, desde `v-01` hasta `v-50`. El script de seed debe ejecutarse antes de ingerir telemetría, porque la relación se protege con una foreign key.
4. **Persistencia de anomalías**: las anomalías se persisten en base de datos, no solo se emiten en tiempo real. Esto permite soportar el endpoint de consulta filtrable y enriquecer la lista de vehículos con la última anomalía.
5. **Sin autenticación**: queda fuera del alcance por el tiempo definido para el challenge. Sería la primera mejora en una fase de hardening productivo.

---

## Qué cambiaría a escala

"Significativamente" significa 10,000 o más vehículos, latencia menor a 100 ms y despliegue multi-región.

- **Message broker** como Kafka o Redpanda entre el endpoint de ingestión y la escritura en base de datos. Esto desacopla el throughput HTTP de la latencia de la base de datos y permite replay de eventos.
- **WebSockets o Server-Sent Events** para reemplazar el polling. Un gateway con estado manejaría el fanout de conexiones.
- **Particionamiento de la tabla `telemetry_events`** por ventanas de tiempo o por hash de `vehicle_id`.
- **Redis `INCR`** para contadores de zona. Esto elimina la contención de filas en PostgreSQL cuando hay miles de eventos concurrentes por segundo para la misma zona.
- **Read replicas** para las consultas del dashboard, evitando que las lecturas compitan con las escrituras de ingestión.
- **Jobs de retención** para eliminar telemetría antigua según un TTL configurable.

---

## Omisiones deliberadas

| Omisión | Motivo |
|---|---|
| Auth y RBAC | No era requerido por el spec y agregaba alcance significativo |
| Retención de telemetría y TTL | Fuera del alcance; en este prototipo la base de datos crece indefinidamente |
| Renderizado geoespacial | El conteo de zonas satisface el spec; un mapa requeriría una librería adicional |
| Alertas push | Las anomalías se almacenan y se pueden consultar; no se implementaron webhooks ni canales de notificación |
| Latitud y longitud en la lista de vehículos | Están presentes en los eventos de telemetría y en la base de datos; el dashboard del spec solo requiere estado, batería y anomalía |
