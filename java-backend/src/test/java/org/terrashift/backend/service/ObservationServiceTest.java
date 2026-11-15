package org.terrashift.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.LocalDate;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.terrashift.backend.domain.DataSourceStatus;
import org.terrashift.backend.domain.DataStatusResponse;
import org.terrashift.backend.domain.ObservationsResponse;
import org.terrashift.backend.repository.ObservationRepository;

class ObservationServiceTest {

    private final ObservationRepository repository = mock(ObservationRepository.class);
    private final ObservationService service = new ObservationService(repository);

    @Test
    void dataStatusFailsWhenZoneDoesNotExist() {
        when(repository.zoneExists("nada")).thenReturn(false);

        assertThrows(ZoneNotFoundException.class, () -> service.dataStatus("nada"));
    }

    @Test
    void dataStatusReturnsTheSourcesOfTheZone() {
        when(repository.zoneExists("piloto")).thenReturn(true);
        DataSourceStatus smap = new DataSourceStatus(
                "smap", "NASA SMAP", LocalDate.of(2015, 4, 1), LocalDate.of(2026, 11, 9), 4200L,
                null, "ok", null);
        when(repository.findDataStatus("piloto")).thenReturn(List.of(smap));

        DataStatusResponse response = service.dataStatus("piloto");

        assertEquals("piloto", response.zone());
        assertEquals(List.of(smap), response.sources());
    }

    @Test
    void monthlyUsesTwentyFourMonthsByDefault() {
        when(repository.zoneExists("piloto")).thenReturn(true);
        when(repository.findMonthly("piloto", 24)).thenReturn(List.of());

        ObservationsResponse response = service.monthly("piloto", null);

        assertEquals(List.of(), response.months());
        verify(repository).findMonthly("piloto", 24);
    }

    @Test
    void monthlyClampsTheRequestedWindow() {
        when(repository.zoneExists("piloto")).thenReturn(true);

        service.monthly("piloto", 100000);
        service.monthly("piloto", -3);

        verify(repository).findMonthly("piloto", 240);
        verify(repository).findMonthly("piloto", 1);
    }
}
