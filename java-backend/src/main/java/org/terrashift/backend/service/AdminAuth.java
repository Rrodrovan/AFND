package org.terrashift.backend.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

/**
 * Autenticación de administrador por token (cabecera X-Admin-Token). El token viene de la variable de
 * entorno TERRASHIFT_ADMIN_TOKEN; si no está definida, los endpoints de administración quedan apagados.
 * Tras 10 fallos por hora desde la misma clave se bloquean los intentos.
 */
@Component
public class AdminAuth {

    static final int MAX_FAILURES_PER_HOUR = 10;

    private final byte[] tokenHash;
    private final RequestLimiter failures;

    public AdminAuth(@Value("${terrashift.admin.token:}") String token, Clock clock) {
        this.tokenHash = token == null || token.isBlank() ? null : sha256(token);
        this.failures = new RequestLimiter(MAX_FAILURES_PER_HOUR, Duration.ofHours(1), clock);
    }

    public void require(String providedToken, String clientKey) {
        if (tokenHash == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "Recurso no disponible.");
        }
        if (failures.isBlocked(clientKey)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS, "Demasiados intentos. Espera una hora.");
        }
        byte[] provided = sha256(providedToken == null ? "" : providedToken);
        if (!MessageDigest.isEqual(tokenHash, provided)) {
            failures.hit(clientKey);
            throw new ApiException(HttpStatus.UNAUTHORIZED, "Token de administrador inválido.");
        }
    }

    private static byte[] sha256(String text) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
