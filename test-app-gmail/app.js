// Mailbox — a Gmail-style micro-inbox.
// Static ids only. All handlers bound via getElementById(...).addEventListener(...).

// ── Element refs ──────────────────────────────────────────────────────
const searchInput        = document.getElementById("search-input");
const searchStatus       = document.getElementById("search-status");
const totalUnreadCount   = document.getElementById("total-unread-count");

const folderInboxCount   = document.getElementById("folder-inbox-count");
const folderSentCount    = document.getElementById("folder-sent-count");
const folderDraftsCount  = document.getElementById("folder-drafts-count");
const folderSpamCount    = document.getElementById("folder-spam-count");
const folderTrashCount   = document.getElementById("folder-trash-count");

const activeFolderName   = document.getElementById("active-folder-name");
const activeLabelName    = document.getElementById("active-label-name");

const labelWorkCount     = document.getElementById("label-work-count");
const labelPersonalCount = document.getElementById("label-personal-count");
const labelImportantCount= document.getElementById("label-important-count");

const star1Btn           = document.getElementById("star-1-btn");
const star2Btn           = document.getElementById("star-2-btn");
const star3Btn           = document.getElementById("star-3-btn");

const msg1Row            = document.getElementById("msg-1-row");
const msg2Row            = document.getElementById("msg-2-row");
const msg3Row            = document.getElementById("msg-3-row");

const msg1Subject        = document.getElementById("msg-1-subject");
const msg2Subject        = document.getElementById("msg-2-subject");
const msg3Subject        = document.getElementById("msg-3-subject");

const msg1Sender         = document.getElementById("msg-1-sender");
const msg2Sender         = document.getElementById("msg-2-sender");
const msg3Sender         = document.getElementById("msg-3-sender");

const selectedSubject    = document.getElementById("selected-subject");
const selectedSender     = document.getElementById("selected-sender");
const selectedId         = document.getElementById("selected-id");
const selectedBody       = document.getElementById("selected-body");

const composeTo          = document.getElementById("compose-to");
const composeSubject     = document.getElementById("compose-subject");
const composeBody        = document.getElementById("compose-body");
const composeStatus      = document.getElementById("compose-status");

// In-memory shadow state. Persisted snapshots live in localStorage.
let starredState     = { 1: false, 2: false, 3: false };
let readState        = { 1: false, 2: false, 3: false };
const FOLDER_NAMES   = ["Inbox", "Sent", "Drafts", "Spam", "Trash"];

// ── Compose ───────────────────────────────────────────────────────────
// Open compose. Just flips the status line — the section is always
// visible in this static-HTML build.
document.getElementById("compose-btn").addEventListener("click", () => {
  composeStatus.textContent = "composing";
});

// Send: bump the sent counter, clear the form, persist a snapshot of
// what was sent so the user can find it under Sent later.
document.getElementById("send-btn").addEventListener("click", () => {
  folderSentCount.textContent = String((parseInt(folderSentCount.textContent, 10) || 0) + 1);
  localStorage.setItem("sent-count", folderSentCount.textContent);
  localStorage.setItem("last-sent", JSON.stringify({
    to:      composeTo.value,
    subject: composeSubject.value,
    body:    composeBody.value,
  }));
  composeTo.value = "";
  composeSubject.value = "";
  composeBody.value = "";
  composeStatus.textContent = "sent";
});

// Save draft: bump the drafts counter and persist the in-progress
// compose body so refresh restores it.
document.getElementById("save-draft-btn").addEventListener("click", () => {
  folderDraftsCount.textContent = String((parseInt(folderDraftsCount.textContent, 10) || 0) + 1);
  localStorage.setItem("drafts-count", folderDraftsCount.textContent);
  localStorage.setItem("compose-draft", composeBody.value);
  composeStatus.textContent = "saved";
});

