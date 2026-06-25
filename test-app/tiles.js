// Class-binding fixture (phase 3b).
//
// Render button populates the host with three "tile" cards whose
// only common identifier is a CSS class — no per-instance id. We then
// bind click handlers on every .tile via querySelectorAll(...).forEach.
//
// Each tile click bumps tile-click-count.
//
// Constraints to verify:
//   P(w(tile-click-count) | A(.tile)) = 1     -> should PASS once a
//     constraint pipeline supports class selectors end-to-end.
//   P(w(tile-host) | A(render-tiles-btn)) = 1 -> regression for
//     phase-1/2: container update via innerHTML assignment.

const renderTilesBtn = document.getElementById("render-tiles-btn");
const tileHost       = document.getElementById("tile-host");
const tileClickCount = document.getElementById("tile-click-count");

let clicks = 0;

renderTilesBtn.addEventListener("click", function () {
  tileHost.innerHTML = `
    <div class="tile">Tile 1</div>
    <div class="tile">Tile 2</div>
    <div class="tile">Tile 3</div>
  `;
  document.querySelectorAll(".tile").forEach(el => {
    el.addEventListener("click", function () {
      clicks += 1;
      tileClickCount.textContent = String(clicks);
    });
  });
});
