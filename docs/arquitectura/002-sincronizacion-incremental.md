# ADR 002 — Sincronización incremental y estado de los datos en la base

**Estado:** propuesto

## Contexto
Las series de la NASA (POWER, SMAP, MODIS, Landsat) crecen cada día. La ingesta manual con rango fijo
(`ingest`) obligaba a recordar qué faltaba y a volver a descargar todo.

## Decisión
- Un comando `sync` calcula, por fuente, la ventana `[última fecha cargada − solape, hoy − latencia]` y la descarga
  en tramos. Un temporizador de systemd lo ejecuta a diario en la VM.
- El seguimiento vive **en la base de datos** (tabla `ingest_run`, columna `updated_at`, vistas `v_data_freshness`
  y `v_observed_monthly`), coherente con ADR 001: la base es el punto de integración entre el ETL y el backend.
  El backend solo **lee** esas vistas; no conoce a Python ni a la NASA.
- La fecha "datos hasta" sale de las tablas de datos, no de un contador aparte, para que no pueda desincronizarse.
- La página muestra ese estado, de modo que un dato atrasado o una sincronización fallida se ven en lugar de ocultarse.

## Consecuencias
- Repetir ventanas es seguro (UPSERT) y absorbe las correcciones que haga la NASA a los datos recientes.
- Una fuente que falla no detiene a las demás y deja su error en `ingest_run`; el texto del error no se publica en la API.
- Latencias y solapes son estimaciones (ver `python-etl/src/sync.py`); si resultan erróneas, el efecto es perder
  unos días de frescura, no corromper datos.
- Una versión nueva de un producto (p. ej. SMAP) solo genera un aviso: cambiarla es una decisión manual.
