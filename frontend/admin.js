// Revisión de zonas propuestas. El token solo vive en esta variable mientras la página está abierta.
(function () {
  "use strict";

  var cfg = window.TERRASHIFT_CONFIG;
  var base = cfg.apiBase.replace(/\/+$/, "") + "/api/v1/admin/zones";
  var token = "";

  var form = document.getElementById("admin-form");
  var tokenInput = document.getElementById("token");
  var msg = document.getElementById("admin-msg");
  var list = document.getElementById("pending");

  function setMessage(kind, text) {
    msg.className = "zone-msg zone-msg--" + kind;
    msg.textContent = text;
  }

  async function call(path, method) {
    var res = await fetch(base + path, { method: method, headers: { "X-Admin-Token": token, Accept: "application/json" } });
    var body = null;
    try { body = await res.json(); } catch (_) { /* sin cuerpo */ }
    if (!res.ok) {
      var text = body && body.error ? body.error : "Error " + res.status;
      var err = new Error(text);
      err.status = res.status;
      throw err;
    }
    return body;
  }

  function osmUrl(z) {
    return "https://www.openstreetmap.org/?minlon=" + z.minLon + "&minlat=" + z.minLat +
      "&maxlon=" + z.maxLon + "&maxlat=" + z.maxLat + "&box=yes";
  }

  function item(z) {
    var row = document.createElement("div");
    row.className = "admin__item";

    var info = document.createElement("div");
    var title = document.createElement("h3");
    title.textContent = z.name;
    var coords = document.createElement("p");
    coords.textContent = z.code + " · oeste " + z.minLon + ", sur " + z.minLat + ", este " + z.maxLon + ", norte " + z.maxLat + " · ";
    var link = document.createElement("a");
    link.href = osmUrl(z);
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "ver en el mapa";
    coords.appendChild(link);
    info.appendChild(title);
    info.appendChild(coords);

    var actions = document.createElement("div");
    actions.className = "admin__actions";
    [["approve", "Aprobar", ""], ["reject", "Rechazar", "button--ghost"]].forEach(function (a) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = a[1];
      if (a[2]) button.className = a[2];
      button.addEventListener("click", async function () {
        if (a[0] === "reject" && !window.confirm('¿Rechazar la zona "' + z.name + '"?')) return;
        actions.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
        try {
          await call("/" + encodeURIComponent(z.code) + "/" + a[0], "POST");
          setMessage("ok", (a[0] === "approve" ? "Aprobada: " : "Rechazada: ") + z.name + ".");
          await load();
        } catch (err) {
          setMessage("error", err.message);
          actions.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
        }
      });
      actions.appendChild(button);
    });

    row.appendChild(info);
    row.appendChild(actions);
    return row;
  }

  async function load() {
    list.replaceChildren();
    try {
      var zones = await call("/pending", "GET");
      if (zones.length === 0) {
        setMessage("info", "No hay solicitudes pendientes.");
        return;
      }
      setMessage("info", zones.length + " solicitud(es) pendiente(s).");
      zones.forEach(function (z) { list.appendChild(item(z)); });
    } catch (err) {
      var text = err.status === 401 ? "Token incorrecto." :
        err.status === 404 ? "La administración no está activada en el servidor." :
        err.status === 429 ? err.message :
        "No se pudo contactar con el servidor.";
      setMessage("error", text);
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    token = tokenInput.value;
    load();
  });
})();
