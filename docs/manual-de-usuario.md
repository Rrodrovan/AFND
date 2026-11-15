# Manual de usuario de TerraShift

TerraShift compara tres estrategias de rotación de cultivos (línea base tradicional, conservación hídrica y regeneración de suelos) para maíz y frijol en el Corredor Seco de Nicaragua, usando datos de la NASA. Es una herramienta de **apoyo a la decisión**: sus resultados son estimaciones con incertidumbre y no sustituyen la asesoría de un técnico agrónomo.

Página: https://rrodrovan.github.io/AFND/

## 1. Qué hay en la página

| Sección | Para qué sirve |
|---|---|
| **Zonas de estudio** (mapa) | Ver las zonas ya aprobadas y proponer una nueva |
| **Estado de la conexión** (etiqueta bajo el formulario) | "Datos en vivo" o "Datos de respaldo" |
| **Datos de la NASA en este servidor** | Hasta qué fecha llega cada fuente y qué se ha observado en la zona |
| **Tarjetas E1, E2, E3** | Resultados de cada estrategia por cultivo y escenario (año normal, seco, canícula) |

Si el servidor no responde (por ejemplo, un filtro de red lo bloquea), la página muestra una copia de respaldo y lo indica con la etiqueta amarilla. Esa copia no incluye el panel de datos de la NASA ni números actualizados.

## 2. Ver las estrategias de una zona

1. Escribe el código de la zona en el campo **Zona** (por defecto, `piloto`) y pulsa **Comparar**, o
2. haz clic sobre un rectángulo naranja del mapa (una zona aprobada).

Si una zona todavía no tiene resultados calculados, verás sus tarjetas con el aviso "Sin resultados calculados todavía".

## 3. Proponer una zona nueva

1. Pulsa **Dibujar zona**.
2. Haz clic en una esquina del área que te interesa y luego en la esquina opuesta.
3. Si el tamaño es correcto, el mensaje lo confirma (por ejemplo, "≈ 22 × 22 km"). Si no, te dice qué ajustar.
4. Escribe un nombre (3 a 60 caracteres; letras, números y signos simples) y pulsa **Enviar solicitud**.

La zona queda **pendiente**. El equipo la revisa y, si la aprueba, aparece en el mapa y empieza la descarga de sus datos. Esa descarga ocurre en la sincronización diaria, así que los primeros datos pueden tardar desde horas hasta un día; el histórico completo puede tardar más.

**Reglas de tamaño y ubicación**

- La zona debe estar dentro de Nicaragua.
- Cada lado debe medir entre unos 2 km y unos 55 km (0,02° a 0,5°).
- Se aceptan hasta 5 solicitudes por hora desde el mismo lugar, y el sistema admite un máximo de 20 solicitudes pendientes a la vez; si se llena, hay que esperar a que el equipo las revise.

## 4. Cómo usa TerraShift la zona dibujada (léelo antes de interpretar resultados)

**La zona es siempre un rectángulo.** El rectángulo delimita el área de estudio; no reproduce la forma exacta de un terreno o de una finca. Esto es una limitación conocida y conviene tenerla presente:

- **Clima (NASA POWER):** se toma un solo punto, el centro de la caja.
- **Humedad del suelo (SMAP) y vegetación (MODIS y Landsat):** se toman 9 puntos repartidos en una rejilla de 3×3 sobre toda la caja y se promedian. Esos puntos **no distinguen** si caen dentro o fuera de un cultivo.

**Qué efecto tiene la forma según la fuente:**

| Fuente | Tamaño del píxel (aprox.) | ¿Importa que el terreno no sea rectangular? |
|---|---|---|
| NASA POWER (clima) | decenas de km | No: un terreno pequeño cabe en un píxel |
| SMAP (humedad del suelo) | 9 km | Muy poco |
| MODIS (NDVI/EVI) | 250 m | **Sí**: la caja puede incluir bosque, caminos, agua o fincas vecinas |
| Landsat/HLS (NDVI/EVI) | 30 m | **Sí**, más que en MODIS |

**Qué significa en la práctica**

- Para comparar estrategias a nivel de **zona del Corredor Seco** (la escala del análisis), el rectángulo es una aproximación razonable.
- Para hablar de **una finca o un terreno concreto**, el promedio de vegetación puede estar diluido por todo lo que no es cultivo dentro de la caja. No tomes decisiones sobre un terreno específico con esos números.
- Para acercarte más a un terreno irregular: dibuja una caja pequeña que cubra solo la parte agrícola (el mínimo permitido es de unos 2 km por lado) y evita incluir lagos, ciudades o bosque denso.
- Por ahora no se filtra por uso de suelo ni se aceptan polígonos. Hacerlo es una mejora posible: dibujar la forma real del terreno y muestrear solo dentro de ella.

## 5. El panel "Datos de la NASA en este servidor"

Muestra una fila por fuente: **Datos hasta** (la fecha del último dato, con cuántos días de atraso lleva), **Última sincronización** y **Estado**.

| Estado | Significado |
|---|---|
| **Al día** | Los datos llegan hasta una fecha razonable para esa fuente |
| **Atrasada** | Hace más tiempo del esperado que no entran datos nuevos (la NASA publica con retraso, así que unos días de atraso son normales) |
| **Error en la última sincronización** | El último intento de descarga falló; los datos anteriores siguen disponibles |
| **Sin datos** | Aún no se ha descargado nada de esa fuente para la zona |

Debajo hay tres gráficos mensuales: lluvia (POWER), humedad de la zona de raíces (SMAP) y vigor de la vegetación, NDVI (MODIS). **Los huecos son meses sin dato**: no se rellenan ni se interpolan.

**Con qué frecuencia se actualiza.** Una vez al día, de madrugada (03:40, hora de Managua). La NASA publica con retraso (SMAP unos 3 a 5 días; MODIS más de tres semanas), por eso "Datos hasta" nunca llega a hoy.

## 6. Preguntas frecuentes

**¿Por qué no veo el mapa?** Si el mapa no carga, la página sigue funcionando sin él. Un filtro de red (por ejemplo, el de una universidad) puede bloquear los mosaicos del mapa o la conexión con el servidor. Prueba desde otra red.

**¿Por qué dice "Datos de respaldo"?** La página no pudo contactar al servidor. Los datos mostrados no están actualizados.

**¿Por qué mi zona sigue pendiente?** Alguien del equipo debe aprobarla. Mientras esté pendiente, no es visible para otras personas y no se descarga nada.

**¿Puedo cambiar o borrar una zona que envié?** No desde la página. Pide al equipo que la rechace y envía una nueva.

**¿Por qué el NDVI de mi zona no coincide con lo que veo en mi cultivo?** Ver la sección 4: la caja promedia todo lo que contiene, no solo el cultivo.

## 7. Para el equipo: aprobar zonas

1. Abre `https://rrodrovan.github.io/AFND/admin.html`.
2. Pega el token de administrador y pulsa **Ver pendientes**. El token no se guarda en el navegador: hay que pegarlo cada vez.
3. Para cada solicitud, usa **ver en el mapa** para comprobar que la caja cubre lo que se espera y pulsa **Aprobar** o **Rechazar**.
4. La descarga empieza en la siguiente sincronización diaria. Para adelantarla, en el servidor: `sudo systemctl start terrashift-sync.service --no-block`.

Cada zona aprobada consume tiempo de la cuenta de NASA Earthdata del equipo (las descargas pueden tardar horas), así que conviene aprobar solo lo que se vaya a usar. El token y las claves nunca deben compartirse por chat ni subirse al repositorio. Instalación y mantenimiento: [`deploy/README.md`](../deploy/README.md).
