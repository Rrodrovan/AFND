package org.terrashift.backend.domain;

/** Solicitud de una zona nueva dibujada en el mapa. Los campos pueden venir vacíos; el servicio los valida. */
public record ZoneRequest(String name, Double minLon, Double minLat, Double maxLon, Double maxLat) {
}
