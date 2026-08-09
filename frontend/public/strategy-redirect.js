(() => {
  "use strict";

  // The strategy lab moved into the research center's 策略验证 view. Old links keep
  // working by replacing themselves with the new owner; replace (not assign) means the
  // back button never loops into this redirect page.
  const allowed = new Set(["ssq", "dlt", "3d", "pl3", "kl8"]);
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("game");
  const game = allowed.has(raw) ? raw : "ssq";
  window.location.replace(`./analysis.html?game=${encodeURIComponent(game)}&view=strategy`);
})();
