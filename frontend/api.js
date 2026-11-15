// Acceso a la API de TerraShift con respaldo local.
// Orden: 1) API en vivo  2) lista de estrategias en vivo (zona sin datos)  3) copia de respaldo.
(function (root) {
  "use strict";

  function httpError(status) {
    var err = new Error("HTTP " + status);
    err.status = status;
    return err;
  }

  async function getJson(url, timeoutMs) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, timeoutMs);
    try {
      var res = await root.fetch(url, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      if (!res.ok) throw httpError(res.status);
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function loadComparison(config, zone) {
    var base = config.apiBase.replace(/\/+$/, "");

    try {
      var live = await getJson(
        base + "/api/v1/strategies/compare?zone=" + encodeURIComponent(zone),
        config.timeoutMs
      );
      return { source: "live", data: live };
    } catch (err) {
      // 404 = el servidor responde, pero esa zona aún no tiene datos cargados.
      if (err.status === 404) {
        try {
          var list = await getJson(base + "/api/v1/strategies", config.timeoutMs);
          return {
            source: "live",
            data: {
              zone: zone,
              strategies: list.map(function (s) { return { strategy: s, indicators: [] }; }),
              note: 'La zona "' + zone + '" aún no tiene datos cargados en el servidor.',
            },
          };
        } catch (_) {
          // Si tampoco responde la lista, se usa la copia de respaldo.
        }
      }
    }

    var snapshot = await getJson(config.snapshotUrl, config.timeoutMs);
    return { source: "backup", data: snapshot };
  }

  // Estado de las fuentes de la NASA y series mensuales. Si el servidor no responde o aún no
  // tiene estos datos (404), devuelve null y la página simplemente oculta el panel.
  async function loadObservations(config, zone, months) {
    var base = config.apiBase.replace(/\/+$/, "");
    var z = encodeURIComponent(zone);
    try {
      var results = await Promise.all([
        getJson(base + "/api/v1/zones/" + z + "/data-status", config.timeoutMs),
        getJson(base + "/api/v1/zones/" + z + "/observations/monthly?months=" + (months || 24), config.timeoutMs),
      ]);
      return { status: results[0], monthly: results[1] };
    } catch (_) {
      return null;
    }
  }

  var api = { loadComparison: loadComparison, loadObservations: loadObservations };
  root.TerraShiftApi = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
