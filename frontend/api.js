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

  var api = { loadComparison: loadComparison };
  root.TerraShiftApi = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
