# Evaluación de rendimiento y escalabilidad — CT chatbot

> Pregunta de negocio: **¿estamos listos para varios/muchos usuarios concurrentes?**
> Esta evaluación midió la infraestructura (sin costo de OpenAI, LLM mockeado), instrumentó
> el sistema para observabilidad continua, y aplicó quick-wins seguros. Workers en prod: **4**
> gunicorn `UvicornWorker` (confirmar nº real en el systemd del servidor).

## TL;DR — veredicto

| Escala | ¿Listos? | Condición |
|--------|----------|-----------|
| **Piloto ~50 usuarios activos** | ✅ **Sí**, con monitoreo | La infra lo aguanta de sobra; validar límites de la cuenta OpenAI. |
| **Crecimiento ~200–500** | 🟡 **Condicional** | Requiere backlog #1–#4 + load test con LLM real en staging. |
| **Masivo 1000+** | 🔴 **No, aún** | Requiere los cambios mayores (escala horizontal, rate limit en Redis, sizing de threadpool, throughput OpenAI enterprise). |

**El cuello de botella NO es la infra propia** (Mongo/MySQL/event loop): es **el LLM** —
su latencia (segundos), el rate limiter por worker y, sobre todo, **los límites de la cuenta
de OpenAI**. La infra local es rápida y escala bien en las pruebas.

## Qué se midió y cómo (toolkit reutilizable, en `evaluation/perf/`)
- `baseline.py` — carga/latencia histórica desde `message_backup` (solo lectura).
- `loadtest.py` — generador de carga async contra `/chat`, rampa de concurrencia.
- `cleanup_loadtest.py` — borra los datos `LOADTEST_` generados.
- `analyze_timings.py` — agrega la latencia por tool/fase ya persistida (instrumentación F1).
- `create_indexes.py` — índices recomendados + TTL (opt-in, destructivo).
- LLM mockeado: `src/ct/settings/fake_llm.py`, activado con `CT_FAKE_LLM=1`.

## Hallazgos (validados con datos)

**1. Tráfico actual = prácticamente un solo usuario.** 1,325 requests en ~1 año (~7/día);
minuto pico 6 req (~0.1 req/s); concurrencia media estimada ~2. **No hay histórico de
concurrencia real** del cual extrapolar → la capacidad se respondió con load test.

**2. La infra propia es rápida y NO serializa de forma grave.** La instrumentación nueva
mostró, por request: `history_load` ≈ **1.8 ms**, `persist_messages` ≈ **4.6 ms**. Es decir,
las llamadas pymongo síncronas que corren en el event loop suman **~7 ms/request** — reales,
pero **despreciables** frente a los segundos del LLM. (Esto corrige la hipótesis inicial de que
el Mongo síncrono era el cuello de botella: lo es en teoría, pero su magnitud es mínima porque
Mongo responde en milisegundos.)

**3. Un worker escala bien bajo latencia tipo-LLM (mockeada ~1 s):**

| Concurrencia | Throughput (req/s) | p50 (s) | p95 (s) | Errores |
|---|---|---|---|---|
| 1  | 1.0  | 0.98 | 1.02 | 0% |
| 5  | 4.8  | 1.03 | 1.12 | 0% |
| 10 | 7.0  | 1.53 | 1.66 | 0% |
| 20 | 14.9 | 1.30 | 1.63 | 0% |
| 40 | 24.8 | 1.55 | 1.79 | 0% |

El throughput sube con la concurrencia (sin errores ni timeouts); la p50 sube de ~1.0→1.5 s,
señal de que las ráfagas de Mongo en el loop sí roban algo de tiempo, pero sin colapsar.

**4. La latencia real está dominada por el LLM.** Histórico (modelos mezclados):
p50 **13 s**, p95 **64 s**, p99 **87 s**. Con gpt-5 reasoning-low reciente es menor, pero sigue
en segundos. Aquí está el 95%+ del tiempo de respuesta.

**5. Observabilidad: cerramos el hueco principal.** Antes no había latencia por tool. Ahora
cada request persiste `tool_timings` y `phase_timings` en `message_backup`; `analyze_timings.py`
los agrega (p50/p95 por tool y por fase) con datos reales de producción.

## Restricciones reales al escalar (lo que pega primero)
1. **Límites de la cuenta OpenAI** (TPM/RPM/concurrencia) para gpt-5 y gpt-4.1-mini — **el techo
   externo**. No lo controla nuestro código.
2. **`InMemoryRateLimiter` del agente**: 10 req/s **por worker** (×4 = 40 req/s) y no compartido;
   hay que alinearlo al tier real de OpenAI.
3. **Threadpool por defecto** (`min(32, cpu+4)`): cada tool síncrona ocupa un hilo durante su
   ejecución (algolia HTTP hasta 10 s). Muchas tools lentas en paralelo pueden agotar hilos.
4. **Rate limit propio no compartido** entre workers (límite efectivo ×4) y crecía sin tope
   (ya mitigado el crecimiento, ver quick-wins).

