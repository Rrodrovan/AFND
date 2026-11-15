-- Zonas propuestas desde el mapa de la página.
--
-- Una zona nueva nace 'pending' (la crea el backend con la solicitud de un visitante) y no se descarga nada
-- hasta que un administrador la aprueba. Idempotente: se puede aplicar a mano sobre una base ya creada:
--     psql -h localhost -U terrashift_user -d terrashift_db -f database/init/04_zone_requests.sql

ALTER TABLE zone ADD COLUMN IF NOT EXISTS status       TEXT NOT NULL DEFAULT 'approved';
ALTER TABLE zone ADD COLUMN IF NOT EXISTS min_lon      DOUBLE PRECISION;
ALTER TABLE zone ADD COLUMN IF NOT EXISTS min_lat      DOUBLE PRECISION;
ALTER TABLE zone ADD COLUMN IF NOT EXISTS max_lon      DOUBLE PRECISION;
ALTER TABLE zone ADD COLUMN IF NOT EXISTS max_lat      DOUBLE PRECISION;
ALTER TABLE zone ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE zone ADD COLUMN IF NOT EXISTS reviewed_at  TIMESTAMPTZ;

ALTER TABLE zone DROP CONSTRAINT IF EXISTS zone_status_check;
ALTER TABLE zone ADD CONSTRAINT zone_status_check CHECK (status IN ('pending', 'approved', 'rejected'));
ALTER TABLE zone DROP CONSTRAINT IF EXISTS zone_bbox_check;
ALTER TABLE zone ADD CONSTRAINT zone_bbox_check CHECK (
    min_lon IS NULL OR (min_lon < max_lon AND min_lat < max_lat
                        AND min_lon >= -180 AND max_lon <= 180 AND min_lat >= -90 AND max_lat <= 90));

-- Las zonas que ya existían (p. ej. 'piloto') quedan aprobadas y reciben su caja a partir de la geometría.
UPDATE zone
   SET min_lon = ST_XMin(geom), min_lat = ST_YMin(geom), max_lon = ST_XMax(geom), max_lat = ST_YMax(geom)
 WHERE min_lon IS NULL AND geom IS NOT NULL;

CREATE INDEX IF NOT EXISTS zone_status_idx ON zone (status);
