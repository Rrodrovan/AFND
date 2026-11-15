package org.terrashift.backend.repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.terrashift.backend.domain.DataSourceStatus;
import org.terrashift.backend.domain.MonthlyObservation;

/** Lee las vistas v_data_freshness y v_observed_monthly (las llena el ETL de Python). */
@Repository
public class ObservationRepository {

    private final JdbcTemplate jdbc;

    public ObservationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public boolean zoneExists(String zoneCode) {
        Integer count = jdbc.queryForObject(
                "SELECT count(*) FROM zone WHERE code = ?", Integer.class, zoneCode);
        return count != null && count > 0;
    }

    public List<DataSourceStatus> findDataStatus(String zoneCode) {
        return jdbc.query(
                """
                SELECT source, label, first_date, last_date, n_rows, last_sync_ok_at,
                       last_run_status, last_run_at
                FROM v_data_freshness
                WHERE zone_code = ?
                ORDER BY CASE source WHEN 'power' THEN 1 WHEN 'smap' THEN 2
                                     WHEN 'modis' THEN 3 ELSE 4 END
                """,
                (rs, i) -> new DataSourceStatus(
                        rs.getString("source"),
                        rs.getString("label"),
                        rs.getObject("first_date", LocalDate.class),
                        rs.getObject("last_date", LocalDate.class),
                        rs.getLong("n_rows"),
                        rs.getObject("last_sync_ok_at", OffsetDateTime.class),
                        rs.getString("last_run_status"),
                        rs.getObject("last_run_at", OffsetDateTime.class)),
                zoneCode);
    }

    public List<MonthlyObservation> findMonthly(String zoneCode, int months) {
        return jdbc.query(
                """
                SELECT month, precip_mm_total, precip_days, t2m_mean_c,
                       surface_m3m3_mean, rootzone_m3m3_mean, ndvi_modis_mean, ndvi_landsat_mean
                FROM v_observed_monthly
                WHERE zone_code = ?
                  AND month > (date_trunc('month', current_date) - make_interval(months => ?))::date
                ORDER BY month
                """,
                (rs, i) -> new MonthlyObservation(
                        rs.getObject("month", LocalDate.class),
                        nullableDouble(rs, "precip_mm_total"),
                        nullableLong(rs, "precip_days"),
                        nullableDouble(rs, "t2m_mean_c"),
                        nullableDouble(rs, "surface_m3m3_mean"),
                        nullableDouble(rs, "rootzone_m3m3_mean"),
                        nullableDouble(rs, "ndvi_modis_mean"),
                        nullableDouble(rs, "ndvi_landsat_mean")),
                zoneCode,
                months);
    }

    private static Double nullableDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    private static Long nullableLong(ResultSet rs, String column) throws SQLException {
        long value = rs.getLong(column);
        return rs.wasNull() ? null : value;
    }
}