## Quick-wins aplicados en este cambio (seguros, verificados)
- **Instrumentación F1**: `TimingCallbackHandler` reescrito (seguro ante tools en paralelo,
  sin prints) y cableado al `astream`; se persisten `tool_timings` + `phase_timings`.
- **FX cacheado con TTL** (`moneda_api.py`): ya no pega a MySQL en cada conversión.
- **Pool MySQL** en `inventory.py`, `moneda_api.py` y `status.descargas_enviadas` (antes abrían
  conexión fresca → TCP+auth por llamada).
- **Dedupe MongoClient**: `ToolAgent` usa el singleton `get_db()` (evita un cliente/pool extra
  por worker).
- **Prune de `_hits`** (`security.py`): el dict de rate limit ya no crece sin límite.
- **Índices/TTL**: `create_indexes.py` listo (opt-in; el TTL es destructivo — confirmar retención).
- Tests: **97/97** unit en verde tras los cambios.

## Backlog priorizado (cambios mayores — NO incluidos aquí)
| # | Acción | Impacto | Esfuerzo |
|---|--------|---------|----------|
| 1 | **Validar límites de la cuenta OpenAI** (TPM/RPM) para gpt-5 y gpt-4.1-mini | Alto | Bajo |
| 2 | **Load test con LLM real en staging** → concurrencia real por worker + costo/req | Alto | Medio |
| 3 | **Threadpool explícito + timeouts** en toda tool; evaluar tools async (algolia) | Alto | Medio |
| 4 | **Rate limit en Redis** (compartido entre workers; `PODMAN_REDIS_URL` ya existe) | Medio | Medio |
| 5 | **Alinear `InMemoryRateLimiter`** al tier OpenAI (hoy 10 rps/worker, no compartido) | Medio | Bajo |
| 6 | **Escala horizontal** (más workers/instancias tras LB) una vez OpenAI sea el único techo | Alto (Fase C) | Medio |
| 7 | **TTL de `InMemoryCache`** del LLM (crecimiento de memoria) | Bajo | Bajo |

**Quick-wins NO aplicados a propósito** (se mueven al backlog por no ser de bajo riesgo):
cachear `CloudScraper` en algolia (la instancia se mutaría por request → no es thread-safe) y
precargar FAISS de support en el `lifespan` (opcional).

## Cómo reproducir
```bash
# 0) Baseline (lectura)
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evaluation/perf/baseline.py

# 1) Servidor con LLM mockeado (sin costo OpenAI). 1 worker = techo por worker.
CT_FAKE_LLM=1 PYTHONIOENCODING=utf-8 PYTHONUTF8=1 .venv/Scripts/python.exe \
  -m uvicorn ct.main:app --host 127.0.0.1 --port 8012

# 2) Rampa de carga + limpieza
.venv/Scripts/python.exe evaluation/perf/loadtest.py --url http://127.0.0.1:8012/chat \
  --concurrency 1,2,5,10,20,40 --requests 50
.venv/Scripts/python.exe evaluation/perf/cleanup_loadtest.py --apply

# 3) Latencia por tool/fase (datos reales, tras desplegar la instrumentación)
.venv/Scripts/python.exe evaluation/perf/analyze_timings.py --days 30
```
Para el techo de los 4 workers reales: levantar gunicorn con `-k uvicorn.workers.UvicornWorker
--workers 4` y `CT_FAKE_LLM=1`, y correr `loadtest.py` con concurrencias mayores.

## Telemetría de UI (decisión "¿sidebar?")
Para resolver con datos el debate de diseño (panel angosto vs. expandible) se añadió:
- **Botón expandir/contraer** en el panel (~400px ↔ `min(680px, 96vw)`), con estado recordado en
  la sesión; en móvil se oculta (ya es full-screen).
- **Endpoint `POST /ui-event`** que escribe a **archivo JSONL** (no MongoDB), y eventos del widget:
  `open`, `close`, `expand`, `collapse`, `product_click` (este último como proxy de completitud).
- Análisis: `evaluation/perf/analyze_ui_events.py` (tasa de expand y de product_click por apertura).

> **Por qué a archivo y no a Mongo:** el usuario de Mongo no puede crear colecciones nuevas
> (permisos por colección → `not authorized` code 13). La telemetría se guarda en
> `logs/ui_events.jsonl` (configurable con `CHATBOT_UI_EVENTS_LOG`), un append atómico por evento,
> seguro entre los 4 workers. **Sin acción de DBA.** Rotación: usar `logrotate` del sistema sobre
> ese archivo (como con el resto de `logs/`). Si el archivo no se puede escribir, la telemetría
> degrada en silencio y loguea **una** advertencia (nunca rompe la UX).

### Cómo leer la decisión con los datos
- **Tasa de `expand` por apertura alta** → los usuarios necesitan más ancho → favorece el
  panel expandible / sidebar.
- **`product_click` por apertura** → mide si el chat realmente lleva a producto (completitud).
- Cruzar con la profundidad de sesión y `close` inmediato para detectar fricción.
