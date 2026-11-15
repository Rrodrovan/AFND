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

## Actualizar el backend

Los endpoints nuevos (`/data-status`, `/observations/monthly`) requieren recompilar:

```bash
cd ~/AFND/java-backend && mvn -q -DskipTests package && sudo systemctl restart terrashift
```
