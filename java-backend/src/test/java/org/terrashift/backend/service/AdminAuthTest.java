package org.terrashift.backend.service;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

class AdminAuthTest {

    private final TestClock clock = new TestClock();

    private HttpStatus statusOf(AdminAuth auth, String token, String client) {
        return assertThrows(ApiException.class, () -> auth.require(token, client)).status();
    }

    @Test
    void adminEndpointsAreOffWhenNoTokenIsConfigured() {
        AdminAuth auth = new AdminAuth("", clock);

        assertEquals(HttpStatus.NOT_FOUND, statusOf(auth, "cualquiera", "ip"));
        assertEquals(HttpStatus.NOT_FOUND, statusOf(auth, "", "ip"));
    }

    @Test
    void acceptsOnlyTheExactToken() {
        AdminAuth auth = new AdminAuth("secreto-largo", clock);

        assertDoesNotThrow(() -> auth.require("secreto-largo", "ip"));
        assertEquals(HttpStatus.UNAUTHORIZED, statusOf(auth, "secreto-largo ", "ip"));
        assertEquals(HttpStatus.UNAUTHORIZED, statusOf(auth, null, "ip"));
    }

    @Test
    void blocksAClientAfterTooManyFailuresEvenWithTheRightToken() {
        AdminAuth auth = new AdminAuth("secreto-largo", clock);
        for (int i = 0; i < AdminAuth.MAX_FAILURES_PER_HOUR; i++) {
            statusOf(auth, "mal", "atacante");
        }

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, statusOf(auth, "secreto-largo", "atacante"));
        assertDoesNotThrow(() -> auth.require("secreto-largo", "equipo"));

        clock.advance(Duration.ofMinutes(61));
        assertDoesNotThrow(() -> auth.require("secreto-largo", "atacante"));
    }
}
