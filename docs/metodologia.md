# Metodología de análogos regionales

> **Estado:** este documento es el diseño del método. La investigación de análogos **no se realizó** durante el hackathon, por lo que los campos `[COMPLETAR]` siguen pendientes y el MVP no calcula resultados por estrategia. Lo que sí funciona hoy son las series observadas de la NASA para la zona piloto (ver README, «Estado actual»).

Este documento desarrolla la sección 2 del [README](../README.md). Está pensado para completarse
con los resultados de la investigación científica y agronómica del equipo.

## 1. Sitio piloto

| Campo | Valor |
|---|---|
| Zona(s) | `[COMPLETAR]` |
| Departamento / municipio | `[COMPLETAR]` |
| Precipitación anual aproximada | `[COMPLETAR]` |
| Duración de la época seca y de la canícula | `[COMPLETAR]` |
| Tipo de suelo y problemas de degradación | `[COMPLETAR]` |
| Cultivos del piloto | Maíz y frijol |

## 2. Criterios de selección de análogos

Ver tabla de criterios obligatorios y deseables en la sección 2.1 del README. Si el equipo ajusta
algún criterio, registrar aquí el cambio y la razón.

## 3. Regiones análogas seleccionadas

Una ficha por región. Toda afirmación debe tener su referencia en [`referencias.md`](referencias.md).

### A1 · `[COMPLETAR]`

- **País y ubicación:** `[COMPLETAR]`
- **Rasgo climático (por qué es comparable):** `[COMPLETAR]`
- **Rasgo edáfico (por qué es comparable):** `[COMPLETAR]`
- **Intervención documentada y estrategia asociada (E1/E2/E3):** `[COMPLETAR]`
- **Resultado medido (con unidad y periodo):** `[COMPLETAR]`
- **Diferencias relevantes con el piloto:** `[COMPLETAR]`

## 4. Factores de transferencia

`efecto_piloto = efecto_analogo × f_clima × f_suelo × f_cultivo`

| Factor | Cómo se calcula | Fuente de los datos | Valor | Rango |
|---|---|---|---|---|
| `f_clima` | `[COMPLETAR]` | NASA POWER / SMAP | `[ ]` | `[ ]` |
| `f_suelo` | `[COMPLETAR]` | `[COMPLETAR]` | `[ ]` | `[ ]` |
| `f_cultivo` | `[COMPLETAR]` | `[COMPLETAR]` | `[ ]` | `[ ]` |

## 5. Escenarios climáticos

| Escenario | Definición operativa | Datos usados |
|---|---|---|
| Normal | `[COMPLETAR]` | `[COMPLETAR]` |
| Seco | `[COMPLETAR]` | `[COMPLETAR]` |
| Canícula prolongada | `[COMPLETAR]` | `[COMPLETAR]` |

## 6. Validación

- [ ] Consistencia de las tendencias simuladas con NDVI/EVI observado
- [ ] Consistencia con la humedad de suelo de SMAP
- [ ] Análisis de sensibilidad del ranking de estrategias a los factores de transferencia
- [ ] Documentar los casos en que el modelo no es consistente con lo observado
