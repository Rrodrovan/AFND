package org.terrashift.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import org.junit.jupiter.api.Test;

class RequestLimiterTest {

    private final TestClock clock = new TestClock();
    private final RequestLimiter limiter = new RequestLimiter(2, Duration.ofHours(1), clock);

    @Test
    void allowsUpToTheLimitThenBlocks() {
        assertTrue(limiter.tryHit("a"));
        assertTrue(limiter.tryHit("a"));
        assertFalse(limiter.tryHit("a"));
        assertEquals(2, limiter.count("a"));
    }

    @Test
    void keysAreIndependent() {
        limiter.hit("a");
        limiter.hit("a");
        assertTrue(limiter.isBlocked("a"));
        assertFalse(limiter.isBlocked("b"));
    }

    @Test
    void eventsExpireAfterTheWindow() {
        limiter.hit("a");
        limiter.hit("a");
        clock.advance(Duration.ofMinutes(59));
        assertTrue(limiter.isBlocked("a"));
        clock.advance(Duration.ofMinutes(2));
        assertEquals(0, limiter.count("a"));
        assertTrue(limiter.tryHit("a"));
    }
}
