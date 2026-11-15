package org.terrashift.backend.service;

import org.springframework.stereotype.Service;
import org.terrashift.backend.domain.DataStatusResponse;
import org.terrashift.backend.domain.ObservationsResponse;
import org.terrashift.backend.repository.ObservationRepository;

@Service
public class ObservationService {

    static final int DEFAULT_MONTHS = 24;
    static final int MAX_MONTHS = 240;

    private final ObservationRepository repository;

    public ObservationService(ObservationRepository repository) {
        this.repository = repository;
    }

    public DataStatusResponse dataStatus(String zoneCode) {
        requireZone(zoneCode);
        return new DataStatusResponse(zoneCode, repository.findDataStatus(zoneCode));
    }

    public ObservationsResponse monthly(String zoneCode, Integer months) {
        requireZone(zoneCode);
        int window = months == null ? DEFAULT_MONTHS : Math.max(1, Math.min(months, MAX_MONTHS));
        return new ObservationsResponse(zoneCode, repository.findMonthly(zoneCode, window));
    }

    private void requireZone(String zoneCode) {
        if (!repository.zoneExists(zoneCode)) {
            throw new ZoneNotFoundException(zoneCode);
        }
    }
}
