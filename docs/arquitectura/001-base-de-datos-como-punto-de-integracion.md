# ADR 001 · La base de datos es el punto de integración

- **Estado:** aceptada
- **Contexto:** el equipo desarrolla en paralelo el motor analítico (Python) y el backend (Java / Spring Boot), con poco tiempo.

## Decisión

Python y Java **no se llaman entre sí**. Se comunican únicamente a través de PostgreSQL/PostGIS.

| Servicio | Escribe | Lee |
|---|---|---|
| `python-etl` | `zone`, `soil_profile`, `climate_daily`, `soil_moisture`, `vegetation_index` | — |
| `java-backend` | `strategy_result` | todas las tablas |
| `database/seeds` | `crop`, `strategy`, `analog_region` | — |

## Consecuencias

**A favor**

- Cada servicio se desarrolla, prueba y despliega por separado.
- El contrato entre equipos es el esquema SQL (`database/init/02_schema.sql`), fácil de revisar.
- Las cargas del ETL son idempotentes (UPSERT), por lo que se pueden repetir sin duplicar datos.

**En contra**

- Cualquier cambio de esquema afecta a ambos servicios: debe avisarse al equipo y registrarse en `database/migrations/`.
- No hay notificación en tiempo real entre servicios; el backend consulta el estado actual de la base de datos.

## Nota sobre el contrato del README

La sección 3 del README menciona tablas con prefijos `raw_*`, `metrics_*` y `app_*`. El esquema inicial usa
los nombres de la tabla "Modelo de datos (borrador)" de ese mismo README. Si el equipo prefiere los prefijos,
conviene renombrar en una migración y actualizar el ETL y el backend a la vez.
