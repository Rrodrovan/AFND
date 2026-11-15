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

  // Zonas aprobadas (para dibujarlas en el mapa). Si el servidor no responde, devuelve null.
  async function loadZones(config) {
    try {
      var zones = await getJson(config.apiBase.replace(/\/+$/, "") + "/api/v1/zones", config.timeoutMs);
      return Array.isArray(zones) ? zones : null;
    } catch (_) {
      return null;
    }
  }

  // Envía una solicitud de zona. Devuelve {ok:true, zone} o {ok:false, error} con un mensaje para mostrar.
  async function requestZone(config, payload) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, config.timeoutMs);
    try {
      var res = await root.fetch(config.apiBase.replace(/\/+$/, "") + "/api/v1/zones/requests", {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      var body = null;
      try { body = await res.json(); } catch (_) { /* respuesta sin cuerpo JSON */ }
      if (res.ok) return { ok: true, zone: body };
      var text = body && typeof body.error === "string" ? body.error : "El servidor no aceptó la solicitud (HTTP " + res.status + ").";
      return { ok: false, error: text };
    } catch (_) {
      return { ok: false, error: "No se pudo contactar con el servidor. Intenta de nuevo en unos minutos." };
    } finally {
      clearTimeout(timer);
    }
  }

  var api = { loadComparison: loadComparison, loadObservations: loadObservations, loadZones: loadZones, requestZone: requestZone };
  root.TerraShiftApi = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
