// Mapa para ver las zonas aprobadas y proponer una nueva dibujando un rectángulo (dos clics).
// Todo texto que viene del servidor se muestra con textContent; los rótulos del mapa son elementos DOM, no HTML.
(function (root) {
  "use strict";

  var NICARAGUA_CENTER = [12.9, -85.2];

  function init(cfg, hooks) {
    var L = root.L;
    var section = document.getElementById("zone-picker");
    if (!L || !section) return null;

    var logic = root.TerraShiftZoneLogic;
    var mapEl = document.getElementById("zone-map");
    var drawBtn = document.getElementById("zone-draw");
    var clearBtn = document.getElementById("zone-clear");
    var sendBtn = document.getElementById("zone-send");
    var nameInput = document.getElementById("zone-name");
    var msg = document.getElementById("zone-msg");

    var map = L.map(mapEl, {
      center: NICARAGUA_CENTER,
      zoom: 7,
      minZoom: 6,
      maxBounds: [[10.0, -89.0], [16.0, -81.5]],
      maxBoundsViscosity: 0.8,
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    var approvedLayer = L.layerGroup().addTo(map);
    var drawn = null;      // rectángulo propuesto
    var box = null;        // caja validada del rectángulo
    var firstCorner = null;
    var drawing = false;

    function setMessage(kind, text) {
      msg.className = "zone-msg zone-msg--" + kind;
      msg.textContent = text;
    }

    function refreshSendState() {
      sendBtn.disabled = !(box && logic.validateBox(box).ok && logic.validateName(nameInput.value).ok);
    }

    function stopDrawing() {
      drawing = false;
      firstCorner = null;
      map.getContainer().style.cursor = "";
      drawBtn.textContent = "Dibujar zona";
      drawBtn.setAttribute("aria-pressed", "false");
    }

    function clearDrawing() {
      if (drawn) { map.removeLayer(drawn); drawn = null; }
      box = null;
      stopDrawing();
      setMessage("info", "Pulsa «Dibujar zona» y haz clic en dos esquinas opuestas del mapa.");
      refreshSendState();
    }

    function startDrawing() {
      clearDrawing();
      drawing = true;
      map.getContainer().style.cursor = "crosshair";
      drawBtn.textContent = "Cancelar dibujo";
      drawBtn.setAttribute("aria-pressed", "true");
      setMessage("info", "Haz clic en la primera esquina de la zona.");
    }

    map.on("click", function (event) {
      if (!drawing) return;
      if (!firstCorner) {
        firstCorner = event.latlng;
        drawn = L.rectangle([firstCorner, firstCorner], { color: "#1f5a43", weight: 2, dashArray: "6 4" }).addTo(map);
        setMessage("info", "Ahora haz clic en la esquina opuesta.");
        return;
      }
      box = logic.boxFromCorners(firstCorner, event.latlng);
      drawn.setBounds([[box.minLat, box.minLon], [box.maxLat, box.maxLon]]);
      var check = logic.validateBox(box);
      drawn.setStyle({ color: check.ok ? "#1f5a43" : "#8f1d1d", dashArray: null });
      stopDrawing();
      setMessage(check.ok ? "ok" : "error", check.message);
      refreshSendState();
    });

    map.on("mousemove", function (event) {
      if (drawing && firstCorner && drawn) {
        var preview = logic.boxFromCorners(firstCorner, event.latlng);
        drawn.setBounds([[preview.minLat, preview.minLon], [preview.maxLat, preview.maxLon]]);
      }
    });

    drawBtn.addEventListener("click", function () { drawing ? clearDrawing() : startDrawing(); });
    clearBtn.addEventListener("click", clearDrawing);
    nameInput.addEventListener("input", refreshSendState);

    sendBtn.addEventListener("click", async function () {
      var name = logic.validateName(nameInput.value);
      var check = logic.validateBox(box);
      if (!name.ok) { setMessage("error", name.message); return; }
      if (!check.ok) { setMessage("error", check.message); return; }
      sendBtn.disabled = true;
      setMessage("info", "Enviando solicitud…");
      var result = await root.TerraShiftApi.requestZone(cfg, {
        name: name.name, minLon: box.minLon, minLat: box.minLat, maxLon: box.maxLon, maxLat: box.maxLat,
      });
      if (result.ok) {
        nameInput.value = "";
        clearDrawing();
        setMessage("ok", "Solicitud enviada. El equipo la revisará y, si la aprueba, empezará a descargar los datos de la NASA para esta zona.");
      } else {
        setMessage("error", result.error);
        refreshSendState();
      }
    });

    function showZones(zones) {
      approvedLayer.clearLayers();
      (zones || []).forEach(function (z) {
        var rect = L.rectangle([[z.minLat, z.minLon], [z.maxLat, z.maxLon]], { color: "#9a5b00", weight: 3, fillOpacity: 0.3 });
        var label = document.createElement("span");
        label.textContent = z.name + " (clic para ver estrategias)";
        rect.bindTooltip(label, (zones || []).length === 1 ? { permanent: true, direction: "right", offset: [12, 0] } : { sticky: true });
        rect.on("click", function (event) {
          if (drawing) return; // mientras se dibuja, el clic es de la esquina
          L.DomEvent.stopPropagation(event);
          hooks.onSelectZone(z.code);
        });
        rect.addTo(approvedLayer);
      });
    }

    clearDrawing();
    section.hidden = false;
    // El mapa se creó dentro de una sección que estaba oculta: hay que recalcular su tamaño.
    setTimeout(function () { map.invalidateSize(); }, 0);
    return { showZones: showZones, map: map };
  }

  var api = { init: init };
  root.TerraShiftZonePicker = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
