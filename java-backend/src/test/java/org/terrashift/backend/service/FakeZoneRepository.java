package org.terrashift.backend.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.terrashift.backend.domain.ZoneSummary;
import org.terrashift.backend.repository.ZoneRepository;

/** Repositorio en memoria para probar el servicio sin base de datos. */
class FakeZoneRepository extends ZoneRepository {

    final List<ZoneSummary> zones = new ArrayList<>();

    FakeZoneRepository() {
        super(null);
    }

    @Override
    public List<ZoneSummary> findByStatus(String status) {
        return zones.stream().filter(z -> z.status().equals(status)).toList();
    }

    @Override
    public Optional<ZoneSummary> findByCode(String code) {
        return zones.stream().filter(z -> z.code().equals(code)).findFirst();
    }

    @Override
    public int countByStatus(String status) {
        return findByStatus(status).size();
    }

    @Override
    public boolean codeExists(String code) {
        return findByCode(code).isPresent();
    }

    @Override
    public void insertPending(String code, String name, double minLon, double minLat, double maxLon, double maxLat) {
        zones.add(new ZoneSummary(code, name, minLon, minLat, maxLon, maxLat, "pending"));
    }

    @Override
    public boolean reviewPending(String code, String newStatus) {
        for (int i = 0; i < zones.size(); i++) {
            ZoneSummary z = zones.get(i);
            if (z.code().equals(code) && z.status().equals("pending")) {
                zones.set(i, new ZoneSummary(z.code(), z.name(), z.minLon(), z.minLat(), z.maxLon(), z.maxLat(), newStatus));
                return true;
            }
        }
        return false;
    }
}
