package org.terrashift.backend.repository;

import java.util.List;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.terrashift.backend.domain.ZoneSummary;

@Repository
public class ZoneRepository {

    private static final String COLUMNS = "code, name, min_lon, min_lat, max_lon, max_lat, status";

    private final JdbcTemplate jdbc;

    public ZoneRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<ZoneSummary> findByStatus(String status) {
        return jdbc.query(
                "SELECT " + COLUMNS + " FROM zone WHERE status = ? AND min_lon IS NOT NULL ORDER BY requested_at, code",
                (rs, i) -> new ZoneSummary(
                        rs.getString("code"),
                        rs.getString("name"),
                        rs.getDouble("min_lon"),
                        rs.getDouble("min_lat"),
                        rs.getDouble("max_lon"),
                        rs.getDouble("max_lat"),
                        rs.getString("status")),
                status);
    }

    public Optional<ZoneSummary> findByCode(String code) {
        return jdbc.query(
                "SELECT " + COLUMNS + " FROM zone WHERE code = ? AND min_lon IS NOT NULL",
                (rs, i) -> new ZoneSummary(
                        rs.getString("code"),
                        rs.getString("name"),
                        rs.getDouble("min_lon"),
                        rs.getDouble("min_lat"),
                        rs.getDouble("max_lon"),
                        rs.getDouble("max_lat"),
                        rs.getString("status")),
                code).stream().findFirst();
    }

    public int countByStatus(String status) {
        Integer count = jdbc.queryForObject("SELECT count(*) FROM zone WHERE status = ?", Integer.class, status);
        return count == null ? 0 : count;
    }

    public boolean codeExists(String code) {
        Integer count = jdbc.queryForObject("SELECT count(*) FROM zone WHERE code = ?", Integer.class, code);
        return count != null && count > 0;
    }

    /** Guarda una solicitud nueva en estado pending (la descarga de datos no empieza hasta aprobarla). */
    public void insertPending(String code, String name, double minLon, double minLat, double maxLon, double maxLat) {
        jdbc.update(
                """
                INSERT INTO zone (code, name, geom, status, min_lon, min_lat, max_lon, max_lat)
                VALUES (?, ?, ST_Multi(ST_MakeEnvelope(?, ?, ?, ?, 4326)), 'pending', ?, ?, ?, ?)
                """,
                code, name, minLon, minLat, maxLon, maxLat, minLon, minLat, maxLon, maxLat);
    }

    /** Cambia el estado solo si la zona sigue pendiente. Devuelve false si no existía o ya estaba revisada. */
    public boolean reviewPending(String code, String newStatus) {
        return jdbc.update(
                "UPDATE zone SET status = ?, reviewed_at = now() WHERE code = ? AND status = 'pending'",
                newStatus, code) > 0;
    }
}
