package org.terrashift.backend.service;

import java.security.SecureRandom;
import java.text.Normalizer;
import java.time.Clock;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.terrashift.backend.domain.ZoneRequest;
import org.terrashift.backend.domain.ZoneSummary;
import org.terrashift.backend.repository.ZoneRepository;

/**
 * Zonas propuestas desde el mapa. Cualquiera puede proponer, pero la zona queda "pending" y no se descarga
 * nada de la NASA hasta que un administrador la aprueba. Límites: tamaño de la caja, ubicación en Nicaragua,
 * cantidad de solicitudes pendientes y solicitudes por hora desde cada origen.
 */
@Service
public class ZoneService {

    static final double MIN_SIDE_DEG = 0.02;
    static final double MAX_SIDE_DEG = 0.5;
    static final double LON_MIN = -88.0, LON_MAX = -82.5, LAT_MIN = 10.5, LAT_MAX = 15.5;
    static final int MAX_PENDING = 20;
    static final int MAX_REQUESTS_PER_HOUR = 5;
    private static final Pattern NAME = Pattern.compile("^[\\p{L}\\p{N} .,'()-]{3,60}$");
    private static final Pattern NOT_ALNUM = Pattern.compile("[^a-z0-9]+");

    private final ZoneRepository repository;
    private final RequestLimiter limiter;
    private final SecureRandom random = new SecureRandom();

    public ZoneService(ZoneRepository repository, Clock clock) {
        this.repository = repository;
        this.limiter = new RequestLimiter(MAX_REQUESTS_PER_HOUR, Duration.ofHours(1), clock);
    }

    public List<ZoneSummary> approved() {
        return repository.findByStatus("approved");
    }

    public List<ZoneSummary> pending() {
        return repository.findByStatus("pending");
    }

    public ZoneSummary request(ZoneRequest request, String clientKey) {
        String name = validate(request);
        if (limiter.isBlocked(clientKey)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "Has enviado demasiadas solicitudes. Intenta de nuevo en una hora.");
        }
        if (repository.countByStatus("pending") >= MAX_PENDING) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "Hay muchas solicitudes pendientes de revisión. Intenta más tarde.");
        }
        String code = uniqueCode(name);
        repository.insertPending(code, name, request.minLon(), request.minLat(), request.maxLon(), request.maxLat());
        limiter.hit(clientKey);
        return new ZoneSummary(code, name, request.minLon(), request.minLat(), request.maxLon(), request.maxLat(), "pending");
    }

    public ZoneSummary approve(String code) {
        return review(code, "approved");
    }

    public ZoneSummary reject(String code) {
        return review(code, "rejected");
    }

    private ZoneSummary review(String code, String status) {
        if (!repository.reviewPending(code, status)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "No hay una solicitud pendiente con ese código.");
        }
        return repository.findByCode(code)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "La zona no existe."));
    }

    /** Valida la solicitud y devuelve el nombre ya limpio. Los mensajes se muestran tal cual al usuario. */
    String validate(ZoneRequest r) {
        if (r == null || r.minLon() == null || r.minLat() == null || r.maxLon() == null || r.maxLat() == null) {
            throw bad("Faltan las coordenadas de la zona.");
        }
        double[] values = {r.minLon(), r.minLat(), r.maxLon(), r.maxLat()};
        for (double v : values) {
            if (Double.isNaN(v) || Double.isInfinite(v)) {
                throw bad("Las coordenadas no son válidas.");
            }
        }
        String name = r.name() == null ? "" : r.name().trim().replaceAll("\\s+", " ");
        if (!NAME.matcher(name).matches()) {
            throw bad("El nombre debe tener entre 3 y 60 caracteres (letras, números y signos simples).");
        }
        if (r.minLon() >= r.maxLon() || r.minLat() >= r.maxLat()) {
            throw bad("La caja está al revés: el oeste debe ser menor que el este y el sur menor que el norte.");
        }
        if (r.minLon() < LON_MIN || r.maxLon() > LON_MAX || r.minLat() < LAT_MIN || r.maxLat() > LAT_MAX) {
            throw bad("La zona debe estar dentro de Nicaragua.");
        }
        double width = r.maxLon() - r.minLon();
        double height = r.maxLat() - r.minLat();
        if (width < MIN_SIDE_DEG || height < MIN_SIDE_DEG) {
            throw bad("La zona es demasiado pequeña (mínimo 0,02° por lado, unos 2 km).");
        }
        if (width > MAX_SIDE_DEG || height > MAX_SIDE_DEG) {
            throw bad("La zona es demasiado grande (máximo 0,5° por lado, unos 55 km).");
        }
        return name;
    }

    private String uniqueCode(String name) {
        String base = slug(name);
        for (int attempt = 0; attempt < 10; attempt++) {
            String code = base + "-" + String.format("%04x", random.nextInt(0x10000));
            if (!repository.codeExists(code)) {
                return code;
            }
        }
        throw new ApiException(HttpStatus.CONFLICT, "No se pudo generar un código para la zona. Intenta de nuevo.");
    }

    static String slug(String name) {
        String plain = Normalizer.normalize(name, Normalizer.Form.NFD).replaceAll("\\p{M}+", "");
        String slug = NOT_ALNUM.matcher(plain.toLowerCase(Locale.ROOT)).replaceAll("-");
        slug = slug.replaceAll("^-+|-+$", "");
        if (slug.length() > 30) {
            slug = slug.substring(0, 30).replaceAll("-+$", "");
        }
        return slug.isEmpty() ? "zona" : slug;
    }

    private static ApiException bad(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, message);
    }
}
