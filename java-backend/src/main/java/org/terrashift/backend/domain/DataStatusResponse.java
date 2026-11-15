package org.terrashift.backend.domain;

import java.util.List;

public record DataStatusResponse(String zone, List<DataSourceStatus> sources) {
}
