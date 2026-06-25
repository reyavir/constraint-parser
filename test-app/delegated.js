// Body-delegation fixture (phase 3c).
// Single document-level click listener dispatches based on data-del.
// Constraint to verify:
//   P(w(del-count) | A(del-btn-a)) = 1   should PASS
// — phase 3c's registeredViaBodyDelegation should tie this delegated
// handler to del-btn-a via its data-del attribute.

let delCount = 0;
const delCountSpan = document.getElementById("del-count");

document.addEventListener("click", function (e) {
  if (e.target.dataset.del) {
    delCount += 1;
    delCountSpan.textContent = String(delCount);
  }
});
