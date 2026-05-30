# Frontend Walkthrough — Guía técnica en español

## Visión general

El frontend es una SPA (Single Page Application) en React 18 + TypeScript + Vite. No tiene routing, no tiene auth, no tiene librerías de UI. Es un dashboard de monitoreo que hace polling al backend cada 2 segundos y renderiza el estado de la flota.

La arquitectura está separada en cuatro capas con responsabilidades distintas:

```
frontend/src/
├── types/index.ts       ← interfaces TypeScript (contratos con el backend)
├── services/api.ts      ← fetch wrappers tipados (capa de API)
├── hooks/
│   ├── usePolling.ts    ← hook genérico de intervalo
│   └── useFleetData.ts  ← estado del dashboard completo
└── components/          ← UI presentacional pura
    ├── FleetSummary.tsx
    ├── VehicleTable.tsx
    ├── ZoneCounts.tsx
    ├── StatusBadge.tsx
    ├── AnomalyBadge.tsx
    ├── LoadingState.tsx
    └── ErrorState.tsx
```

---

## Por qué esta separación importa

**Sin la separación:**
Un componente que hace `fetch` directamente, maneja errores, transforma datos y renderiza HTML mezcla cuatro responsabilidades. Testearlo requiere mockear fetch, y cualquier cambio en la API rompe la UI.

**Con la separación:**
- `api.ts` es el único lugar que sabe cómo hablar con el backend.
- `useFleetData` es el único lugar que sabe cuándo y con qué frecuencia hacer las llamadas.
- Los componentes solo reciben props y renderizan. No tienen efectos secundarios.

---

## `types/index.ts` — El contrato con el backend

```typescript
export type VehicleStatus = 'idle' | 'moving' | 'charging' | 'fault';

export interface Vehicle {
  vehicle_id: string;
  current_status: VehicleStatus;
  battery_pct: number | null;
  last_seen_at: string | null;
  latest_anomaly: Anomaly | null;
}

export interface ZoneCountResponse {
  zones: ZoneCount[];  // envelope que el backend devuelve
}
```

**Por qué estos tipos:** son el espejo exacto de los schemas Pydantic del backend. Si el backend cambia un campo, TypeScript detectará la discrepancia en tiempo de compilación. `battery_pct` y `last_seen_at` son `null` porque un vehículo recién seeded no ha recibido telemetría todavía.

**`VehicleStatus` como union type:** en lugar de `string`. Esto hace que el compilador falle si se pasa un valor inválido a `StatusBadge` o se compara contra un string que no existe.

**`ZoneCountResponse`:** el backend devuelve `{ zones: [...] }`, no un array directo. El type modela ese envelope explícitamente. La capa de servicios es quien lo desenvuelve.

---

## `services/api.ts` — Capa de API

```typescript
async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function fetchZoneCounts(): Promise<ZoneCount[]> {
  const data = await apiFetch<ZoneCountResponse>('/api/zones/counts');
  return data.zones;  // desenvuelve el envelope aquí, no en el hook
}
```

**Por qué paths relativos `/api/vehicles`:** el frontend corre en el mismo origen que el Vite proxy. Las llamadas a `/api/*` las intercepta Vite y las redirige al backend. Si se usara una URL absoluta (`http://backend:8000/api/vehicles`), las llamadas irían directamente al backend sin pasar por el proxy, lo que rompería el CORS en el browser.

**Por qué un solo `apiFetch` genérico:** el manejo de errores HTTP es idéntico para todas las rutas. Si la respuesta no es ok, se lanza un error. No hay 4 versiones del mismo try/catch.

**Por qué no axios u otras librerías:** `fetch` nativo es suficiente para este caso. Sin dependencias adicionales que gestionar o versionar.

---

## `hooks/usePolling.ts` — Polling sin re-renders innecesarios

```typescript
export function usePolling(callback: () => void, intervalMs: number): void {
  const savedCallback = useRef<() => void>(callback);

  useEffect(() => {
    savedCallback.current = callback;   // actualiza la ref sin re-correr el interval
  }, [callback]);

  useEffect(() => {
    savedCallback.current();            // llama inmediatamente al montar
    const id = setInterval(() => savedCallback.current(), intervalMs);
    return () => clearInterval(id);     // limpia al desmontar (sin memory leaks)
  }, [intervalMs]);
}
```

**El patrón de ref para el callback:** sin la ref, cada vez que `callback` cambia (lo que ocurre en cada render porque `useCallback` en `useFleetData` tiene dependencias), el `useEffect` que configura el interval se volvería a ejecutar, creando un nuevo `setInterval`. Con la ref, el interval se registra una vez y siempre llama a la versión más reciente del callback.

**Por qué llamar inmediatamente en mount:** para que el dashboard no espere 2 segundos en pantalla vacía antes de mostrar datos. El primer poll ocurre al montar.

**Por qué `clearInterval` en el return:** si el componente se desmonta (poco probable en esta app de una página, pero correcto igualmente), el interval no sigue corriendo. Sin esto, se acumularían intervals en memoria.

---

## `hooks/useFleetData.ts` — Estado del dashboard

```typescript
const poll = useCallback(async () => {
  try {
    const [v, f, z, a] = await Promise.all([
      fetchVehicles(), fetchFleetState(), fetchZoneCounts(), fetchAnomalies()
    ]);
    setVehicles(v); setFleetState(f); setZoneCounts(z); setAnomalies(a);
    setLastUpdated(new Date());
    setError(null);
  } catch (err) {
    setError(err instanceof Error ? err.message : 'An unknown error occurred');
  } finally {
    setLoading(prev => prev ? false : prev);  // solo cambia de true a false, una vez
  }
}, []);

usePolling(poll, POLL_INTERVAL_MS);
```

