/* Animaciones de scroll, barra de avance y botón "volver arriba". Solo mejora visual: sin esto la página funciona igual. */
(function () {
  "use strict";
  var doc = document;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) return;

  doc.documentElement.classList.add("js");

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });

  function watch(node, delay) {
    if (!node || node.classList.contains("reveal")) return;
    node.classList.add("reveal");
    if (delay) node.style.setProperty("--d", delay + "ms");
    io.observe(node);
  }

  doc.querySelectorAll(".controls, .panel, .summary, .note, .footer").forEach(function (n) { watch(n, 0); });

  var results = doc.getElementById("results");
  if (results) {
    var tagCards = function () {
      Array.prototype.forEach.call(results.children, function (c, i) { watch(c, i * 110); });
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
