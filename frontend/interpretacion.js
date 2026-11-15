// Interpretación para el agricultor: evalúa las reglas de interpretacion.json sobre los resultados de
// E1/E2/E3 y los datos mensuales de la NASA. No hay IA ni servidor: son reglas fijas y editables.
// Cada texto sale de una regla cuya condición se cumple, y cada regla dice su criterio para poder verificarla.
(function (root) {
  "use strict";

  var STRATEGIES = ["E1", "E2", "E3"];
  var CROPS = ["maiz", "frijol"];
  var SCENARIOS = ["normal", "seco", "canicula"];
  var TIE = 0.5;        // dos estrategias a menos de 0,5 puntos se consideran parejas
  var NO_GAP = 1;       // por debajo de 1 punto no se declara ganadora a ninguna
  var DRY_MONTH_MM = 50;
  var CANICULA_RATIO = 0.8;

  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function plain(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }

  // ---- hechos: números y etiquetas calculados a partir de los datos ----------------------------

  function indicatorKey(name) {
    var n = plain(name);
    if (n.indexOf("rendimiento") === 0) return "rend";
    if (n.indexOf("indice de estres") === 0) return "estres";
    if (n.indexOf("deficit") === 0) return "deficit";
    if (n.indexOf("lluvia efectiva") === 0) return "lluvia";
    return null;
  }

  function resultFacts(strategies, facts) {
    (strategies || []).forEach(function (item) {
      var code = item.strategy && item.strategy.code;
      (item.indicators || []).forEach(function (ind) {
        var key = indicatorKey(ind.indicator);
        if (!key || !isNum(ind.value)) return;
        var base = plain(ind.crop) + "." + ind.scenario + "." + code + ".";
        facts[base + key] = ind.value;
        if (key === "rend") {
          if (isNum(ind.min)) facts[base + "rend_min"] = ind.min;
          if (isNum(ind.max)) facts[base + "rend_max"] = ind.max;
        }
      });
    });
  }

  function derive(facts) {
    var counts = { E1: 0, E2: 0, E3: 0 };
    var combos = 0;
    var gapMax = 0;
    CROPS.forEach(function (c) {
      var drops = {};
      SCENARIOS.forEach(function (s) {
        var base = c + "." + s + ".";
        var r = {};
        STRATEGIES.forEach(function (e) { r[e] = facts[base + e + ".rend"]; });
        if (!STRATEGIES.every(function (e) { return isNum(r[e]); })) return;
        combos++;
        var gapE2 = r.E2 - r.E1;
        var gapE3 = r.E3 - r.E1;
        var gap = Math.max(gapE2, gapE3, 0);
        facts[base + "gap_E2"] = gapE2;
        facts[base + "gap_E3"] = gapE3;
        facts[base + "gap_max"] = gap;
        gapMax = Math.max(gapMax, gap);
        var best;
        var top = Math.max(r.E1, r.E2, r.E3);
        if (gap < NO_GAP) {
          best = "ninguna";
        } else if (Math.abs(r.E2 - r.E3) < TIE && Math.min(r.E2, r.E3) > r.E1) {
          best = "E2_E3";
          counts.E2++; counts.E3++;
        } else {
          best = STRATEGIES.filter(function (e) { return r[e] === top; })[0];
          counts[best]++;
        }
        facts[base + "mejor"] = best;
        var d = function (e) { return facts[base + e + ".deficit"]; };
        if (isNum(d("E1")) && isNum(d("E2"))) facts[base + "def_red_E2"] = d("E1") - d("E2");
        if (isNum(d("E1")) && isNum(d("E3"))) facts[base + "def_red_E3"] = d("E1") - d("E3");
      });
      // caída respecto al año normal y variación entre años
      STRATEGIES.forEach(function (e) {
        var n = facts[c + ".normal." + e + ".rend"];
        ["seco", "canicula"].forEach(function (s) {
          var v = facts[c + "." + s + "." + e + ".rend"];
          if (isNum(n) && isNum(v)) facts[c + "." + e + ".caida_" + s] = n - v;
        });
        var lo = facts[c + ".normal." + e + ".rend_min"];
        var hi = facts[c + ".normal." + e + ".rend_max"];
        if (isNum(lo) && isNum(hi)) facts[c + "." + e + ".amplitud"] = hi - lo;
        if (isNum(facts[c + "." + e + ".caida_seco"])) drops[e] = facts[c + "." + e + ".caida_seco"];
      });
      var codes = Object.keys(drops);
      if (codes.length === STRATEGIES.length) {
        var least = codes.sort(function (a, b) { return drops[a] - drops[b]; })[0];
        facts[c + ".menos_caida"] = least;
        facts[c + ".menos_caida_valor"] = drops[least];
        facts[c + ".menos_caida_mejora"] = drops.E1 - drops[least];
      }
    });

    if (combos === 0) return;
    facts["global.n_total"] = combos;
    facts["global.gap_max"] = gapMax;
    var max = Math.max(counts.E1, counts.E2, counts.E3);
    var leaders = STRATEGIES.filter(function (e) { return counts[e] === max; });
    if (max === 0) {
      facts["global.mejor"] = "ninguna";
      facts["global.n_mejor"] = 0;
    } else if (leaders.length === 1) {
      facts["global.mejor"] = leaders[0];
      facts["global.n_mejor"] = max;
    } else if (leaders.length === 2 && leaders[0] === "E2" && leaders[1] === "E3") {
      facts["global.mejor"] = "E2_E3";
      facts["global.n_mejor"] = max;
    } else {
      facts["global.mejor"] = "empate";
      facts["global.n_mejor"] = max;
    }
  }

  function monthFacts(months, facts) {
    months = months || [];
    var rain = months.filter(function (m) { return isNum(m.precipMmTotal); }).slice(-12);
    if (rain.length >= 6) {
      facts["zona.meses_lluvia"] = rain.length;
      facts["zona.lluvia12"] = rain.reduce(function (s, m) { return s + m.precipMmTotal; }, 0);
      facts["zona.meses_secos"] = rain.filter(function (m) { return m.precipMmTotal < DRY_MONTH_MM; }).length;
    }
    var idx = {};
    months.forEach(function (m) { idx[m.month.slice(0, 7)] = m; });
    var years = {};
    months.forEach(function (m) { years[m.month.slice(0, 4)] = true; });
    var evaluated = 0;
    var canicula = 0;
    Object.keys(years).forEach(function (y) {
      var get = function (mm) { var m = idx[y + "-" + mm]; return m && isNum(m.precipMmTotal) ? m.precipMmTotal : null; };
      var v = [get("06"), get("07"), get("08"), get("09")];
      if (v.some(function (x) { return x === null; })) return;
      evaluated++;
      if (Math.min(v[1], v[2]) < CANICULA_RATIO * (v[0] + v[3]) / 2) canicula++;
    });
    if (evaluated > 0) {
      facts["zona.anios_evaluados"] = evaluated;
      facts["zona.canicula_anios"] = canicula;
    }
    if (months.length) facts["zona.smap"] = months.some(function (m) { return isNum(m.rootzoneM3m3Mean) || isNum(m.surfaceM3m3Mean); }) ? 1 : 0;

    var key = months.some(function (m) { return isNum(m.ndviModisMean); }) ? "ndviModisMean" : "ndviLandsatMean";
    var valid = months.filter(function (m) { return isNum(m[key]); });
    if (valid.length) {
      var last = valid[valid.length - 1];
      var prev = idx[(Number(last.month.slice(0, 4)) - 1) + last.month.slice(4, 7)];
      if (prev && isNum(prev[key]) && prev[key] > 0) facts["zona.ndvi_cambio"] = (last[key] / prev[key] - 1) * 100;
    }
  }

  function buildFacts(strategies, months) {
    var facts = {};
    resultFacts(strategies, facts);
    derive(facts);
    monthFacts(months, facts);
    return facts;
  }

  // ---- evaluación de condiciones -------------------------------------------------------------------

  function evalCond(cond, facts) {
    if (cond.todas) return cond.todas.every(function (c) { return evalCond(c, facts); });
    if (cond.alguna) return cond.alguna.some(function (c) { return evalCond(c, facts); });
    if (cond.no) return !evalCond(cond.no, facts);
    var v = facts[cond.hecho];
    if (cond.op === "existe") return v !== undefined && v !== null;
    if (v === undefined || v === null) return false;
    if (cond.op === "entre") return isNum(v) && v >= cond.rango[0] && v <= cond.rango[1];
    var ref = cond.valor_hecho !== undefined ? facts[cond.valor_hecho] : cond.valor;
    if (ref === undefined || ref === null) return false;
    switch (cond.op) {
      case ">": return v > ref;
      case ">=": return v >= ref;
      case "<": return v < ref;
      case "<=": return v <= ref;
      case "==": return v === ref;
      case "!=": return v !== ref;
      default: return false;
    }
  }

  // ---- textos --------------------------------------------------------------------------------------

  function band(scale, value) {
    for (var i = 0; i < scale.length; i++) {
      if (scale[i].hasta === null || value < scale[i].hasta) return scale[i].texto;
    }
    return "";
  }

  // Devuelve null si falta algún dato del texto: la regla simplemente no se muestra.
  function renderText(template, facts, rules) {
    var missing = false;
    var out = template.replace(/\{([\w.]+)(?::(\d))?(?:\|(\w+))?\}/g, function (_, name, dec, kind) {
      var v = facts[name];
      if (v === undefined || v === null) { missing = true; return ""; }
      if (kind) {
        if (typeof v === "number") {
          var scale = rules.escalas && rules.escalas[kind];
          if (!scale) { missing = true; return ""; }
          return band(scale, v);
        }
        var names = rules.nombres || {};
        return names[v] !== undefined ? names[v] : String(v);
      }
      if (typeof v === "number") {
        var d = dec === undefined ? 0 : Number(dec);
        return v.toFixed(d).replace(".", ",");
      }
      return String(v);
    });
    return missing ? null : out;
  }

  function expand(rule) {
    if (!rule.para) return [rule];
    return rule.para.map(function (p) {
      var json = JSON.stringify(rule).replace(/\$cultivo/g, p.cultivo).replace(/\$c/g, p.c);
      var copy = JSON.parse(json);
      delete copy.para;
      copy.id = rule.id + "-" + p.c;
      copy.cultivo = p.cultivo;
      return copy;
    });
  }

  // Resultado: [{ id, titulo, items: [{ id, texto, criterio }] }] solo con secciones que tengan algo que decir.
  function build(rules, strategies, months) {
    var facts = buildFacts(strategies, months);
    var sections = [];
    ((rules && rules.secciones) || []).forEach(function (sec) {
      var items = [];
      (sec.reglas || []).forEach(function (rule) {
        expand(rule).forEach(function (r) {
          if (!evalCond(r.cuando, facts)) return;
          var text = renderText(r.texto, facts, rules);
          if (text) items.push({ id: r.id, texto: text, criterio: r.criterio || "" });
        });
      });
      if (items.length) sections.push({ id: sec.id, titulo: sec.titulo, items: items });
    });
    return sections;
  }

  var cache = null;
  function load(url) {
    if (!cache) {
      cache = root.fetch(url).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).catch(function (e) { cache = null; throw e; });
    }
    return cache;
  }

  root.TerraShiftInterpretation = { build: build, buildFacts: buildFacts, evalCond: evalCond, renderText: renderText, load: load };
  if (typeof module !== "undefined" && module.exports) module.exports = root.TerraShiftInterpretation;
})(typeof window !== "undefined" ? window : this);