**Por qué `Promise.all` y no 4 fetches secuenciales:** los 4 endpoints son independientes. Con `Promise.all` se lanzan en paralelo y terminan cuando todos responden. Secuencial sería 4× más lento en el mejor caso.

**El comportamiento de `loading`:** `loading` empieza en `true`. El bloque `finally` solo lo pone en `false` la primera vez. En polls subsiguientes, `loading` ya es `false` y no se toca. Esto evita el efecto visual de "spinner en cada actualización".

**Stale data en error:** si falla un poll después del primero, `error` se setea pero los datos anteriores permanecen. El usuario ve sus últimos datos conocidos más un banner de advertencia. Limpiar los datos en error sería una regresión de UX.

**`lastUpdated`:** se actualiza solo en polls exitosos. Si hay un error, el timestamp no cambia, lo cual es informativo: el usuario ve cuándo fue la última actualización exitosa.

---

## `App.tsx` — Composición del dashboard

```tsx
function App() {
  const { vehicles, fleetState, zoneCounts, lastUpdated, loading, error } = useFleetData();

  if (loading) return <LoadingState />;                    // primer poll en progreso
  if (error && !fleetState) return <ErrorState />;         // primer poll falló

  return (
    <div className="app">
      <header>
        <h1>Fleet Telemetry Dashboard</h1>
        {lastUpdated && <span>Last updated: {lastUpdated.toLocaleTimeString()}</span>}
      </header>
      <main>
        {error && <div className="error-banner">⚠ {error}</div>}  {/* poll subsiguiente falló */}
        <FleetSummary state={fleetState} />
        <div className="content-grid">
          <VehicleTable vehicles={vehicles} />
          <ZoneCounts zones={zoneCounts} />
        </div>
      </main>
    </div>
  );
}
```

**Tres estados de UI distintos:**
1. `loading = true`: spinner (primer poll todavía en vuelo)
2. `error && !fleetState`: error de página completa (nunca hubo datos)
3. `error && fleetState`: banner de advertencia sobre datos stale (hubo datos antes)

Esta distinción importa. Un sistema de monitoreo de flota que borra la pantalla en cada error de red deja al operador sin información cuando más la necesita.

---

## El bug del proxy de Vite

**`vite.config.ts` original (incorrecto):**
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://backend:8000',
      rewrite: (path) => path.replace(/^\/api/, ''),  // 🐛 quitaba el /api
    }
  }
}
```

**El resultado:** `fetch('/api/vehicles')` → Vite rewrites a `/vehicles` → backend recibe `GET /vehicles` → 404. El backend expone los endpoints bajo `/api/vehicles`, no `/vehicles`.

**Fix:**
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://backend:8000',
      // sin rewrite — Vite reenvía /api/vehicles → http://backend:8000/api/vehicles
    }
  }
}
```

**Por qué importa entender esto:** el `rewrite` en Vite sirve cuando el backend no tiene el prefijo `/api` en sus rutas. Aquí el backend sí lo tiene (lo agrega `main.py`). El rewrite y el prefijo del backend deben coincidir.

---

## Componentes — Lógica de presentación

### `VehicleTable.tsx`
- Tabla ordenada por `vehicle_id` (orden de string funciona porque el formato es `v-01` a `v-50`).
- `battery_pct` se muestra en rojo si es `< 15`, alineado con la regla de anomalía `LOW_BATTERY`.
- Filas con status `fault` tienen fondo rojo claro.
- `latest_anomaly` viene del objeto `Vehicle` directamente — no hay join en el cliente.

### `ZoneCounts.tsx`
- Ordenado por `entry_count` descendente (zonas más activas primero).
- Zonas con `charging` en el nombre tienen highlight azul.

### `StatusBadge.tsx` y `AnomalyBadge.tsx`
- Badges de color que usan clases CSS según el valor del enum.
- `AnomalyBadge` tiene tooltip con descripción y timestamp de la anomalía.

### `LoadingState.tsx` y `ErrorState.tsx`
- Componentes de pantalla completa para el primer poll.
- `ErrorState` muestra el mensaje de error y un hint de "will retry".

---

## Por qué polling y no WebSockets

Con 50 vehículos a 1 Hz, los datos cambian múltiples veces dentro de cada intervalo de 2 segundos. El lag de 2 segundos es imperceptible para un operador de almacén.

WebSockets agregarían:
- Lógica de reconexión en el cliente.
- Estado de fanout en el servidor.
- Complejidad de deployment (balanceadores de carga y sticky sessions).

Para este escenario de 50 vehículos y un dashboard, polling es suficiente y más simple. El ADR documenta cuándo cambiar a WebSockets: 10,000+ vehículos o latencia sub-segundo.

---

## Cómo explicar el frontend en una entrevista

"El frontend no es sofisticado a propósito. Tiene una capa de tipos que espeja el backend, una capa de fetch wrappers, hooks que encapsulan el polling, y componentes que solo renderizan. Cuando el backend cambia la forma de un response, TypeScript me avisa antes de que lo vea en el browser. El patrón de `useRef` en `usePolling` evita que el interval se recree en cada render. Y el manejo de error distingue entre error en el primer poll (pantalla de error) y error en polls subsiguientes (banner, datos stale visibles)."
