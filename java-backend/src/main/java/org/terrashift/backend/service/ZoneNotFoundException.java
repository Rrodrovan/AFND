package org.terrashift.backend.service;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.NOT_FOUND)
public class ZoneNotFoundException extends RuntimeException {

    public ZoneNotFoundException(String zoneCode) {
        super("La zona '" + zoneCode + "' no existe. Ejecuta primero la ingesta del ETL.");
    }
}
