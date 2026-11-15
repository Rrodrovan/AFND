# python-etl · Ingesta de datos NASA

Descarga series de tiempo de la NASA para la zona piloto y las carga en PostgreSQL/PostGIS.

| Fuente | Producto (versión vigente al 14-nov-2026) | Qué se guarda | Tabla | Acceso |
|---|---|---|---|---|
| NASA POWER | API diaria, comunidad AG | Precipitación, temperatura, humedad relativa, radiación solar | `climate_daily` | API pública directa |
| SMAP | `SPL4SMGP.008` (9 km) | Humedad superficial y de zona de raíces (m³/m³) | `soil_moisture` | AppEEARS |
| MODIS | `MOD13Q1.061` (250 m, cada 16 días) | NDVI y EVI | `vegetation_index` (`source = 'MODIS'`) | AppEEARS |
| Landsat | `HLSL30.020` (30 m) | NDVI y EVI calculados | `vegetation_index` (`source = 'LANDSAT'`) | AppEEARS |

SMAP, MODIS y Landsat se piden a **AppEEARS**, la API de la NASA que recorta y entrega solo los píxeles
solicitados. Requiere una cuenta gratuita en https://urs.earthdata.nasa.gov.

## Ejecutar en el servidor

```bash
cd ~/AFND/python-etl
sudo apt install -y python3-venv
python3 -m venv .venv && . .venv/bin/activate
pip install requests "psycopg[binary]"

# Credenciales: en un archivo propio, nunca en el repositorio ni en el chat
cat > ~/.terrashift-etl.env <<'EOF'
POSTGRES_HOST=localhost
POSTGRES_DB=terrashift_db
POSTGRES_USER=terrashift_user
POSTGRES_PASSWORD=...
EARTHDATA_USERNAME=...
EARTHDATA_PASSWORD=...
PILOT_ZONE_BBOX=min_lon,min_lat,max_lon,max_lat
ETL_START_DATE=2015-04-01
ETL_END_DATE=2025-12-31
EOF
chmod 600 ~/.terrashift-etl.env
set -a; . ~/.terrashift-etl.env; set +a

# Prueba corta primero (un trimestre, una fuente)
python -m src.cli ingest --zone piloto --source smap --start 2024-01-01 --end 2024-03-31

# Todas las fuentes, rango completo
python -m src.cli ingest --zone piloto --source all
```

Opciones: `--source power|smap|modis|landsat|landsat-modis|all`, `--grid N` (rejilla de N×N puntos, por
defecto 3), `--timeout-min` (espera máxima por tarea de AppEEARS, por defecto 120).

Las tareas de AppEEARS entran en una cola de la NASA: pueden tardar de minutos a horas. Si una fuente falla,
las demás continúan y el comando termina con código 1 indicando cuáles fallaron. Es seguro repetirlo: las
cargas son idempotentes.

## Actualización automática (`sync`)

`ingest` carga un rango fijo; `sync` es el comando pensado para correr todos los días y **trae solo lo que falta**:

```bash
python -m src.cli sync --zone piloto            # lo nuevo de cada fuente
python -m src.cli sync --zone piloto --dry-run  # solo muestra qué pediría (no descarga ni escribe)
python -m src.cli sync --zone piloto --source smap
python -m src.cli sync --all-zones              # todas las zonas aprobadas (es lo que corre a diario)
```

Con `--all-zones` se sincronizan todas las zonas con estado `approved` de la tabla `zone`, leyendo su caja de la base
(las dibujadas en el mapa de la página y aprobadas por el equipo). Si `PILOT_ZONE_BBOX` está definida, la zona `piloto`
se crea o actualiza primero desde ahí. **Si cambias esa caja, los datos ya cargados siguen siendo los de la caja anterior**
(el comando lo avisa); bórralos de `climate_daily`, `soil_moisture` y `vegetation_index` si quieres series coherentes.

