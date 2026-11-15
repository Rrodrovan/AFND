# ADR 003 — Zonas propuestas desde el mapa con aprobación del equipo

**Estado:** propuesto

## Contexto
La zona piloto salía de una variable de entorno (`PILOT_ZONE_BBOX`). Queremos que el usuario la elija en un mapa.
Cada zona nueva hace que el ETL descargue datos de la NASA con **la cuenta de Earthdata del equipo**: tareas lentas y con
límites de uso. Si cualquiera pudiera crear zonas libremente, podría saturar la cola o agotar esa cuenta.

## Decisión
- Cualquiera puede **proponer** una zona dibujando un rectángulo (dos clics). El backend la guarda como `pending`.
- Solo un administrador la **aprueba** (página `admin.html`, token en la cabecera `X-Admin-Token`). Hasta entonces no se
  descarga nada y la zona no es pública.
- El ETL (`sync --all-zones`) sincroniza solo las zonas `approved`, leyendo su caja de la base. La base sigue siendo el
  punto de integración (ADR 001).
- Límites en el servidor (la validación del navegador es solo ayuda): dentro de Nicaragua, 0,02°–0,5° por lado,
  5 solicitudes por hora por origen, máximo 20 pendientes, nombre de 3 a 60 caracteres con signos simples.
- El token de administrador viene de `TERRASHIFT_ADMIN_TOKEN`; sin él, los endpoints de administración responden 404.
  Se compara en tiempo constante y 10 fallos por hora desde un mismo origen bloquean nuevos intentos.
- Leaflet se incluye en `frontend/vendor/` (sin CDN, sin depender de un tercero en tiempo de carga).

## Consecuencias
- El límite por origen usa la cabecera `X-Real-IP`, que debe fijar Nginx (`proxy_set_header X-Real-IP $remote_addr;`).
  Sin ella, todas las solicitudes comparten una clave y el límite pasa a ser global (más estricto, no más laxo).
- Un atacante podría agotar el cupo de 20 pendientes; el costo es solo que nadie más pueda proponer hasta revisarlas.
- Aprobar una zona no descarga al instante: la sincronización diaria la toma (o se lanza a mano el servicio).
- Los mosaicos del mapa vienen de OpenStreetMap (con su atribución); un filtro de red puede bloquearlos.
