package org.terrashift.backend.domain;

/** Zona de estudio con su caja (oeste, sur, este, norte en grados) y su estado: pending, approved o rejected. */
public record ZoneSummary(
        String code,
        String name,
        double minLon,
        double minLat,
        double maxLon,
        double maxLat,
        String status) {
}
