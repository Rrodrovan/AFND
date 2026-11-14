package org.terrashift.backend.domain;

import java.util.List;

/** Una estrategia junto con sus indicadores calculados para una zona. */
public record StrategyComparison(Strategy strategy, List<Indicator> indicators) {
}
