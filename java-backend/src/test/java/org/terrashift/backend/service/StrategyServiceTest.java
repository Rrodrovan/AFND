package org.terrashift.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.terrashift.backend.domain.ComparisonResponse;
import org.terrashift.backend.domain.Indicator;
import org.terrashift.backend.domain.Strategy;
import org.terrashift.backend.repository.StrategyRepository;

class StrategyServiceTest {

    private final StrategyRepository repository = mock(StrategyRepository.class);
    private final StrategyService service = new StrategyService(repository);

    @Test
    void compareFailsWhenZoneDoesNotExist() {
        when(repository.zoneExists("piloto")).thenReturn(false);

        assertThrows(ZoneNotFoundException.class, () -> service.compare("piloto"));
    }

    @Test
    void compareReturnsOneEntryPerStrategy() {
        when(repository.zoneExists("piloto")).thenReturn(true);
        when(repository.findAll()).thenReturn(List.of(
                new Strategy(1, "E1", "Línea base tradicional", "Práctica actual"),
                new Strategy(2, "E2", "Conservación hídrica", "Retención de agua"),
                new Strategy(3, "E3", "Regeneración de suelos", "Materia orgánica")));
        when(repository.findIndicators("piloto", 1)).thenReturn(List.of(
                new Indicator("Maíz", "seco", "rendimiento_t_ha", 1.2, 0.9, 1.5, "t/ha")));
        when(repository.findIndicators("piloto", 2)).thenReturn(List.of());
        when(repository.findIndicators("piloto", 3)).thenReturn(List.of());

        ComparisonResponse response = service.compare("piloto");

        assertEquals("piloto", response.zone());
        assertEquals(3, response.strategies().size());
        assertEquals(1, response.strategies().get(0).indicators().size());
        assertEquals(StrategyService.PENDING_NOTE, response.note());
    }
}