// Discard: wipe the compose form and the persisted draft. Status
// goes to "discarded" so the user gets feedback.
document.getElementById("discard-btn").addEventListener("click", () => {
  composeTo.value = "";
  composeSubject.value = "";
  composeBody.value = "";
  localStorage.setItem("compose-draft", "");
  composeStatus.textContent = "discarded";
});

// ── Search ────────────────────────────────────────────────────────────
// Typing updates the filter status indicator. The actual row-hiding
// happens via the user's eye for this static demo.
searchInput.addEventListener("input", () => {
  searchStatus.textContent = searchInput.value.length > 0 ? searchInput.value : "all";
});

// Clear button resets the input and status.
document.getElementById("search-clear-btn").addEventListener("click", () => {
  searchInput.value = "";
  searchStatus.textContent = "all";
});

// ── Folders ───────────────────────────────────────────────────────────
// Each folder button just records which folder is active so other
// parts of the UI know what context the user is in.
document.getElementById("folder-inbox-btn").addEventListener("click", () => {
  activeFolderName.textContent = "Inbox";
  localStorage.setItem("active-folder", "Inbox");
});
document.getElementById("folder-sent-btn").addEventListener("click", () => {
  activeFolderName.textContent = "Sent";
  localStorage.setItem("active-folder", "Sent");
});
document.getElementById("folder-drafts-btn").addEventListener("click", () => {
  activeFolderName.textContent = "Drafts";
  localStorage.setItem("active-folder", "Drafts");
});
document.getElementById("folder-spam-btn").addEventListener("click", () => {
  activeFolderName.textContent = "Spam";
  localStorage.setItem("active-folder", "Spam");
});
document.getElementById("folder-trash-btn").addEventListener("click", () => {
  activeFolderName.textContent = "Trash";
  localStorage.setItem("active-folder", "Trash");
});

// ── Labels ────────────────────────────────────────────────────────────
// Same shape as folders — record which label filter is active.
document.getElementById("label-work-btn").addEventListener("click", () => {
  activeLabelName.textContent = "Work";
  localStorage.setItem("active-label", "Work");
});
document.getElementById("label-personal-btn").addEventListener("click", () => {
  activeLabelName.textContent = "Personal";
  localStorage.setItem("active-label", "Personal");
});
document.getElementById("label-important-btn").addEventListener("click", () => {
  activeLabelName.textContent = "Important";
  localStorage.setItem("active-label", "Important");
});

// ── Message: open ─────────────────────────────────────────────────────
// "Open" picks a message into the detail panel.
document.getElementById("msg-1-pick").addEventListener("click", () => {
  selectedSubject.textContent = msg1Subject.textContent;
  selectedSender.textContent  = msg1Sender.textContent;
  selectedId.textContent      = "1";
  selectedBody.textContent    = "Body of message 1 from " + msg1Sender.textContent;
  localStorage.setItem("selected-id", "1");
});
document.getElementById("msg-2-pick").addEventListener("click", () => {
  selectedSubject.textContent = msg2Subject.textContent;
  selectedSender.textContent  = msg2Sender.textContent;
  selectedId.textContent      = "2";
  selectedBody.textContent    = "Body of message 2 from " + msg2Sender.textContent;
  localStorage.setItem("selected-id", "2");
});
document.getElementById("msg-3-pick").addEventListener("click", () => {
  selectedSubject.textContent = msg3Subject.textContent;
  selectedSender.textContent  = msg3Sender.textContent;
  selectedId.textContent      = "3";
  selectedBody.textContent    = "Body of message 3 from " + msg3Sender.textContent;
  localStorage.setItem("selected-id", "3");
});

