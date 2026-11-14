#!/bin/bash
# Ejecuta los scripts de database/seeds (montados en /seeds) después de crear el esquema.
set -e

for f in /seeds/*.sql; do
    echo "Cargando semilla: $f"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f"
done
