package org.terrashift.backend.api;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.terrashift.backend.domain.DataStatusResponse;
import org.terrashift.backend.domain.ObservationsResponse;
import org.terrashift.backend.service.ObservationService;

@RestController
@RequestMapping("/api/v1/zones/{zone}")
public class ObservationController {

    private final ObservationService service;

    public ObservationController(ObservationService service) {
        this.service = service;
    }

    /** Hasta qué fecha llegan los datos de cada fuente de la NASA y cómo fue la última sincronización. */
    @GetMapping("/data-status")
    public DataStatusResponse dataStatus(@PathVariable String zone) {
        return service.dataStatus(zone);
    }

    /** Series mensuales de lluvia, temperatura, humedad del suelo y NDVI (por defecto, los últimos 24 meses). */
    @GetMapping("/observations/monthly")
    public ObservationsResponse monthly(@PathVariable String zone, @RequestParam(required = false) Integer months) {
        return service.monthly(zone, months);
    }
}
