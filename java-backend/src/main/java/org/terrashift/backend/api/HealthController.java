package org.terrashift.backend.api;

import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class HealthController {

    private final JdbcTemplate jdbc;

    public HealthController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        String database;
        try {
            jdbc.queryForObject("SELECT 1", Integer.class);
            database = "up";
        } catch (Exception e) {
            database = "down";
        }
        return Map.of("status", "up", "database", database);
    }
}
