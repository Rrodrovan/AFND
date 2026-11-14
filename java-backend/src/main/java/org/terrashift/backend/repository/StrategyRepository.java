package org.terrashift.backend.repository;

import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.terrashift.backend.domain.Indicator;
import org.terrashift.backend.domain.Strategy;

@Repository
public class StrategyRepository {

    private final JdbcTemplate jdbc;

    public StrategyRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Strategy> findAll() {
        return jdbc.query(
                "SELECT id, code, name, focus FROM strategy ORDER BY code",
                (rs, i) -> new Strategy(
                        rs.getInt("id"), rs.getString("code"), rs.getString("name"), rs.getString("focus")));
    }

    public boolean zoneExists(String zoneCode) {
        Integer count = jdbc.queryForObject(
                "SELECT count(*) FROM zone WHERE code = ?", Integer.class, zoneCode);
        return count != null && count > 0;
    }

    public List<Indicator> findIndicators(String zoneCode, int strategyId) {
        return jdbc.query(
                """
                SELECT c.name AS crop, r.scenario, r.indicator,
                       r.value_mid, r.value_min, r.value_max, r.unit
                FROM strategy_result r
                JOIN zone z ON z.id = r.zone_id
                JOIN crop c ON c.id = r.crop_id
                WHERE z.code = ? AND r.strategy_id = ?
                ORDER BY c.name, r.scenario, r.indicator
                """,
                (rs, i) -> new Indicator(
                        rs.getString("crop"),
                        rs.getString("scenario"),
                        rs.getString("indicator"),
                        (Double) rs.getObject("value_mid"),
                        (Double) rs.getObject("value_min"),
                        (Double) rs.getObject("value_max"),
                        rs.getString("unit")),
                zoneCode,
                strategyId);
    }
}