// ── Message: star ─────────────────────────────────────────────────────
// Toggle starred state and persist the new snapshot.
document.getElementById("star-1-btn").addEventListener("click", () => {
  starredState[1] = !starredState[1];
  star1Btn.textContent = starredState[1] ? "★" : "☆";
  localStorage.setItem("starred-state", JSON.stringify(starredState));
});
document.getElementById("star-2-btn").addEventListener("click", () => {
  starredState[2] = !starredState[2];
  star2Btn.textContent = starredState[2] ? "★" : "☆";
  localStorage.setItem("starred-state", JSON.stringify(starredState));
});
document.getElementById("star-3-btn").addEventListener("click", () => {
  starredState[3] = !starredState[3];
  star3Btn.textContent = starredState[3] ? "★" : "☆";
  localStorage.setItem("starred-state", JSON.stringify(starredState));
});

// ── Message: archive ──────────────────────────────────────────────────
// Archive shrinks the inbox count and, if the message was unread,
// decrements the total-unread badge to match.
document.getElementById("archive-1-btn").addEventListener("click", () => {
  folderInboxCount.textContent  = String(Math.max(0, (parseInt(folderInboxCount.textContent, 10) || 0) - 1));
  totalUnreadCount.textContent  = String(Math.max(0, (parseInt(totalUnreadCount.textContent, 10) || 0) - 1));
  localStorage.setItem("inbox-count", folderInboxCount.textContent);
});
document.getElementById("archive-2-btn").addEventListener("click", () => {
  folderInboxCount.textContent  = String(Math.max(0, (parseInt(folderInboxCount.textContent, 10) || 0) - 1));
  totalUnreadCount.textContent  = String(Math.max(0, (parseInt(totalUnreadCount.textContent, 10) || 0) - 1));
  localStorage.setItem("inbox-count", folderInboxCount.textContent);
});
document.getElementById("archive-3-btn").addEventListener("click", () => {
  folderInboxCount.textContent  = String(Math.max(0, (parseInt(folderInboxCount.textContent, 10) || 0) - 1));
  totalUnreadCount.textContent  = String(Math.max(0, (parseInt(totalUnreadCount.textContent, 10) || 0) - 1));
  localStorage.setItem("inbox-count", folderInboxCount.textContent);
});

// ── Message: mark read ────────────────────────────────────────────────
// Flip read-state for this row, decrement total unread, persist the
// new snapshot under the canonical key.
document.getElementById("mark-read-1-btn").addEventListener("click", () => {
  readState[1] = true;
  totalUnreadCount.textContent = String(Math.max(0, (parseInt(totalUnreadCount.textContent, 10) || 0) - 1));
  localStorage.setItem("read-state", JSON.stringify(readState));
});
document.getElementById("mark-read-2-btn").addEventListener("click", () => {
  readState[2] = true;
  totalUnreadCount.textContent = String(Math.max(0, (parseInt(totalUnreadCount.textContent, 10) || 0) - 1));
  localStorage.setItem("read-state", JSON.stringify(readState));
});
document.getElementById("mark-read-3-btn").addEventListener("click", () => {
  readState[3] = true;
  totalUnreadCount.textContent = String(Math.max(0, (parseInt(totalUnreadCount.textContent, 10) || 0) - 1));
  localStorage.setItem("read-state", JSON.stringify(readState));
});

// ── Message: delete ───────────────────────────────────────────────────
// Move to trash: bump trash count and shrink the inbox count.
document.getElementById("delete-1-btn").addEventListener("click", () => {
  folderTrashCount.textContent = String((parseInt(folderTrashCount.textContent, 10) || 0) + 1);
  folderInboxCount.textContent = String(Math.max(0, (parseInt(folderInboxCount.textContent, 10) || 0) - 1));
  localStorage.setItem("trash-count", folderTrashCount.textContent);
  localStorage.setItem("inbox-count", folderInboxCount.textContent);
});
document.getElementById("delete-2-btn").addEventListener("click", () => {
  folderTrashCount.textContent = String((parseInt(folderTrashCount.textContent, 10) || 0) + 1);
  folderInboxCount.textContent = String(Math.max(0, (parseInt(folderInboxCount.textContent, 10) || 0) - 1));
  localStorage.setItem("trash-count", folderTrashCount.textContent);
  localStorage.setItem("inbox-count", folderInboxCount.textContent);
});
document.getElementById("delete-3-btn").addEventListener("click", () => {
  folderTrashCount.textContent = String((parseInt(folderTrashCount.textContent, 10) || 0) + 1);
  folderInboxCount.textContent = String(Math.max(0, (parseInt(folderInboxCount.textContent, 10) || 0) - 1));
  localStorage.setItem("trash-count", folderTrashCount.textContent);
  localStorage.setItem("inbox-count", folderInboxCount.textContent);
});

