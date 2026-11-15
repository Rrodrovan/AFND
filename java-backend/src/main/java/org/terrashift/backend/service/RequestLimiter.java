package org.terrashift.backend.service;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.Map;

/** Limita cuántas veces puede ocurrir algo por clave (por ejemplo, una IP) dentro de una ventana de tiempo. */
public class RequestLimiter {

    private static final int MAX_KEYS = 10_000;

    private final int limit;
    private final Duration window;
    private final Clock clock;
    private final Map<String, Deque<Instant>> hits = new HashMap<>();

    public RequestLimiter(int limit, Duration window, Clock clock) {
        this.limit = limit;
        this.window = window;
        this.clock = clock;
    }

    /** Cuántos eventos lleva la clave dentro de la ventana. */
    public synchronized int count(String key) {
        Deque<Instant> queue = hits.get(key);
        if (queue == null) {
            return 0;
        }
        Instant cutoff = clock.instant().minus(window);
        while (!queue.isEmpty() && !queue.peekFirst().isAfter(cutoff)) {
            queue.pollFirst();
        }
        if (queue.isEmpty()) {
            hits.remove(key);
            return 0;
        }
        return queue.size();
    }

    public synchronized void hit(String key) {
        if (hits.size() >= MAX_KEYS) {
            hits.clear(); // tope de memoria: ante un ataque con miles de claves se reinicia el conteo
        }
        hits.computeIfAbsent(key, k -> new ArrayDeque<>()).addLast(clock.instant());
    }

    public synchronized boolean isBlocked(String key) {
        return count(key) >= limit;
    }

    /** Registra el evento si aún hay cupo; devuelve false (sin registrar) si ya se alcanzó el límite. */
    public synchronized boolean tryHit(String key) {
        if (isBlocked(key)) {
            return false;
        }
        hit(key);
        return true;
    }
}
