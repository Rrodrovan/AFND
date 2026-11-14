-- Esquema inicial de TerraShift (modelo de datos de la sección 3 del README).
--
-- Propiedad de escritura (la base de datos es el punto de integración):
--   python-etl  -> zone, soil_profile, climate_daily, soil_moisture, vegetation_index
--   java-backend -> strategy_result
--   catálogos (crop, strategy, analog_region) -> database/seeds

-- ---------------------------------------------------------------------------
-- Zonas y suelo
-- ---------------------------------------------------------------------------
CREATE TABLE zone (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    geom        geometry(MultiPolygon, 4326) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX zone_geom_gix ON zone USING GIST (geom);

CREATE TABLE soil_profile (
    zone_id             INTEGER PRIMARY KEY REFERENCES zone (id) ON DELETE CASCADE,
    texture             TEXT,
    organic_matter_pct  REAL,
    field_capacity      REAL,
    wilting_point       REAL,
    notes               TEXT
);

-- ---------------------------------------------------------------------------
-- Series observadas (NASA)
-- ---------------------------------------------------------------------------
CREATE TABLE climate_daily (
    zone_id      INTEGER NOT NULL REFERENCES zone (id) ON DELETE CASCADE,
    date         DATE NOT NULL,
    precip_mm    REAL,
    t2m_c        REAL,
    t2m_max_c    REAL,
    t2m_min_c    REAL,
    rh2m_pct     REAL,
    solar_mj_m2  REAL,
    source       TEXT NOT NULL DEFAULT 'NASA POWER',
    PRIMARY KEY (zone_id, date)
);

CREATE TABLE soil_moisture (
    zone_id          INTEGER NOT NULL REFERENCES zone (id) ON DELETE CASCADE,
    date             DATE NOT NULL,
    surface_m3m3     REAL,
    rootzone_m3m3    REAL,
    source           TEXT NOT NULL DEFAULT 'SMAP',
    PRIMARY KEY (zone_id, date)
);

CREATE TABLE vegetation_index (
    zone_id  INTEGER NOT NULL REFERENCES zone (id) ON DELETE CASCADE,
    date     DATE NOT NULL,
    source   TEXT NOT NULL CHECK (source IN ('LANDSAT', 'MODIS')),
    ndvi     REAL,
    evi      REAL,
    PRIMARY KEY (zone_id, date, source)
);

-- ---------------------------------------------------------------------------
-- Catálogos
-- ---------------------------------------------------------------------------
CREATE TABLE crop (
    id           SERIAL PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    cycle_days   INTEGER,
    notes        TEXT
);

CREATE TABLE strategy (
    id           SERIAL PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    focus        TEXT NOT NULL,
    description  TEXT
);

CREATE TABLE analog_region (
    id              SERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    country         TEXT NOT NULL,
    climate_notes   TEXT,
    soil_notes      TEXT,
    strategy_id     INTEGER REFERENCES strategy (id),
    reference       TEXT
);

-- ---------------------------------------------------------------------------
-- Resultados de la comparación (escribe el backend)
-- ---------------------------------------------------------------------------
CREATE TABLE strategy_result (
    id            SERIAL PRIMARY KEY,
    zone_id       INTEGER NOT NULL REFERENCES zone (id) ON DELETE CASCADE,
    strategy_id   INTEGER NOT NULL REFERENCES strategy (id),
    crop_id       INTEGER NOT NULL REFERENCES crop (id),
    scenario      TEXT NOT NULL CHECK (scenario IN ('normal', 'seco', 'canicula')),
    indicator     TEXT NOT NULL,
    value_mid     DOUBLE PRECISION,
    value_min     DOUBLE PRECISION,
    value_max     DOUBLE PRECISION,
    unit          TEXT,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (zone_id, strategy_id, crop_id, scenario, indicator)
);
CREATE INDEX strategy_result_zone_idx ON strategy_result (zone_id, strategy_id);
