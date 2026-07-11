// Multi-hop test app.
// Each button's handler writes its display through a chain of helper calls.
// Constraints of the form P(w(display-N) | A(btn-N)) = 1 should PASS with
// interprocedural depth ≥ N+1.

const display0 = document.getElementById("display-0");
const display1 = document.getElementById("display-1");
const display2 = document.getElementById("display-2");
const display3 = document.getElementById("display-3");
const display4 = document.getElementById("display-4");
const displayBroken = document.getElementById("display-broken");

// ── Direct write (0 hops): handler writes inline ──
document.getElementById("btn-0").addEventListener("click", () => {
  display0.textContent = "written";
});

// ── 1 hop: handler → helper → write ──
function writeDisplay1() {
  display1.textContent = "written";
}
document.getElementById("btn-1").addEventListener("click", () => {
  writeDisplay1();
});

// ── 2 hops: handler → outer → inner → write ──
function inner2() {
  display2.textContent = "written";
}
function outer2() {
  inner2();
}
document.getElementById("btn-2").addEventListener("click", () => {
  outer2();
});

// ── 3 hops: handler → a → b → c → write ──
function c3() {
  display3.textContent = "written";
}
function b3() {
  c3();
}
function a3() {
  b3();
}
document.getElementById("btn-3").addEventListener("click", () => {
  a3();
});

// ── 4 hops: handler → a → b → c → d → write ──
function d4() {
  display4.textContent = "written";
}
function c4() {
  d4();
}
function b4() {
  c4();
}
function a4() {
  b4();
}
document.getElementById("btn-4").addEventListener("click", () => {
  a4();
});

// ── Broken multi-hop: one branch skips the write ──
// Handler → outerBroken → (if random > 0.5) writes / (else) does nothing.
// Even with unbounded interprocedural depth, all_paths_write should FAIL
// because one branch inside the helper legitimately doesn't write.
function innerBroken() {
  displayBroken.textContent = "written";
}
function outerBroken() {
  if (Math.random() > 0.5) {
    innerBroken();
  }
  // else: no write — this is the branch that breaks universality.
}
document.getElementById("btn-broken").addEventListener("click", () => {
  outerBroken();
});

// ── If/else where BOTH branches write the target ──
// Universality holds: no matter which branch runs, the target is written.
// If all_paths_write is reachability-based (every exit dominated by a
// write), this passes. If it's naive path-existence, it might fail.
const displayIfelse = document.getElementById("display-ifelse");
document.getElementById("btn-ifelse").addEventListener("click", () => {
  if (Math.random() > 0.5) {
    displayIfelse.textContent = "true-branch";
  } else {
    displayIfelse.textContent = "false-branch";
  }
});

// ── If/else nested inside a helper (both branches write) ──
// Handler → helper. Helper has if/else, both branches write. Universality
// should still hold through the interprocedural check.
const displayIfelseNested = document.getElementById("display-ifelse-nested");
function ifelseHelper() {
  if (Math.random() > 0.5) {
    displayIfelseNested.textContent = "true-branch";
  } else {
    displayIfelseNested.textContent = "false-branch";
  }
}
document.getElementById("btn-ifelse-nested").addEventListener("click", () => {
  ifelseHelper();
});

// ── classList.add on element ──
const displayClasslist = document.getElementById("display-classlist");
document.getElementById("btn-classlist").addEventListener("click", () => {
  displayClasslist.classList.add("visible");
});

// ── classList.toggle on element ──
const displayClasslistToggle = document.getElementById("display-classlist-toggle");
document.getElementById("btn-classlist-toggle").addEventListener("click", () => {
  displayClasslistToggle.classList.toggle("active");
});

// ── style.setProperty on element ──
const displayStyle = document.getElementById("display-style");
document.getElementById("btn-style").addEventListener("click", () => {
  displayStyle.style.setProperty("color", "red");
});
