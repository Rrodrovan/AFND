#!/usr/bin/env bash
# Instala la sincronizacion diaria de TerraShift en la VM (Ubuntu + PostgreSQL local).
# Se puede ejecutar varias veces: no pisa lo que ya existe sin preguntar.
#
#   cd ~/AFND && git pull && bash deploy/setup-sync.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ME="$(id -un)"
ENV_FILE=/etc/terrashift-etl.env

# Valores entre comillas simples: systemd y bash los leen igual (sin expandir $ ni espacios).
quoted() {
    case "$1" in
        *"'"*|*'\'*) echo "Los valores no pueden contener comillas simples (') ni barras invertidas (\\)." >&2; exit 1 ;;
    esac
    printf "'%s'" "$1"
}

echo "== 1/5 Python =="
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "Se necesita Python 3.10 o superior (tienes $(python3 --version 2>&1))." >&2
    exit 1
fi
if ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
    sudo apt-get update -y && sudo apt-get install -y python3-venv
fi
python3 -m venv "$REPO/python-etl/.venv"
"$REPO/python-etl/.venv/bin/pip" install --quiet --upgrade pip
"$REPO/python-etl/.venv/bin/pip" install --quiet "$REPO/python-etl"

echo "== 2/5 Tablas de seguimiento y de zonas (database/init/03 y 04) =="
if [ ! -f "$ENV_FILE" ]; then
    echo "Voy a crear $ENV_FILE (solo root puede leerlo). Los datos que escribas no se muestran."
    read -r  -p "Base de datos [terrashift_db]: " DB_NAME;  DB_NAME=${DB_NAME:-terrashift_db}
    read -r  -p "Usuario de la base [terrashift_user]: " DB_USER;  DB_USER=${DB_USER:-terrashift_user}
    read -r -s -p "Contrasena de la base: " DB_PASS; echo
    read -r  -p "Usuario de NASA Earthdata: " ED_USER
    read -r -s -p "Contrasena de NASA Earthdata: " ED_PASS; echo
    echo "Caja de la zona piloto: min_lon,min_lat,max_lon,max_lat (Enter = valor de EJEMPLO, cambialo por el real)"
    read -r  -p "PILOT_ZONE_BBOX [-86.70,13.40,-86.50,13.60]: " BBOX; BBOX=${BBOX:--86.70,13.40,-86.50,13.60}
    read -r  -p "Inicio del historico [2015-04-01]: " START; START=${START:-2015-04-01}
    ( umask 077; sudo tee "$ENV_FILE" >/dev/null <<ENV
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=$(quoted "$DB_NAME")
POSTGRES_USER=$(quoted "$DB_USER")
POSTGRES_PASSWORD=$(quoted "$DB_PASS")
EARTHDATA_USERNAME=$(quoted "$ED_USER")
EARTHDATA_PASSWORD=$(quoted "$ED_PASS")
PILOT_ZONE_BBOX=$(quoted "$BBOX")
ETL_START_DATE=$(quoted "$START")
ENV
    )
    sudo chown root:root "$ENV_FILE"; sudo chmod 600 "$ENV_FILE"
    unset DB_PASS ED_PASS
else
    echo "$ENV_FILE ya existe; no lo toco."
fi

# Aplica el SQL de seguimiento con las credenciales del mismo archivo (la contrasena no pasa por la linea de comandos).
for sql in 03_ingest_tracking.sql 04_zone_requests.sql; do
    sudo bash -c "set -a; . '$ENV_FILE'; set +a; PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -v ON_ERROR_STOP=1 -q -h \"\$POSTGRES_HOST\" -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -f '$REPO/database/init/$sql'"
done

echo "== 3/5 Servicio y temporizador =="
for unit in terrashift-sync.service terrashift-sync.timer; do
    sed -e "s|__USER__|$ME|g" -e "s|__REPO__|$REPO|g" "$REPO/deploy/$unit" | sudo tee "/etc/systemd/system/$unit" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now terrashift-sync.timer

echo "== 4/5 Plan de la proxima sincronizacion (no descarga nada) =="
sudo bash -c "set -a; . '$ENV_FILE'; set +a; cd '$REPO/python-etl' && PYTHONDONTWRITEBYTECODE=1 '$REPO/python-etl/.venv/bin/python' -m src.cli sync --all-zones --dry-run"

echo "== 5/5 Listo =="
systemctl list-timers terrashift-sync.timer --no-pager || true
cat <<MSG

Para sincronizar ahora mismo (la primera vez tarda, trae todo el historico):
    sudo systemctl start terrashift-sync.service --no-block
    journalctl -u terrashift-sync.service -f
Para ver el estado desde la base:
    curl -s http://localhost:8080/api/v1/zones/piloto/data-status
MSG
