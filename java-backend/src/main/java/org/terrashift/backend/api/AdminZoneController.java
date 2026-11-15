package org.terrashift.backend.api;

import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.terrashift.backend.domain.ZoneSummary;
import org.terrashift.backend.service.AdminAuth;
import org.terrashift.backend.service.ZoneService;

/** Revisión de solicitudes de zona. Todas las rutas exigen la cabecera X-Admin-Token. */
@RestController
@RequestMapping("/api/v1/admin/zones")
public class AdminZoneController {

    private final ZoneService service;
    private final AdminAuth auth;

    public AdminZoneController(ZoneService service, AdminAuth auth) {
        this.service = service;
        this.auth = auth;
    }

    @GetMapping("/pending")
    public List<ZoneSummary> pending(
            @RequestHeader(value = "X-Admin-Token", required = false) String token, HttpServletRequest http) {
        auth.require(token, ClientKey.of(http));
        return service.pending();
    }

    @PostMapping("/{code}/approve")
    public ZoneSummary approve(
            @PathVariable String code,
            @RequestHeader(value = "X-Admin-Token", required = false) String token,
            HttpServletRequest http) {
        auth.require(token, ClientKey.of(http));
        return service.approve(code);
    }

    @PostMapping("/{code}/reject")
    public ZoneSummary reject(
            @PathVariable String code,
            @RequestHeader(value = "X-Admin-Token", required = false) String token,
            HttpServletRequest http) {
        auth.require(token, ClientKey.of(http));
        return service.reject(code);
    }
}
