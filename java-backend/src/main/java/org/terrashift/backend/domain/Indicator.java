package org.terrashift.backend.domain;

/** Resultado de un indicador para una estrategia, con su rango de incertidumbre. */
public record Indicator(
        String crop,
        String scenario,
        String indicator,
        Double value,
        Double min,
        Double max,
        String unit) {
}
