# Método: balance hídrico con datos de la NASA

Este documento desarrolla la sección 2 del [README](../README.md). La comparación de E1, E2 y E3 se calcula con las series observadas de la NASA para cada zona, mediante un balance de agua diario del suelo con métodos de la FAO. El código está en `python-etl/src/metrics/` (`waterbalance.py` y `strategies.py`).

## 1. Sitio piloto

| Campo | Valor |
|---|---|
| Zona | `piloto` (rectángulo en el Corredor Seco; límites en la tabla `zone`) |
| Cultivos | Maíz (siembra de primera, mayo) y frijol (siembra de postrera, septiembre) |
| Clima | Serie diaria de NASA POWER cargada en `climate_daily` |
| Vegetación | NDVI/EVI de MODIS y Landsat/HLS |
| Humedad del suelo | SMAP (carga acotada a lo más reciente) |

## 2. Datos de entrada

| Variable | Fuente | Uso |
|---|---|---|
| Precipitación diaria (mm) | NASA POWER | Entrada de agua al suelo y escenarios |
| Temperatura máxima y mínima (°C) | NASA POWER | ET0 con Hargreaves-Samani |
| Latitud de la zona | Centro del rectángulo | Radiación extraterrestre (FAO-56) |
| NDVI/EVI | MODIS, Landsat/HLS | Contraste con el estrés calculado |
| Humedad del suelo | SMAP | Contraste con el balance de agua |

## 3. Cálculo

1. **ET0 diaria** con Hargreaves-Samani, usando la radiación extraterrestre `Ra` de FAO-56.
2. **Demanda del cultivo:** `Kc = Kcb + Ke`, con curvas por etapa (inicial, desarrollo, media y final) de FAO-56. `Kcb` es la transpiración y `Ke` la evaporación del suelo.
3. **Depósito de agua del suelo:** capacidad `TAW`; se parte con 30 días previos a la siembra para que el suelo llegue con una humedad realista. La lluvia (menos escorrentía) lo llena; evaporación y transpiración lo vacían.
4. **Estrés:** cuando el agua disponible baja de la fracción `p`, la transpiración se reduce con `Ks`.
5. **Rendimiento relativo:** `1 − Ky · (1 − Ta/Tc)` (FAO-33), con `Ta` transpiración real y `Tc` potencial del ciclo.
6. Los ciclos con más de 5 % de días sin dato se descartan. Un cultivo necesita al menos 5 años completos para calcularse.

## 4. Parámetros de manejo (supuestos del modelo)

| Parámetro | E1 | E2 | E3 |
|---|---|---|---|
| Escorrentía | 0,15 | 0,08 | 0,12 |
| Factor de evaporación del suelo | 1,00 | 0,85 | 1,00 |
| Multiplicador de `TAW` | 1,00 | 1,00 | 1,10 |

Son supuestos explícitos y ajustables en `strategies.py`. Para un análisis de sensibilidad, cambie un valor y vuelva a ejecutar `python -m src.cli metrics --zone piloto`.

## 5. Escenarios climáticos

| Escenario | Definición operativa | Datos usados |
|---|---|---|
| Normal | Años del tercio central por lluvia del ciclo | Lluvia diaria de NASA POWER |
| Seco | Los 3 años con menos lluvia en el ciclo | Lluvia diaria de NASA POWER |
| Canícula prolongada | Los 3 años con menos lluvia en julio–agosto | Lluvia diaria de NASA POWER |

Se reporta la media y el rango `[mín – máx]` de los años de cada escenario. Los años son los mismos para las tres estrategias.

## 6. Contraste con la señal satelital

- [ ] Comparar el NDVI de los años secos y normales con el estrés calculado.
- [ ] Comparar la humedad de SMAP con el balance de agua cuando termine su carga.
- [ ] Cambiar los parámetros de manejo y comprobar si el orden de las estrategias se mantiene.
