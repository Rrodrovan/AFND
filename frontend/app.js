// Interfaz de TerraShift. Todo el texto que viene de la API se inserta con textContent (nunca innerHTML).
(function () {
  "use strict";

  var cfg = window.TERRASHIFT_CONFIG;
  var SCENARIOS = { normal: "Año normal", seco: "Año seco", canicula: "Canícula prolongada" };

  var form = document.getElementById("zone-form");
  var zoneInput = document.getElementById("zone");
  var statusEl = document.getElementById("status");
  var noteEl = document.getElementById("note");
  var resultsEl = document.getElementById("results");
  var buttonEl = form.querySelector("button");

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function fmt(value) {
    if (value === null || value === undefined) return "—";
    return Number(value).toLocaleString("es", { maximumFractionDigits: 2 });
  }

  function fmtValue(ind) {
    var main = fmt(ind.value);
    if (ind.min !== null && ind.min !== undefined && ind.max !== null && ind.max !== undefined) {
      main += " [" + fmt(ind.min) + " – " + fmt(ind.max) + "]";
    }
    return ind.unit ? main + " " + ind.unit : main;
  }

  function setStatus(kind, text) {
    statusEl.className = "status status--" + kind;
    statusEl.textContent = text;
  }

  // Días de atraso a partir de los cuales una fuente se marca "Atrasada" (latencia de la NASA + margen).
  var LATE_AFTER_DAYS = { power: 12, smap: 12, modis: 45, landsat: 25 };
  var DAY_MS = 24 * 3600 * 1000;

  // "2026-11-09" -> fecha local sin cambios de zona horaria
  function parseIsoDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
  }

  function daysSince(iso) {
    var d = parseIsoDate(iso);
    if (!d) return null;
    var now = new Date();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((today - d) / DAY_MS);
  }

  function fmtDate(iso) {
    var d = parseIsoDate(iso);
    return d ? d.toLocaleDateString("es", { day: "numeric", month: "short", year: "numeric" }) : "—";
  }

  function fmtDateTime(iso) {
    var d = iso ? new Date(iso) : null;
    if (!d || isNaN(d.getTime())) return "—";
    return d.toLocaleString("es", { dateStyle: "medium", timeStyle: "short" });
  }

  function badge(kind, text) {
    return el("span", "badge badge--" + kind, text);
  }

  function sourceState(src) {
    if (!src.lastDate) return badge("none", "Sin datos");
    if (src.lastRunStatus === "error") return badge("error", "Error en la última sincronización");
    var behind = daysSince(src.lastDate);
    var limit = LATE_AFTER_DAYS[src.source] || 30;
    return behind !== null && behind > limit ? badge("late", "Atrasada") : badge("ok", "Al día");
  }

  function renderNasaPanel(obs) {
    var panel = document.getElementById("nasa-panel");
    if (!obs || !obs.status || !obs.status.sources || obs.status.sources.length === 0) {
      panel.hidden = true;
      return;
    }
    var table = document.getElementById("nasa-sources");
    table.replaceChildren();
    var head = table.createTHead().insertRow();
    ["Fuente", "Datos hasta", "Última sincronización", "Estado"].forEach(function (h) {
      var th = document.createElement("th");
      th.scope = "col";
      th.textContent = h;
      head.appendChild(th);
    });
    var body = table.createTBody();
    obs.status.sources.forEach(function (src) {
      var row = body.insertRow();
      row.insertCell().textContent = src.label;
      var behind = src.lastDate ? daysSince(src.lastDate) : null;
      row.insertCell().textContent = src.lastDate
        ? fmtDate(src.lastDate) + (behind !== null && behind >= 0 ? " (hace " + behind + " d)" : "")
        : "—";
      row.insertCell().textContent = fmtDateTime(src.lastSyncOkAt);
      row.insertCell().appendChild(sourceState(src));
    });

    var charts = document.getElementById("nasa-charts");
    charts.replaceChildren();
    var C = window.TerraShiftCharts;
    var months = (obs.monthly && obs.monthly.months) || [];
    charts.appendChild(C.chart(C.seriesFrom(months, "precipMmTotal"), "bar",
      { title: "Lluvia mensual (NASA POWER)", unit: "mm", decimals: 0 }));
    charts.appendChild(C.chart(C.seriesFrom(months, "rootzoneM3m3Mean"), "line",
      { title: "Humedad en la zona de raíces (SMAP)", unit: "m³/m³", decimals: 2 }));
    charts.appendChild(C.chart(C.seriesFrom(months, "ndviModisMean"), "line",
      { title: "Vigor de la vegetación, NDVI (MODIS)", unit: "", decimals: 2, min: 0, max: 1 }));
    var lines = window.TerraShiftReading ? window.TerraShiftReading.read(months) : [];
    var readingEl = document.getElementById("nasa-reading");
    var list = document.getElementById("nasa-reading-list");
    list.replaceChildren();
    lines.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    readingEl.hidden = lines.length === 0;
    panel.hidden = false;
  }

  function renderIndicators(indicators) {
    if (!indicators || indicators.length === 0) {
      return el("p", "empty", "Sin resultados calculados todavía para esta estrategia.");
    }
    var table = el("table", "indicators");
    var head = table.createTHead().insertRow();
    ["Cultivo", "Escenario", "Indicador", "Valor [mín – máx]"].forEach(function (h) {
      var th = document.createElement("th");
      th.scope = "col";
      th.textContent = h;
      head.appendChild(th);
    });
    var body = table.createTBody();
    indicators.forEach(function (ind) {
      var row = body.insertRow();
      [ind.crop, SCENARIOS[ind.scenario] || ind.scenario, ind.indicator, fmtValue(ind)].forEach(function (text) {
        row.insertCell().textContent = text;
      });
    });
    return table;
  }

  function render(result) {
    var data = result.data;
    resultsEl.replaceChildren();

    if (result.source === "live") {
      setStatus("live", "Datos en vivo desde el servidor");
    } else {
      setStatus("backup", "Datos de respaldo: no se pudo contactar al servidor");
    }

    noteEl.textContent = data.note || "";
    noteEl.hidden = !data.note;

    (data.strategies || []).forEach(function (item) {
      var s = item.strategy;
      var card = el("article", "card");
      card.appendChild(el("span", "card__code", s.code));
      card.appendChild(el("h2", "card__title", s.name));
      card.appendChild(el("p", "card__focus", s.focus));
      card.appendChild(renderIndicators(item.indicators));
      resultsEl.appendChild(card);
    });
  }

  async function run(zone) {
    buttonEl.disabled = true;
    setStatus("loading", "Conectando con el servidor…");
    try {
      var result = await window.TerraShiftApi.loadComparison(cfg, zone);
      render(result);
      // Los datos de la NASA solo se piden si el servidor respondió; con la copia de respaldo no hay panel.
      renderNasaPanel(result.source === "live" ? await window.TerraShiftApi.loadObservations(cfg, zone, 24) : null);
    } catch (err) {
      document.getElementById("nasa-panel").hidden = true;
      resultsEl.replaceChildren();
      noteEl.hidden = true;
      setStatus("error", "No se pudieron cargar los datos. Intenta de nuevo en unos minutos.");
    } finally {
      buttonEl.disabled = false;
    }
  }

  // Menú de zonas: solo las aprobadas. Si el servidor no responde, queda la zona por defecto.
  function setZone(code) {
    var found = false;
    for (var i = 0; i < zoneInput.options.length; i++) {
      if (zoneInput.options[i].value === code) found = true;
    }
    if (!found) {
      var extra = document.createElement("option");
      extra.value = code;
      extra.textContent = code;
      zoneInput.appendChild(extra);
    }
    zoneInput.value = code;
  }

  // Con el servidor disponible el menú empieza vacío ("Elige una zona…"): el mapa no dibuja nada hasta elegir.
  function fillZoneMenu(zones) {
    zoneInput.textContent = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Elige una zona…";
    zoneInput.appendChild(placeholder);
    (zones || []).forEach(function (z) {
      var option = document.createElement("option");
      option.value = z.code;
      option.textContent = z.name || z.code;
      zoneInput.appendChild(option);
    });
    zoneInput.value = "";
  }

  // El mapa muestra solo la zona elegida en el menú.
  var allZones = null;
  function syncMap() {
    if (!picker || !allZones) return;
    var chosen = allZones.filter(function (z) { return zoneInput.value !== "" && z.code === zoneInput.value; });
    picker.showZones(chosen, chosen.length > 0);
  }

  zoneInput.addEventListener("change", function () {
    if (zoneInput.value) run(zoneInput.value);
    else setStatus("loading", "Elige una zona en el menú para ver sus estrategias.");
    syncMap();
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var zone = zoneInput.value.trim();
    if (zone) run(zone);
  });

  // Mapa de zonas: si Leaflet no cargó (p. ej. sin red), la página sigue funcionando sin él.
  var picker = window.TerraShiftZonePicker && window.TerraShiftZonePicker.init(cfg, {
    onSelectZone: function () {},
  });
  window.TerraShiftApi.loadZones(cfg).then(function (zones) {
    allZones = zones;
    if (zones && zones.length) {
      fillZoneMenu(zones);
      resultsEl.replaceChildren();
      setStatus("loading", "Elige una zona en el menú para ver sus estrategias.");
      syncMap();
    } else {
      // Sin servidor: se muestra la zona por defecto con la copia de respaldo.
      setZone(cfg.defaultZone);
      run(cfg.defaultZone);
    }
  });

  document.getElementById("repo-link").href = cfg.repoUrl;
  document.getElementById("docs-link").href = cfg.apiBase.replace(/\/+$/, "") + "/api/swagger-ui.html";
})();
