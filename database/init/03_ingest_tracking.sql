-- Seguimiento de ingestas y vistas de lectura para el producto.
--
-- Es idempotente (IF NOT EXISTS; las vistas se recrean), así que sirve tanto en una base
-- nueva (docker-entrypoint-initdb.d) como para aplicarlo a mano sobre una base ya creada:
--     psql -h localhost -U terrashift_user -d terrashift_db -f database/init/03_ingest_tracking.sql

-- Cuándo se escribió por última vez cada fila (el UPSERT lo actualiza).
ALTER TABLE climate_daily    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE soil_moisture    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE vegetation_index ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Una fila por cada intento de sincronización de una fuente.
CREATE TABLE IF NOT EXISTS ingest_run (
    id             BIGSERIAL PRIMARY KEY,
    zone_id        INTEGER NOT NULL REFERENCES zone (id) ON DELETE CASCADE,
    source         TEXT NOT NULL CHECK (source IN ('power', 'smap', 'modis', 'landsat')),
    status         TEXT NOT NULL CHECK (status IN ('running', 'ok', 'up_to_date', 'error')),
    range_start    DATE,
    range_end      DATE,
    rows_loaded    INTEGER NOT NULL DEFAULT 0,
    last_data_date DATE,
    error          TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ingest_run_zone_source_idx ON ingest_run (zone_id, source, started_at DESC);

-- Las vistas no guardan datos: se recrean para poder cambiar sus columnas entre versiones.
DROP VIEW IF EXISTS v_data_freshness;
DROP VIEW IF EXISTS v_observed_monthly;

-- Estado de cada fuente por zona: hasta qué fecha hay datos y cuándo se sincronizó por última vez.
-- La fecha sale de las tablas de datos (siempre es verdad); lo demás, de ingest_run.
CREATE VIEW v_data_freshness AS
WITH series AS (
    SELECT zone_id, 'power'::text AS source, 'NASA POWER (clima diario)'::text AS label,
           min(date) AS first_date, max(date) AS last_date, count(*) AS n_rows,
           max(updated_at) AS last_written_at
    FROM climate_daily GROUP BY zone_id
    UNION ALL
    SELECT zone_id, 'smap', 'NASA SMAP (humedad del suelo)',
           min(date), max(date), count(*), max(updated_at)
    FROM soil_moisture GROUP BY zone_id
    UNION ALL
    SELECT zone_id, 'modis', 'MODIS (NDVI/EVI, 250 m)',
           min(date), max(date), count(*), max(updated_at)
    FROM vegetation_index WHERE source = 'MODIS' GROUP BY zone_id
    UNION ALL
    SELECT zone_id, 'landsat', 'Landsat / HLS (NDVI/EVI, 30 m)',
           min(date), max(date), count(*), max(updated_at)
    FROM vegetation_index WHERE source = 'LANDSAT' GROUP BY zone_id
),
sources AS (
    SELECT z.id AS zone_id, s.source, s.label
    FROM zone z
    CROSS JOIN (VALUES
        ('power',   'NASA POWER (clima diario)'),
        ('smap',    'NASA SMAP (humedad del suelo)'),
        ('modis',   'MODIS (NDVI/EVI, 250 m)'),
        ('landsat', 'Landsat / HLS (NDVI/EVI, 30 m)')
    ) AS s (source, label)
),
last_run AS (
    SELECT DISTINCT ON (zone_id, source)
           zone_id, source, status, finished_at, error
    FROM ingest_run
    WHERE status <> 'running'
    ORDER BY zone_id, source, started_at DESC
),
last_good AS (
    SELECT zone_id, source, max(finished_at) AS finished_at
    FROM ingest_run
    WHERE status IN ('ok', 'up_to_date')
    GROUP BY zone_id, source
)
SELECT z.code AS zone_code,
       so.source,
       so.label,
       se.first_date,
       se.last_date,
       COALESCE(se.n_rows, 0) AS n_rows,
       se.last_written_at,
       lg.finished_at AS last_sync_ok_at,
       lr.status      AS last_run_status,
       lr.finished_at AS last_run_at,
       lr.error       AS last_run_error
FROM sources so
JOIN zone z ON z.id = so.zone_id
LEFT JOIN series   se ON se.zone_id = so.zone_id AND se.source = so.source
LEFT JOIN last_run lr ON lr.zone_id = so.zone_id AND lr.source = so.source
LEFT JOIN last_good lg ON lg.zone_id = so.zone_id AND lg.source = so.source;

-- Resumen mensual de lo observado por la NASA, listo para graficar.
-- Los meses sin dato de una variable quedan en NULL (no se rellenan ni se inventan).
CREATE VIEW v_observed_monthly AS
WITH months AS (
    SELECT zone_id, date_trunc('month', date)::date AS month FROM climate_daily
    UNION
    SELECT zone_id, date_trunc('month', date)::date FROM soil_moisture
    UNION
    SELECT zone_id, date_trunc('month', date)::date FROM vegetation_index
),
climate AS (
    SELECT zone_id, date_trunc('month', date)::date AS month,
           sum(precip_mm) AS precip_mm_total,
           count(precip_mm) AS precip_days,
           avg(t2m_c) AS t2m_mean_c
    FROM climate_daily GROUP BY 1, 2
),
soil AS (
    SELECT zone_id, date_trunc('month', date)::date AS month,
           avg(surface_m3m3) AS surface_m3m3_mean,
           avg(rootzone_m3m3) AS rootzone_m3m3_mean
    FROM soil_moisture GROUP BY 1, 2
),
veg AS (
    SELECT zone_id, date_trunc('month', date)::date AS month,
           avg(ndvi) FILTER (WHERE source = 'MODIS')   AS ndvi_modis_mean,
           avg(ndvi) FILTER (WHERE source = 'LANDSAT') AS ndvi_landsat_mean
    FROM vegetation_index GROUP BY 1, 2
)
SELECT z.code AS zone_code,
       m.month,
       round(c.precip_mm_total::numeric, 1)::float8 AS precip_mm_total,
       c.precip_days,
       round(c.t2m_mean_c::numeric, 1)::float8 AS t2m_mean_c,
       round(s.surface_m3m3_mean::numeric, 4)::float8 AS surface_m3m3_mean,
       round(s.rootzone_m3m3_mean::numeric, 4)::float8 AS rootzone_m3m3_mean,
       round(v.ndvi_modis_mean::numeric, 4)::float8 AS ndvi_modis_mean,
       round(v.ndvi_landsat_mean::numeric, 4)::float8 AS ndvi_landsat_mean
FROM months m
JOIN zone z ON z.id = m.zone_id
LEFT JOIN climate c ON c.zone_id = m.zone_id AND c.month = m.month
LEFT JOIN soil    s ON s.zone_id = m.zone_id AND s.month = m.month
LEFT JOIN veg     v ON v.zone_id = m.zone_id AND v.month = m.month;