Para cada fuente mira la última fecha cargada en la base y pide desde ahí hasta `hoy − latencia`
(la NASA publica con retraso). La primera vez, con la base vacía, descarga el histórico desde `ETL_START_DATE`
en tramos (cada uno se guarda al terminar, así un corte no pierde lo ya cargado).

| Fuente | Latencia | Se re-piden | Nuevo dato posible cada | Tramo |
|---|---|---|---|---|
| NASA POWER | 5 d | 14 d | 1 d | 5 años |
| SMAP | 5 d | 7 d | 1 d | 1 año |
| MODIS | 24 d | 32 d | 16 d | 2 años |
| Landsat/HLS | 7 d | 15 d | 5 d | 1 año |

*Re-piden*: la NASA puede corregir los últimos datos; repetirlos no duplica nada (UPSERT).
Si no puede haber datos nuevos todavía, la fuente se marca "al día" sin consultar a la NASA.
Las latencias son estimaciones prudentes (`src/sync.py`, `POLICIES`), no mediciones: ajústalas si ves que la NASA publica antes o después.

Cada intento queda en la tabla `ingest_run`; la vista `v_data_freshness` resume por fuente hasta qué fecha hay datos y
cómo fue la última sincronización, y la API la publica en `/api/v1/zones/{zona}/data-status`, que alimenta el panel de la página.

Al terminar, `sync` consulta el catálogo público de AppEEARS y **avisa** si existe una versión de SMAP más nueva que
`SPL4SMGP.008`. No cambia de versión por su cuenta: una versión nueva puede renombrar capas, y es mejor revisarlo a mano.

Instalación del temporizador diario en la VM: ver [`deploy/README.md`](../deploy/README.md).

## Cómo se obtiene un valor por zona

Se muestrea una **rejilla de N×N puntos** dentro de `PILOT_ZONE_BBOX` y se promedian por fecha los píxeles
válidos. Es una aproximación a la media de la zona, no una estadística zonal exacta. Con `--grid 1` se usa
solo el píxel del centro.

## Decisiones y supuestos

- **SMAP L4 en lugar de L3 (`SPL3SMP_E`)**: solo el L4 entrega humedad de la zona de raíces y no tiene vacíos
  entre pasadas del satélite.
- **MODIS**: se descartan los píxeles con calidad MODLAND 2 o 3 y con nubes mezcladas (capa `VI_Quality`).
- **Landsat**: se enmascaran nube, adyacente a nube y sombra (capa `Fmask`). NDVI = (NIR − Rojo)/(NIR + Rojo);
  EVI = 2.5·(NIR − Rojo)/(NIR + 6·Rojo − 7.5·Azul + 1).
- **No se incluye evapotranspiración** (MOD16A2GF): la tabla `vegetation_index` no tiene columna para ella.

## Pendiente de verificar contra el servicio real

- Las **latencias de `sync`** y la respuesta de `GET /product` (campos `Product`, `Version`, `Deleted`, `Available`) son supuestos; el aviso de versión nueva nunca hace fallar la sincronización.
Estos puntos se escribieron a partir de la documentación oficial, pero **no se han probado contra AppEEARS**
(el entorno de desarrollo no tenía acceso a la NASA). Si algo falla en la primera ejecución, el mensaje de
error lista las columnas recibidas para corregirlo rápido:

- Nombres de las columnas del CSV de resultados (`<Producto>_<Versión>_<Capa>`).
- Formato de la respuesta de `/status` y nombres de los archivos del bundle (se buscan los `*results*.csv`).
- Significado de los bits de `VI_Quality` y `Fmask`: confirmar con las guías de usuario de MOD13Q1 y HLS v2.0.
- Que las fechas pedidas queden dentro de la cobertura de cada producto (el código las ajusta al inicio
  conocido de cada uno).

## Pruebas

```bash
pip install pytest
python -m pytest -q
```
Las pruebas usan respuestas simuladas; no consumen la API de la NASA.