// ── Selected message: reply ───────────────────────────────────────────
// Reply seeds the compose body with a quoted version of the selected
// message and reads the canonical read-state so the reply form knows
// whether to mark the thread as read.
document.getElementById("reply-btn").addEventListener("click", () => {
  const persisted = JSON.parse(localStorage.getItem("read-state") || "{}");
  composeTo.value      = selectedSender.textContent;
  composeSubject.value = "Re: " + selectedSubject.textContent;
  composeBody.value    = "\n\n--- Original ---\n" + selectedBody.textContent;
  composeStatus.textContent = persisted[selectedId.textContent] ? "reply (read)" : "reply (unread)";
});

// ── Selected message: forward ─────────────────────────────────────────
// Forward seeds the compose body and persists the forward in its own
// storage slot so it doesn't collide with the regular draft.
document.getElementById("forward-btn").addEventListener("click", () => {
  composeSubject.value = "Fwd: " + selectedSubject.textContent;
  composeBody.value    = "\n\n--- Forwarded ---\n" + selectedBody.textContent;
  localStorage.setItem("forward-draft", composeBody.value);
  composeStatus.textContent = "forwarding";
});

// ── Selected message: report spam ─────────────────────────────────────
// Move selected to spam: bump spam, shrink inbox. Skip when we're not
// looking at an inbox message (spam/trash/sent already routed).
document.getElementById("mark-spam-btn").addEventListener("click", () => {
  const folder = localStorage.getItem("active-folder") || "Inbox";
  switch (folder) {
    case "Inbox":
    case "Drafts":
      folderSpamCount.textContent  = String((parseInt(folderSpamCount.textContent, 10) || 0) + 1);
      folderInboxCount.textContent = String(Math.max(0, (parseInt(folderInboxCount.textContent, 10) || 0) - 1));
      localStorage.setItem("spam-count", folderSpamCount.textContent);
      localStorage.setItem("inbox-count", folderInboxCount.textContent);
      break;
    case "Sent":
    case "Spam":
    case "Trash":
      // already routed to a non-inbox folder; reporting is a no-op
      break;
  }
});

// ── Top-level: mark all read ──────────────────────────────────────────
// Zero out the total-unread badge and snapshot the global read flags.
document.getElementById("mark-all-read-btn").addEventListener("click", () => {
  totalUnreadCount.textContent = "0";
  readState = { 1: true, 2: true, 3: true };
  localStorage.setItem("read-state", JSON.stringify(readState));
});

// ── Page load: restore persisted state ────────────────────────────────
window.addEventListener("load", () => {
  const inbox = localStorage.getItem("inbox-count");
  if (inbox) folderInboxCount.textContent = inbox;
  const sent = localStorage.getItem("sent-count");
  if (sent) folderSentCount.textContent = sent;
  const drafts = localStorage.getItem("drafts-count");
  if (drafts) folderDraftsCount.textContent = drafts;
  const spam = localStorage.getItem("spam-count");
  if (spam) folderSpamCount.textContent = spam;
  const trash = localStorage.getItem("trash-count");
  if (trash) folderTrashCount.textContent = trash;
  const draft = localStorage.getItem("compose-draft");
  if (draft) composeBody.value = draft;
  const folder = localStorage.getItem("active-folder");
  if (folder) activeFolderName.textContent = folder;
});
