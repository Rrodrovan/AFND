// Reglas para las zonas propuestas. Son las mismas que valida el servidor (ZoneService); aquí solo sirven
// para avisar al usuario antes de enviar. La validación que cuenta es la del servidor.
(function (root) {
  "use strict";

  var LIMITS = { lonMin: -88.0, lonMax: -82.5, latMin: 10.5, latMax: 15.5, minSide: 0.02, maxSide: 0.5 };
  var NAME_RE = /^[\p{L}\p{N} .,'()-]{3,60}$/u;

  function round4(v) { return Math.round(v * 10000) / 10000; }

  function boxFromCorners(a, b) {
    return {
      minLon: round4(Math.min(a.lng, b.lng)),
      minLat: round4(Math.min(a.lat, b.lat)),
      maxLon: round4(Math.max(a.lng, b.lng)),
      maxLat: round4(Math.max(a.lat, b.lat)),
    };
  }

  // Tamaño aproximado en km (1° de latitud ≈ 111,3 km; el de longitud se reduce con cos(latitud)).
  function sizeKm(box) {
    var midLat = (box.minLat + box.maxLat) / 2;
    return {
      width: (box.maxLon - box.minLon) * 111.32 * Math.cos((midLat * Math.PI) / 180),
      height: (box.maxLat - box.minLat) * 110.57,
    };
  }

  function describeBox(box) {
    var s = sizeKm(box);
    return "≈ " + s.width.toFixed(0) + " × " + s.height.toFixed(0) + " km";
  }

  function validateBox(box) {
    if (!box) return { ok: false, message: "Dibuja un rectángulo sobre el mapa." };
    var width = box.maxLon - box.minLon, height = box.maxLat - box.minLat;
    if (box.minLon < LIMITS.lonMin || box.maxLon > LIMITS.lonMax || box.minLat < LIMITS.latMin || box.maxLat > LIMITS.latMax) {
      return { ok: false, message: "La zona debe estar dentro de Nicaragua." };
    }
    if (width < LIMITS.minSide || height < LIMITS.minSide) {
      return { ok: false, message: "La zona es demasiado pequeña (mínimo unos 2 km por lado)." };
    }
    if (width > LIMITS.maxSide || height > LIMITS.maxSide) {
      return { ok: false, message: "La zona es demasiado grande (máximo unos 55 km por lado)." };
    }
    return { ok: true, message: "Tamaño correcto: " + describeBox(box) + "." };
  }

  function validateName(name) {
    var clean = String(name || "").trim().replace(/\s+/g, " ");
    if (!NAME_RE.test(clean)) {
      return { ok: false, name: clean, message: "El nombre debe tener entre 3 y 60 caracteres (letras, números y signos simples)." };
    }
    return { ok: true, name: clean, message: "" };
  }

  var api = { LIMITS: LIMITS, boxFromCorners: boxFromCorners, validateBox: validateBox, validateName: validateName, describeBox: describeBox };
  root.TerraShiftZoneLogic = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
