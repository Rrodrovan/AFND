package org.terrashift.backend.domain;

import java.time.LocalDate;

/** Resumen mensual de lo observado. Una variable sin dato ese mes es null (nunca se rellena). */
public record MonthlyObservation(
        LocalDate month,
        Double precipMmTotal,
        Long precipDays,
        Double t2mMeanC,
        Double surfaceM3m3Mean,
        Double rootzoneM3m3Mean,
        Double ndviModisMean,
        Double ndviLandsatMean) {
}
