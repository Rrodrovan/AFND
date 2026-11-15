// Lectura en lenguaje sencillo de los datos observados de una zona.
// Son reglas fijas y transparentes sobre los valores mensuales que ya entrega la API: no es un pronóstico
// ni un modelo agronómico. Cada frase dice el criterio que usó para que se pueda verificar.
(function (root) {
  "use strict";

  var DRY_MONTH_MM = 50;       // mes seco: menos de 50 mm de lluvia
  var CANICULA_RATIO = 0.8;    // descenso de jul-ago frente al promedio de jun y sep
  var MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function monthName(iso) { return MONTHS[Number(iso.slice(5, 7)) - 1]; }
  function fmt(n, d) { return n.toFixed(d).replace(".", ","); }

  function byYearMonth(months) {
    var map = {};
    months.forEach(function (m) { map[m.month.slice(0, 7)] = m; });
    return map;
  }

  function rainfall(months) {
    var withRain = months.filter(function (m) { return isNum(m.precipMmTotal); });
    var last = withRain.slice(-12);
    if (last.length < 6) return null;
    var total = last.reduce(function (s, m) { return s + m.precipMmTotal; }, 0);
    var dry = last.filter(function (m) { return m.precipMmTotal < DRY_MONTH_MM; }).map(function (m) { return monthName(m.month); });
    var text = "Lluvia: en " + last.length + " meses con datos cayeron unos " + Math.round(total) + " mm.";
    text += dry.length
      ? " Meses secos (menos de " + DRY_MONTH_MM + " mm): " + dry.join(", ") + "."
      : " Ningún mes bajó de " + DRY_MONTH_MM + " mm.";
    return text;
  }

  function canicula(months) {
    var idx = byYearMonth(months);
    var notes = [];
    var years = {};
    months.forEach(function (m) { years[m.month.slice(0, 4)] = true; });
    Object.keys(years).sort().forEach(function (y) {
      var get = function (mm) { var m = idx[y + "-" + mm]; return m && isNum(m.precipMmTotal) ? m.precipMmTotal : null; };
      var jun = get("06"), jul = get("07"), aug = get("08"), sep = get("09");
      if ([jun, jul, aug, sep].some(function (v) { return v === null; })) return;
      var trough = Math.min(jul, aug);
      var reference = (jun + sep) / 2;
      if (trough < CANICULA_RATIO * reference) {
        notes.push(y + ": julio-agosto bajó a " + Math.round(trough) + " mm frente a un promedio de " + Math.round(reference) + " mm en junio y septiembre (compatible con canícula).");
      } else {
        notes.push(y + ": no se nota un descenso claro en julio-agosto.");
      }
    });
    if (!notes.length) return null;
    return "Canícula (criterio: julio-agosto por debajo del " + Math.round(CANICULA_RATIO * 100) + " % del promedio de junio y septiembre). " + notes.join(" ");
  }

  function vegetation(months) {
    var key = months.some(function (m) { return isNum(m.ndviModisMean); }) ? "ndviModisMean" : "ndviLandsatMean";
    var label = key === "ndviModisMean" ? "MODIS" : "Landsat";
    var valid = months.filter(function (m) { return isNum(m[key]); });
    if (valid.length < 3) return null;
    var last = valid[valid.length - 1];
    var idx = byYearMonth(valid);
    var y = String(Number(last.month.slice(0, 4)) - 1) + last.month.slice(4, 7);
    var before = idx[y];
    var peak = valid.slice(-12).reduce(function (a, b) { return b[key] > a[key] ? b : a; });
    var text = "Vegetación (NDVI " + label + "): último valor " + fmt(last[key], 2) + " en " + monthName(last.month) + ".";
    if (before) {
      var diff = last[key] - before[key];
      text += Math.abs(diff) < 0.03
        ? " Es parecido al mismo mes del año anterior (" + fmt(before[key], 2) + ")."
        : " Es " + (diff > 0 ? "mayor" : "menor") + " que el mismo mes del año anterior (" + fmt(before[key], 2) + ").";
    }
    text += " El punto más alto de los últimos 12 meses fue " + monthName(peak.month) + " (" + fmt(peak[key], 2) + ").";
    return text;
  }

  function soil(months) {
    var valid = months.filter(function (m) { return isNum(m.rootzoneM3m3Mean); });
    if (!valid.length) return "Humedad del suelo (SMAP): todavía no hay datos cargados, por eso no se interpreta.";
    var last = valid[valid.length - 1];
    var values = valid.map(function (m) { return m.rootzoneM3m3Mean; });
    var min = Math.min.apply(null, values), max = Math.max.apply(null, values);
    return "Humedad del suelo en la zona de raíces (SMAP): último valor " + fmt(last.rootzoneM3m3Mean, 2) + " m³/m³ en " + monthName(last.month) +
      "; en el periodo cargado varió entre " + fmt(min, 2) + " y " + fmt(max, 2) + ".";
  }

  // Devuelve una lista de frases (puede estar vacía si no hay datos suficientes).
  function read(months) {
    if (!Array.isArray(months) || months.length === 0) return [];
    return [rainfall(months), canicula(months), vegetation(months), soil(months)].filter(Boolean);
  }

  var api = { read: read };
  root.TerraShiftReading = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
