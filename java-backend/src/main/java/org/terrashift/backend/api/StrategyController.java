package org.terrashift.backend.api;

import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.terrashift.backend.domain.ComparisonResponse;
import org.terrashift.backend.domain.Strategy;
import org.terrashift.backend.service.StrategyService;

@RestController
@RequestMapping("/api/v1/strategies")
public class StrategyController {

    private final StrategyService service;

    public StrategyController(StrategyService service) {
        this.service = service;
    }

    @GetMapping
    public List<Strategy> list() {
        return service.listStrategies();
    }

    @GetMapping("/compare")
    public ComparisonResponse compare(@RequestParam String zone) {
        return service.compare(zone);
    }
}
