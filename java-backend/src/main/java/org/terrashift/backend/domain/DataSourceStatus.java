package org.terrashift.backend.domain;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/**
 * Estado de una fuente de datos de la NASA en una zona: hasta cuándo hay datos y cómo fue la última
 * sincronización. El texto del error no se publica (queda en ingest_run y en el registro del servicio).
 */
public record DataSourceStatus(
        String source,
        String label,
        LocalDate firstDate,
        LocalDate lastDate,
        long rows,
        OffsetDateTime lastSyncOkAt,
        String lastRunStatus,
        OffsetDateTime lastRunAt) {
}
