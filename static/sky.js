// Gentle depth for the skyline: layers follow the pointer a little (near moves more than far).
// Skipped when the device asks for reduced motion.
(function () {
  var bar = document.getElementById("topbar");
  if (!bar || !window.matchMedia || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var target = 0, current = 0, raf = null;
  function step() {
    current += (target - current) * 0.06;
    bar.style.setProperty("--mx", current.toFixed(3));
    raf = Math.abs(target - current) > 0.002 ? requestAnimationFrame(step) : null;
  }
  window.addEventListener("pointermove", function (e) {
    if (e.pointerType !== "mouse") return;
    target = (e.clientX / window.innerWidth) * 2 - 1;
    if (!raf) raf = requestAnimationFrame(step);
  }, { passive: true });
})();
