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
        var topAlt = Math.max(r.E2, r.E3);
        if (gap < NO_GAP && r.E1 - topAlt >= NO_GAP) {
          best = "E1";
          counts.E1++;
        } else if (gap < NO_GAP) {
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

  var MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

  function mean(a) { return a.reduce(function (s, v) { return s + v; }, 0) / a.length; }

  // Compara el promedio de los 3 últimos valores con el de los anteriores (en %). Necesita 6 valores o más.
  function recentVsEarlier(values) {
    if (values.length < 6) return null;
    var earlier = mean(values.slice(0, -3));
    if (!(earlier > 0)) return null;
    return (mean(values.slice(-3)) / earlier - 1) * 100;
  }

  // Quita el mes en curso: su promedio con pocos días no es comparable con los meses completos.
  function completeMonths(months, today) {
    var now = today || new Date();
    var cutoff = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
    return (months || []).filter(function (m) { return m.month.slice(0, 7) < cutoff; });
  }

  function groupByYear(months, field) {
    var years = {};
    months.forEach(function (m) {
      if (!isNum(m[field])) return;
      var y = m.month.slice(0, 4);
      (years[y] = years[y] || {})[Number(m.month.slice(5, 7))] = m[field];
    });
    return years;
  }

  function monthFacts(months, facts) {
    months = months || [];
    var rainBy = groupByYear(months, "precipMmTotal");
    var tempBy = groupByYear(months, "t2mMeanC");
    var key = months.some(function (m) { return isNum(m.ndviModisMean); }) ? "ndviModisMean" : "ndviLandsatMean";
    var ndviBy = groupByYear(months, key);
    var count = function (o) { return Object.keys(o).length; };
    var yearsOf = function (by, min) {
      return Object.keys(by).sort().filter(function (y) { return count(by[y]) >= min; });
    };

    // --- último año de lluvia (12 meses con datos)
    var rain = months.filter(function (m) { return isNum(m.precipMmTotal); }).slice(-12);
    if (rain.length >= 6) {
      facts["zona.meses_lluvia"] = rain.length;
      facts["zona.lluvia12"] = rain.reduce(function (s, m) { return s + m.precipMmTotal; }, 0);
      facts["zona.meses_secos"] = rain.filter(function (m) { return m.precipMmTotal < DRY_MONTH_MM; }).length;
    }

    // --- canícula observada: julio-agosto frente a junio y septiembre
    var evaluated = 0;
    var canicula = 0;
    var flags = [];
    Object.keys(rainBy).sort().forEach(function (y) {
      var r = rainBy[y];
      if (![6, 7, 8, 9].every(function (m) { return isNum(r[m]); })) return;
      evaluated++;
      var hit = Math.min(r[7], r[8]) < CANICULA_RATIO * (r[6] + r[9]) / 2;
      flags.push(hit ? 1 : 0);
      if (hit) canicula++;
    });
    if (evaluated > 0) {
      facts["zona.anios_evaluados"] = evaluated;
      facts["zona.canicula_anios"] = canicula;
      facts["zona.canicula_frec"] = canicula / evaluated * 100;
      if (evaluated >= 4) facts["zona.canicula_recientes"] = flags.slice(-3).reduce(function (s, v) { return s + v; }, 0);
    }

    // --- humedad del suelo (SMAP)
    var smapVals = months.filter(function (m) { return isNum(m.rootzoneM3m3Mean); });
    if (months.length) facts["zona.smap"] = (smapVals.length || months.some(function (m) { return isNum(m.surfaceM3m3Mean); })) ? 1 : 0;
    if (smapVals.length >= 2) facts["zona.smap_reciente"] = mean(smapVals.slice(-3).map(function (m) { return m.rootzoneM3m3Mean; }));

    // --- vigor frente al mismo mes del año anterior
    var withNdvi = months.filter(function (m) { return isNum(m[key]); });
    if (withNdvi.length) {
      var last = withNdvi[withNdvi.length - 1];
      var prevYear = (Number(last.month.slice(0, 4)) - 1) + last.month.slice(4, 7);
      var prev = months.filter(function (m) { return m.month.slice(0, 7) === prevYear; })[0];
      if (prev && isNum(prev[key]) && prev[key] > 0) facts["zona.ndvi_cambio"] = (last[key] / prev[key] - 1) * 100;
    }

    // --- tendencias: últimos 3 años frente a los anteriores
    var fullRain = yearsOf(rainBy, 12);
    var annual = fullRain.map(function (y) { return Object.keys(rainBy[y]).reduce(function (s, m) { return s + rainBy[y][m]; }, 0); });
    facts["zona.anios_completos"] = fullRain.length;
    var trendRain = recentVsEarlier(annual);
    if (trendRain !== null) facts["zona.lluvia_tendencia"] = trendRain;

    var julAug = Object.keys(rainBy).sort().filter(function (y) { return isNum(rainBy[y][7]) && isNum(rainBy[y][8]); })
      .map(function (y) { return rainBy[y][7] + rainBy[y][8]; });
    var trendJA = recentVsEarlier(julAug);
    if (trendJA !== null) facts["zona.julago_tendencia"] = trendJA;

    var fullTemp = yearsOf(tempBy, 12);
    if (fullTemp.length >= 6) {
      var tAnnual = fullTemp.map(function (y) { return mean(Object.keys(tempBy[y]).map(function (m) { return tempBy[y][m]; })); });
      facts["zona.temp_tendencia"] = mean(tAnnual.slice(-3)) - mean(tAnnual.slice(0, -3));
    }

    var ndviYears = yearsOf(ndviBy, 10);
    var nAnnual = ndviYears.map(function (y) { return mean(Object.keys(ndviBy[y]).map(function (m) { return ndviBy[y][m]; })); });
    var trendNdvi = recentVsEarlier(nAnnual);
    if (trendNdvi !== null) facts["zona.ndvi_tendencia"] = trendNdvi;

    // --- proyección lineal de la lluvia anual (solo si hay 6 años completos), limitada al rango observado
    if (annual.length >= 6) {
      var n = annual.length;
      var xs = annual.map(function (_, k) { return k; });
      var mx = mean(xs), my = mean(annual);
      var sxy = 0, sxx = 0;
      xs.forEach(function (x, k) { sxy += (x - mx) * (annual[k] - my); sxx += (x - mx) * (x - mx); });
      var slope = sxx > 0 ? sxy / sxx : 0;
      var pred = my + slope * (n - mx);
      pred = Math.max(Math.min.apply(null, annual), Math.min(Math.max.apply(null, annual), pred));
      facts["zona.lluvia_media_anual"] = my;
      facts["zona.proy_lluvia_anual"] = pred;
      facts["zona.proy_vs_media"] = (pred / my - 1) * 100;
      var dryYears = annual.filter(function (v) { return v < 0.85 * my; }).length;
      facts["zona.anios_secos_frec"] = dryYears / n * 100;
    }

    // --- próximos tres meses según el historial de esos mismos meses
    var lastRain = months.filter(function (m) { return isNum(m.precipMmTotal); });
    if (lastRain.length) {
      var lm = lastRain[lastRain.length - 1];
      var next = [1, 2, 3].map(function (k) { return ((Number(lm.month.slice(5, 7)) - 1 + k) % 12) + 1; });
      var sums = [], dryShare = [], ok = true;
      next.forEach(function (mo) {
        var vals = Object.keys(rainBy).map(function (y) { return rainBy[y][mo]; }).filter(isNum);
        if (vals.length < 3) { ok = false; return; }
        sums.push(mean(vals));
        dryShare.push(vals.filter(function (v) { return v < DRY_MONTH_MM; }).length / vals.length * 100);
      });
      if (ok) {
        facts["zona.prox_meses"] = MONTH_NAMES[next[0] - 1] + ", " + MONTH_NAMES[next[1] - 1] + " y " + MONTH_NAMES[next[2] - 1];
        facts["zona.proy_lluvia_3m"] = sums.reduce(function (s, v) { return s + v; }, 0);
        facts["zona.prox_prob_seco"] = mean(dryShare);
      }
    }

    // --- perspectiva: cuántas señales de riesgo se cumplen (al menos 3 deben poder evaluarse)
    var signals = [
      ["zona.lluvia_tendencia", function (v) { return v <= -10; }],
      ["zona.julago_tendencia", function (v) { return v <= -15; }],
      ["zona.temp_tendencia", function (v) { return v >= 0.4; }],
      ["zona.canicula_recientes", function (v) { return v >= 2; }],
      ["zona.ndvi_tendencia", function (v) { return v <= -5; }]
    ];
    var evaluable = signals.filter(function (s) { return isNum(facts[s[0]]); });
    if (evaluable.length >= 3) {
      var points = evaluable.filter(function (s) { return s[1](facts[s[0]]); }).length;
      facts["zona.riesgo_puntos"] = points;
      facts["zona.riesgo_senales"] = evaluable.length;
      facts["zona.riesgo"] = points >= 3 ? "alto" : (points === 2 ? "medio" : "bajo");
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
      if (kind === "abs" && typeof v === "number") return Math.abs(v).toFixed(dec === undefined ? 0 : Number(dec)).replace(".", ",");
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
  function build(rules, strategies, months, today) {
    var facts = buildFacts(strategies, completeMonths(months, today));
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

  // Resumen breve: una frase por línea (resultados, riesgo y recomendación); gana la primera variante que se cumple.
  function buildBrief(rules, strategies, months, today) {
    var facts = buildFacts(strategies, completeMonths(months, today));
    var lines = [];
    ((rules && rules.resumen_breve) || []).forEach(function (line) {
      for (var i = 0; i < (line.variantes || []).length; i++) {
        var v = line.variantes[i];
        if (!evalCond(v.cuando, facts)) continue;
        var text = renderText(v.texto, facts, rules);
        if (text) { lines.push(text); break; }
      }
    });
    return lines;
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

  root.TerraShiftInterpretation = { completeMonths: completeMonths, build: build, buildBrief: buildBrief, buildFacts: buildFacts, evalCond: evalCond, renderText: renderText, load: load };
  if (typeof module !== "undefined" && module.exports) module.exports = root.TerraShiftInterpretation;
})(typeof window !== "undefined" ? window : this);
