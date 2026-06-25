// Notice fixture for the id-in-template-literal phase 2 work.
//
// Clicking the button writes a fresh `<div id="notice-msg">…</div>` into
// the host container's innerHTML. The child element only exists in the
// runtime DOM after this click — there's no `getElementById('notice-msg')`
// call in the source. The scan_ids extractor should still pick up
// `notice-msg` from the template literal, and the CodeQL queries should
// treat this innerHTML assignment as a write to `notice-msg`.
//
// Constraint to verify:
//   P(w(notice-msg) | A(show-notice-btn)) = 1
// should PASS path_exists + all_paths_write end-to-end.

const showNoticeBtn = document.getElementById("show-notice-btn");
const noticeHost    = document.getElementById("notice-host");

showNoticeBtn.addEventListener("click", function () {
  noticeHost.innerHTML = `<div id="notice-msg">Hello — this notice was just rendered.</div>`;
});
