// Settings fixture — two handlers against localStorage["settings"]:
//
//   save-settings-btn   → writes JSON containing nickname-input.value
//                         (Rule 3 PASS for r(nickname-input))
//   reset-settings-btn  → writes a hardcoded constant payload
//                         (Rule 3 FAIL if a constraint claims user-input
//                          taint, because no user input flows in)
//
// Both handlers are straight-line — no try/catch, no early returns — so
// all_paths_write PASSES for both. The PASS / FAIL split is driven
// entirely by the source-set check on r(nickname-input).

const nicknameInput   = document.getElementById("nickname-input");
const saveSettingsBtn = document.getElementById("save-settings-btn");
const resetSettingsBtn = document.getElementById("reset-settings-btn");

const DEFAULT_SETTINGS = { nickname: "guest" };

saveSettingsBtn.addEventListener("click", function () {
  const payload = JSON.stringify({ nickname: nicknameInput.value });
  localStorage.setItem("settings", payload);
});

resetSettingsBtn.addEventListener("click", function () {
  const payload = JSON.stringify(DEFAULT_SETTINGS);
  localStorage.setItem("settings", payload);
});
