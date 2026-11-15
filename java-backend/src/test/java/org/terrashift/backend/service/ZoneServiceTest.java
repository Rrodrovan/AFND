package org.terrashift.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.terrashift.backend.domain.ZoneRequest;
import org.terrashift.backend.domain.ZoneSummary;

class ZoneServiceTest {

    private final FakeZoneRepository repository = new FakeZoneRepository();
    private final TestClock clock = new TestClock();
    private final ZoneService service = new ZoneService(repository, clock);

    private static ZoneRequest valid(String name) {
        return new ZoneRequest(name, -86.70, 13.40, -86.50, 13.60);
    }

    private static HttpStatus statusOf(Runnable action) {
        return assertThrows(ApiException.class, action::run).status();
    }

    @Test
    void validRequestIsStoredAsPendingAndGetsAReadableCode() {
        ZoneSummary zone = service.request(valid("Somoto Cañón"), "1.1.1.1");

        assertEquals("pending", zone.status());
        assertTrue(zone.code().matches("somoto-canon-[0-9a-f]{4}"), zone.code());
        assertEquals(1, repository.countByStatus("pending"));
        assertEquals(0, service.approved().size());
    }

    @Test
    void rejectsMissingCoordinates() {
        assertEquals(HttpStatus.BAD_REQUEST,
                statusOf(() -> service.request(new ZoneRequest("Zona", null, 13.4, -86.5, 13.6), "ip")));
    }

    @Test
    void rejectsInvalidNames() {
        assertEquals(HttpStatus.BAD_REQUEST, statusOf(() -> service.request(valid("ab"), "ip")));
        assertEquals(HttpStatus.BAD_REQUEST, statusOf(() -> service.request(valid("<script>alert(1)</script>"), "ip")));
        assertEquals(HttpStatus.BAD_REQUEST, statusOf(() -> service.request(valid("x".repeat(61)), "ip")));
        assertEquals(HttpStatus.BAD_REQUEST, statusOf(() -> service.request(valid(null), "ip")));
    }

    @Test
    void rejectsInvertedBox() {
        assertEquals(HttpStatus.BAD_REQUEST,
                statusOf(() -> service.request(new ZoneRequest("Zona", -86.5, 13.4, -86.7, 13.6), "ip")));
    }

    @Test
    void rejectsZonesOutsideNicaragua() {
        assertEquals(HttpStatus.BAD_REQUEST,
                statusOf(() -> service.request(new ZoneRequest("Zona", -99.2, 19.3, -99.0, 19.5), "ip")));
    }

    @Test
    void rejectsTooSmallAndTooLargeBoxes() {
        assertEquals(HttpStatus.BAD_REQUEST,
                statusOf(() -> service.request(new ZoneRequest("Zona", -86.60, 13.50, -86.595, 13.505), "ip")));
        assertEquals(HttpStatus.BAD_REQUEST,
                statusOf(() -> service.request(new ZoneRequest("Zona", -87.5, 12.0, -86.0, 13.5), "ip")));
    }

    @Test
    void rejectsNonFiniteCoordinates() {
        assertEquals(HttpStatus.BAD_REQUEST,
                statusOf(() -> service.request(new ZoneRequest("Zona", Double.NaN, 13.4, -86.5, 13.6), "ip")));
    }

    @Test
    void limitsRequestsPerClientPerHour() {
        for (int i = 0; i < ZoneService.MAX_REQUESTS_PER_HOUR; i++) {
            service.request(valid("Zona " + i), "same-ip");
            // las pendientes también están limitadas; se aprueban para no llegar a ese tope
            repository.reviewPending(repository.zones.get(repository.zones.size() - 1).code(), "approved");
        }
        assertEquals(HttpStatus.TOO_MANY_REQUESTS, statusOf(() -> service.request(valid("Otra"), "same-ip")));

        // otro cliente no se ve afectado, y pasada la hora el primero vuelve a poder enviar
        service.request(valid("De otro"), "other-ip");
        clock.advance(Duration.ofMinutes(61));
        service.request(valid("Otra vez"), "same-ip");
    }

    @Test
    void failedValidationDoesNotConsumeTheClientQuota() {
        for (int i = 0; i < 10; i++) {
            statusOf(() -> service.request(valid("x"), "ip"));
        }
        service.request(valid("Zona buena"), "ip");
    }

    @Test
    void capsTheNumberOfPendingRequests() {
        for (int i = 0; i < ZoneService.MAX_PENDING; i++) {
            service.request(valid("Zona " + i), "ip-" + i);
        }
        assertEquals(HttpStatus.TOO_MANY_REQUESTS, statusOf(() -> service.request(valid("Una más"), "nueva-ip")));
    }

    @Test
    void approveMakesTheZonePublicAndIsOnlyPossibleOnce() {
        ZoneSummary zone = service.request(valid("Zona uno"), "ip");

        assertEquals("approved", service.approve(zone.code()).status());
        assertEquals(1, service.approved().size());
        assertEquals(HttpStatus.NOT_FOUND, statusOf(() -> service.approve(zone.code())));
        assertEquals(HttpStatus.NOT_FOUND, statusOf(() -> service.reject(zone.code())));
    }

    @Test
    void rejectedZonesNeverBecomePublic() {
        ZoneSummary zone = service.request(valid("Zona dos"), "ip");

        assertEquals("rejected", service.reject(zone.code()).status());
        assertEquals(0, service.approved().size());
        assertEquals(0, service.pending().size());
    }

    @Test
    void slugRemovesAccentsAndSymbols() {
        assertEquals("canon-de-somoto", ZoneService.slug("Cañón de Somoto!"));
        assertEquals("zona", ZoneService.slug("***"));
        assertTrue(ZoneService.slug("a".repeat(80)).length() <= 30);
    }
}
