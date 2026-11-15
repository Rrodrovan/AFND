# Despliegue en la VM (Google Cloud, Ubuntu)

## Sincronización diaria de datos NASA

Instala un temporizador de systemd que ejecuta `python -m src.cli sync` todos los días a las 03:40 (hora de Managua).
Si la VM estaba apagada a esa hora, lo ejecuta al encenderse.

```bash
cd ~/AFND
git pull
bash deploy/setup-sync.sh
```

El script, que se puede repetir sin problema:

1. Crea el entorno de Python (`python-etl/.venv`) e instala las dependencias.
2. Pide —sin mostrarlas— la contraseña de la base y tus credenciales de NASA Earthdata, y las guarda en
   `/etc/terrashift-etl.env` (propietario root, permisos 600). **Nunca están en el repositorio.**
3. Aplica `database/init/03_ingest_tracking.sql` (tablas y vistas de seguimiento; es idempotente).
4. Instala y activa `terrashift-sync.service` y `terrashift-sync.timer`.
5. Muestra el plan de la próxima sincronización sin descargar nada.

Para lanzar la primera sincronización ya (trae todo el histórico y puede tardar horas):

```bash
sudo systemctl start terrashift-sync.service --no-block
journalctl -u terrashift-sync.service -f
```

Estado: `systemctl list-timers terrashift-sync.timer` y `curl -s http://localhost:8080/api/v1/zones/piloto/data-status`.

## Actualizar la unidad de sincronización

Si cambia `deploy/terrashift-sync.service` o el timer, **no los copies con `cp`**: el archivo del repo trae los marcadores `__USER__` y `__REPO__` y systemd rechaza la unidad (y mata el sync en curso). Reinstálalos sustituyéndolos, igual que hace `setup-sync.sh`:

```bash
REPO=$HOME/AFND; ME=$(whoami)
for unit in terrashift-sync.service terrashift-sync.timer; do
  sed -e "s|__USER__|$ME|g" -e "s|__REPO__|$REPO|g" "$REPO/deploy/$unit" | sudo tee "/etc/systemd/system/$unit" >/dev/null
done
sudo systemctl daemon-reload
systemctl cat terrashift-sync.service | grep -E "User=|WorkingDirectory=|ExecStart="   # no debe quedar ningún "__"
```

Hazlo cuando el servicio no esté corriendo (`systemctl is-active terrashift-sync.service` → `inactive`), porque `daemon-reload` con una unidad inválida termina el sync.

## Actualizar el backend

Los endpoints nuevos (`/data-status`, `/observations/monthly`) requieren recompilar:

```bash
cd ~/AFND/java-backend && mvn -q -DskipTests package && sudo systemctl restart terrashift
```

## Zonas propuestas desde el mapa

Necesita (una sola vez) el SQL de zonas, un token de administrador y la cabecera `X-Real-IP` en Nginx.

```bash
cd ~/AFND && git pull

# 1. SQL de zonas (si ya corriste setup-sync.sh después de este cambio, ya está aplicado)
sudo bash -c 'set -a; . /etc/terrashift-etl.env; set +a; PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -h localhost -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f database/init/04_zone_requests.sql'

# 2. Token de administrador (se genera uno y se guarda en el archivo del backend)
sudo grep -q TERRASHIFT_ADMIN_TOKEN /etc/terrashift.env || echo "TERRASHIFT_ADMIN_TOKEN=$(openssl rand -hex 24)" | sudo tee -a /etc/terrashift.env >/dev/null
sudo grep TERRASHIFT_ADMIN_TOKEN /etc/terrashift.env     # ese es el token que pegas en admin.html; no lo compartas

# 3. Nginx: debe pasar la IP real del visitante
sudo grep -rn "proxy_pass\|X-Real-IP" /etc/nginx/sites-enabled/
#   Si no sale X-Real-IP, agrega justo debajo de la línea proxy_pass:
#       proxy_set_header X-Real-IP $remote_addr;
#   y recarga:  sudo nginx -t && sudo systemctl reload nginx

# 4. Recompilar y reiniciar el backend
cd java-backend && mvn -q -DskipTests package && sudo systemctl restart terrashift
cd .. && bash deploy/setup-sync.sh      # vuelve a instalar el servicio (ahora sincroniza todas las zonas aprobadas)
```

Revisar solicitudes: abre `https://rrodrovan.github.io/AFND/admin.html`, pega el token y aprueba o rechaza.
Después de aprobar, la descarga empieza en la siguiente sincronización (o ya: `sudo systemctl start terrashift-sync.service --no-block`).

### Si el backend no arranca (502 Bad Gateway)

Tras reiniciar, Spring tarda entre 10 y 40 segundos en responder; Nginx da 502 mientras tanto. Si persiste:

```bash
systemctl is-active terrashift
sudo journalctl -u terrashift -n 60 --no-pager     # la causa suele estar en las últimas líneas
```

Si por error se agregó más de un `TERRASHIFT_ADMIN_TOKEN` a `/etc/terrashift.env`, vale el último. Para ver cuál es sin mostrar los demás:
`sudo grep TERRASHIFT_ADMIN_TOKEN /etc/terrashift.env | tail -1`.
