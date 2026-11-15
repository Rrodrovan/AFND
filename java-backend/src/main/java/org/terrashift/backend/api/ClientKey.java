package org.terrashift.backend.api;

import jakarta.servlet.http.HttpServletRequest;

/**
 * Identifica al cliente para los límites de uso. Detrás de Nginx se usa la cabecera X-Real-IP (que Nginx
 * fija con $remote_addr); si no llega, se usa la dirección directa, que sería la de Nginx (límite global).
 */
final class ClientKey {

    private ClientKey() {
    }

    static String of(HttpServletRequest request) {
        String real = request.getHeader("X-Real-IP");
        String key = real != null && !real.isBlank() ? real.trim() : request.getRemoteAddr();
        return key == null ? "desconocido" : key.substring(0, Math.min(key.length(), 64));
    }
}
