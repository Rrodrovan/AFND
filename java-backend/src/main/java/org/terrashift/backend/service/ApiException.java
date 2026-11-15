package org.terrashift.backend.service;

import org.springframework.http.HttpStatus;

/** Error de negocio con el código HTTP que debe devolverse y un mensaje seguro de mostrar al usuario. */
public class ApiException extends RuntimeException {

    private final HttpStatus status;

    public ApiException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus status() {
        return status;
    }
}
