// Gráficos SVG mínimos (sin librerías). Todo texto se inserta con textContent y los números se validan.
(function (root) {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  var W = 300, H = 120, PAD = { l: 38, r: 8, t: 8, b: 20 };
  var MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  function svg(tag, attrs, text) {
    var node = root.document.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, String(attrs[k])); });
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function isNum(v) { return typeof v === "number" && isFinite(v); }

  // "2026-03-01" -> "mar 26" (sin pasar por Date para no sufrir cambios de zona horaria)
  function monthLabel(iso) {
    var m = /^(\d{4})-(\d{2})/.exec(String(iso));
    if (!m) return "";
    return MONTHS[Number(m[2]) - 1] + " " + m[1].slice(2);
  }

  function niceMax(max) {
    if (max <= 0) return 1;
    var pow = Math.pow(10, Math.floor(Math.log10(max)));
    var f = max / pow;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow;
  }

  function fmt(v, decimals) {
    return Number(v).toLocaleString("es", { maximumFractionDigits: decimals });
  }

  /**
   * points: [{label, value|null}]. kind: "bar" | "line".
   * opts: {title, unit, decimals, min, max}. Devuelve un <figure> con el SVG y su descripción.
   */
  function chart(points, kind, opts) {
    var doc = root.document;
    var figure = doc.createElement("figure");
    figure.className = "chart";
    var caption = doc.createElement("figcaption");
    caption.textContent = opts.title;
    figure.appendChild(caption);

    var values = points.map(function (p) { return p.value; }).filter(isNum);
    if (values.length === 0) {
      var empty = doc.createElement("p");
      empty.className = "empty";
      empty.textContent = "Sin datos todavía.";
      figure.appendChild(empty);
      return figure;
    }

    var decimals = opts.decimals === undefined ? 1 : opts.decimals;
    var lo = opts.min !== undefined ? opts.min : Math.min.apply(null, values);
    var hi = opts.max !== undefined ? opts.max : Math.max.apply(null, values);
    if (kind === "bar") { lo = 0; hi = niceMax(hi); }
    if (hi === lo) hi = lo + 1;

    var node = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "class": "chart__svg" });
    var last = points.filter(function (p) { return isNum(p.value); }).pop();
    node.setAttribute("aria-label", opts.title + ": " + values.length + " meses con datos; último valor " +
      fmt(last.value, decimals) + " " + opts.unit + " en " + last.label);
    node.appendChild(svg("title", {}, opts.title));

    var plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b;
    function x(i) { return PAD.l + (points.length === 1 ? plotW / 2 : (plotW * i) / (points.length - 1)); }
    function y(v) { return PAD.t + plotH - ((v - lo) / (hi - lo)) * plotH; }

    // ejes
    node.appendChild(svg("line", { x1: PAD.l, y1: PAD.t, x2: PAD.l, y2: PAD.t + plotH, "class": "chart__axis" }));
    node.appendChild(svg("line", { x1: PAD.l, y1: PAD.t + plotH, x2: W - PAD.r, y2: PAD.t + plotH, "class": "chart__axis" }));
    node.appendChild(svg("text", { x: PAD.l - 4, y: PAD.t + 4, "text-anchor": "end", "class": "chart__tick" }, fmt(hi, decimals)));
    node.appendChild(svg("text", { x: PAD.l - 4, y: PAD.t + plotH, "text-anchor": "end", "class": "chart__tick" }, fmt(lo, decimals)));
    node.appendChild(svg("text", { x: PAD.l, y: H - 5, "text-anchor": "start", "class": "chart__tick" }, points[0].label));
    node.appendChild(svg("text", { x: W - PAD.r, y: H - 5, "text-anchor": "end", "class": "chart__tick" }, points[points.length - 1].label));

    if (kind === "bar") {
      var barW = Math.max(2, (plotW / points.length) * 0.7);
      points.forEach(function (p, i) {
        if (!isNum(p.value)) return;
        var top = y(p.value);
        var bar = svg("rect", { x: x(i) - barW / 2, y: top, width: barW, height: Math.max(0, PAD.t + plotH - top), "class": "chart__bar" });
        bar.appendChild(svg("title", {}, p.label + ": " + fmt(p.value, decimals) + " " + opts.unit));
        node.appendChild(bar);
      });
    } else {
      // la línea se corta donde faltan datos: no se interpola nada
      var segment = [];
      function flush() {
        if (segment.length > 1) {
          node.appendChild(svg("polyline", { points: segment.join(" "), "class": "chart__line" }));
        }
        segment = [];
      }
      points.forEach(function (p, i) {
        if (!isNum(p.value)) { flush(); return; }
        segment.push(x(i).toFixed(1) + "," + y(p.value).toFixed(1));
        var dot = svg("circle", { cx: x(i).toFixed(1), cy: y(p.value).toFixed(1), r: 2.5, "class": "chart__dot" });
        dot.appendChild(svg("title", {}, p.label + ": " + fmt(p.value, decimals) + " " + opts.unit));
        node.appendChild(dot);
      });
      flush();
    }

    figure.appendChild(node);
    return figure;
  }

  function seriesFrom(months, field) {
    return months.map(function (m) {
      return { label: monthLabel(m.month), value: isNum(m[field]) ? m[field] : null };
    });
  }

  var api = { chart: chart, seriesFrom: seriesFrom, monthLabel: monthLabel };
  root.TerraShiftCharts = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
