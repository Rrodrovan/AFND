/* Navegación flotante, animaciones de scroll, barra de avance y botón "volver arriba".
   Solo mejora visual y de orden: sin este archivo la página funciona igual. */
(function () {
  "use strict";
  var doc = document;

  // ---- Navegación por secciones: solo muestra las que ya tienen contenido y marca la activa ----
  var nav = doc.querySelector(".nav");
  var links = nav ? Array.prototype.slice.call(nav.querySelectorAll("a[data-target]")) : [];
  function targetVisible(id) {
    var t = doc.getElementById(id);
    if (!t || t.hidden) return false;
    if (id === "results-block") { var r = doc.getElementById("results"); return !!(r && r.children.length > 0); }
    return true;
  }
  function spy() {
    if (!nav) return;
    var active = null;
    links.forEach(function (a) {
      if (a.hidden) return;
      var t = doc.getElementById(a.dataset.target);
      if (t && t.getBoundingClientRect().top <= 140) active = a;
    });
    links.forEach(function (a) {
      var on = a === active;
      a.classList.toggle("is-active", on);
      if (on) { a.setAttribute("aria-current", "true"); } else { a.removeAttribute("aria-current"); }
    });
    if (active && nav.scrollWidth > nav.clientWidth) {
      nav.scrollTo({ left: active.offsetLeft - nav.clientWidth / 2 + active.clientWidth / 2, behavior: "smooth" });
    }
  }
  function syncNav() {
    if (!nav) return;
    var any = false;
    links.forEach(function (a) { var ok = targetVisible(a.dataset.target); a.hidden = !ok; if (ok) any = true; });
    nav.hidden = !any;
    spy();
  }
  var navTimer = 0;
  function queueSync() { if (!navTimer) navTimer = window.setTimeout(function () { navTimer = 0; syncNav(); }, 60); }
  var main = doc.querySelector("main");
  if (nav && main && "MutationObserver" in window) {
    new MutationObserver(queueSync).observe(main, { attributes: true, attributeFilter: ["hidden"], childList: true, subtree: true });
  }
  syncNav();
  var spyTick = false;
  window.addEventListener("scroll", function () {
    if (!spyTick) { spyTick = true; window.requestAnimationFrame(function () { spyTick = false; spy(); }); }
  }, { passive: true });

  // ---- Animaciones (se omiten si la persona pidió reducir movimiento) ----
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) return;

  doc.documentElement.classList.add("js");

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
    });
  }, { threshold: 0, rootMargin: "0px 0px -8% 0px" });

  function watch(node, delay) {
    if (!node || node.classList.contains("reveal")) return;
    node.classList.add("reveal");
    if (delay) node.style.setProperty("--d", delay + "ms");
    io.observe(node);
  }

  doc.querySelectorAll(".controls, .panel, .summary, .note, .section-head, .site-footer").forEach(function (n) { watch(n, 0); });

  var results = doc.getElementById("results");
  if (results) {
    var tagCards = function () {
      Array.prototype.forEach.call(results.children, function (c, i) { watch(c, i * 120); });
    };
    new MutationObserver(tagCards).observe(results, { childList: true });
    tagCards();
  }

  var bar = doc.createElement("div");
  bar.className = "progress";
  bar.setAttribute("aria-hidden", "true");
  var top = doc.createElement("button");
  top.type = "button"; top.className = "to-top"; top.textContent = "↑";
  top.setAttribute("aria-label", "Volver arriba");
  top.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
  doc.body.appendChild(bar); doc.body.appendChild(top);

  var ticking = false;
  function update() {
    var max = doc.documentElement.scrollHeight - window.innerHeight;
    var y = window.pageYOffset || 0;
    bar.style.transform = "scaleX(" + (max > 0 ? Math.min(1, y / max) : 0) + ")";
    top.classList.toggle("is-on", y > 600);
    ticking = false;
  }
  window.addEventListener("scroll", function () { if (!ticking) { ticking = true; window.requestAnimationFrame(update); } }, { passive: true });
  update();
})();
