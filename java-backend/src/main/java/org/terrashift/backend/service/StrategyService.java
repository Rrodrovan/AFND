package org.terrashift.backend.service;

import java.util.List;
import org.springframework.stereotype.Service;
import org.terrashift.backend.domain.ComparisonResponse;
import org.terrashift.backend.domain.Strategy;
import org.terrashift.backend.domain.StrategyComparison;
import org.terrashift.backend.repository.StrategyRepository;

@Service
public class StrategyService {

    static final String PENDING_NOTE =
            "Puntaje global y nivel de confianza pendientes (Fase 3 del roadmap). "
                    + "Se muestran los indicadores disponibles en strategy_result.";

    private final StrategyRepository repository;

    public StrategyService(StrategyRepository repository) {
        this.repository = repository;
    }

    public List<Strategy> listStrategies() {
        return repository.findAll();
    }

    public ComparisonResponse compare(String zoneCode) {
        if (!repository.zoneExists(zoneCode)) {
            throw new ZoneNotFoundException(zoneCode);
        }
        List<StrategyComparison> comparisons = repository.findAll().stream()
                .map(s -> new StrategyComparison(s, repository.findIndicators(zoneCode, s.id())))
                .toList();
        return new ComparisonResponse(zoneCode, comparisons, PENDING_NOTE);
    }
}
