package org.terrashift.backend.api;

import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.terrashift.backend.domain.ZoneRequest;
import org.terrashift.backend.domain.ZoneSummary;
import org.terrashift.backend.service.ZoneService;

@RestController
@RequestMapping("/api/v1/zones")
public class ZoneController {

    private final ZoneService service;

    public ZoneController(ZoneService service) {
        this.service = service;
    }

    /** Zonas aprobadas (las únicas visibles al público). */
    @GetMapping
    public List<ZoneSummary> approved() {
        return service.approved();
    }

    /** Propone una zona nueva: queda pendiente de aprobación. */
    @PostMapping("/requests")
    @ResponseStatus(HttpStatus.CREATED)
    public ZoneSummary request(@RequestBody ZoneRequest body, HttpServletRequest http) {
        return service.request(body, ClientKey.of(http));
    }
}
