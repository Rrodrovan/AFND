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
      render(await window.TerraShiftApi.loadComparison(cfg, zone));
    } catch (err) {
      resultsEl.replaceChildren();
      noteEl.hidden = true;
      setStatus("error", "No se pudieron cargar los datos. Intenta de nuevo en unos minutos.");
    } finally {
      buttonEl.disabled = false;
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var zone = zoneInput.value.trim();
    if (zone) run(zone);
  });

  document.getElementById("repo-link").href = cfg.repoUrl;
  document.getElementById("docs-link").href = cfg.apiBase.replace(/\/+$/, "") + "/api/swagger-ui.html";

  zoneInput.value = cfg.defaultZone;
  run(cfg.defaultZone);
})();
