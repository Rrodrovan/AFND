package org.terrashift.backend.domain;

import java.util.List;

public record ObservationsResponse(String zone, List<MonthlyObservation> months) {
}
