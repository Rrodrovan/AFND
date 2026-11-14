package org.terrashift.backend.domain;

import java.util.List;

/** Respuesta de la comparación de las tres estrategias para una zona. */
public record ComparisonResponse(String zone, List<StrategyComparison> strategies, String note) {
}
