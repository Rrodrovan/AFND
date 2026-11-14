package org.terrashift.backend.domain;

/** Estrategia de rotación de cultivos (E1, E2, E3). */
public record Strategy(int id, String code, String name, String focus) {
}
