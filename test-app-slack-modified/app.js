// Slacky — micro-workspace.
// Static ids only. Every handler bound via getElementById(...).addEventListener(...).

// ── Element refs ──────────────────────────────────────────────────────
const composeInput          = document.getElementById("compose-input");
const messageCount          = document.getElementById("message-count");
const notificationCount     = document.getElementById("notification-count");
const mentionCount          = document.getElementById("mention-count");
const currentStatus         = document.getElementById("current-status");
const statusSelector        = document.getElementById("status-selector");
const themeInput            = document.getElementById("theme-input");
const themeDisplay          = document.getElementById("theme-display");
const notificationsEnabled  = document.getElementById("notifications-enabled");
const statsDisplay          = document.getElementById("stats-display");
const activeChannelName     = document.getElementById("active-channel-name");

const channel1Name          = document.getElementById("channel-1-name");
const channel2Name          = document.getElementById("channel-2-name");
const channel3Name          = document.getElementById("channel-3-name");
const channel1UnreadCount   = document.getElementById("channel-1-unread-count");
const channel2UnreadCount   = document.getElementById("channel-2-unread-count");
const channel3UnreadCount   = document.getElementById("channel-3-unread-count");

const react1Count           = document.getElementById("react-1-count");
const react2Count           = document.getElementById("react-2-count");

const usernameInput         = document.getElementById("username-input");
const usernameDisplay       = document.getElementById("username-display");
const topicInput            = document.getElementById("topic-input");
const topicDisplay          = document.getElementById("topic-display");
const pinnedDisplay         = document.getElementById("pinned-display");
const searchInput           = document.getElementById("search-input");
const searchStatus          = document.getElementById("search-status");
const onlineRosterDisplay   = document.getElementById("online-roster-display");

let notificationsOn = true;

// ── Compose ───────────────────────────────────────────────────────────
// Typing auto-saves the draft so refresh restores in-flight messages.
composeInput.addEventListener("input", () => {
  localStorage.setItem("draft", composeInput.value);
});

// Send: increment the message counter and clear the saved draft. We
// leave the textarea contents so the user can scroll back through the
// last thing they typed.
document.getElementById("send-message-btn").addEventListener("click", () => {
  if (composeInput.value.length > 0) {
    messageCount.textContent = String((parseInt(messageCount.textContent, 10) || 0) + 1);
    localStorage.setItem("draft", "");
  }
});

// Pin the most recently sent message. Snapshots the current count.
document.getElementById("pin-last-btn").addEventListener("click", () => {
  pinnedDisplay.textContent = "Message #" + messageCount.textContent;
  localStorage.setItem("pinned", messageCount.textContent);
});

// ── Channels ──────────────────────────────────────────────────────────
// Clicking a channel button activates it — copy the channel name into
// the "Active" display.
document.getElementById("channel-1-btn").addEventListener("click", () => {
  activeChannelName.textContent = channel1Name.textContent;
});
document.getElementById("channel-2-btn").addEventListener("click", () => {
  activeChannelName.textContent = channel2Name.textContent;
});
document.getElementById("channel-3-btn").addEventListener("click", () => {
  activeChannelName.textContent = channel3Name.textContent;
});

// Mark-as-read clears the unread badge for that channel and
// deducts those messages from the global bell.
document.getElementById("mark-channel-1-read-btn").addEventListener("click", () => {
  const cleared = parseInt(channel1UnreadCount.textContent, 10) || 0;
  notificationCount.textContent = String(Math.max(0, (parseInt(notificationCount.textContent, 10) || 0) - cleared));
  channel2UnreadCount.textContent = "0";
});
document.getElementById("mark-channel-2-read-btn").addEventListener("click", () => {
  channel2UnreadCount.textContent = "0";
});
document.getElementById("mark-channel-3-read-btn").addEventListener("click", () => {
  channel3UnreadCount.textContent = "0";
});

// ── Search ────────────────────────────────────────────────────────────
// Show the current channel-list filter state.
searchInput.addEventListener("input", () => {
  searchStatus.textContent = searchInput.value.length > 0 ? searchInput.value : "all";
});

// ── Notifications ─────────────────────────────────────────────────────
// Mark-all-read zeros the global badge.
document.getElementById("mark-all-read-btn").addEventListener("click", () => {
  notificationCount.textContent = "0";
});

// Clear-mentions zeros the @ badge and resets the persisted
// notification cache so the next load starts fresh.
document.getElementById("clear-mentions-btn").addEventListener("click", () => {
  mentionCount.textContent = "0";
  localStorage.setItem("notification-state", JSON.stringify({}));
});

// ── Reactions on the last message ─────────────────────────────────────
// Each click increments the matching reaction's count. Reactions also
// surface as engagement signals in the mentions feed.
document.getElementById("react-1-btn").addEventListener("click", () => {
  react1Count.textContent = String((parseInt(react1Count.textContent, 10) || 0) + 1);
  mentionCount.textContent = String((parseInt(mentionCount.textContent, 10) || 0) + 1);
});
document.getElementById("react-2-btn").addEventListener("click", () => {
  react2Count.textContent = String((parseInt(react2Count.textContent, 10) || 0) + 1);
});

// ── Profile ───────────────────────────────────────────────────────────
// Save the typed display name into both the sidebar and storage.
document.getElementById("save-username-btn").addEventListener("click", () => {
  usernameDisplay.textContent = usernameInput.value;
  localStorage.setItem("username", usernameInput.value);
});

// ── Channel topic ─────────────────────────────────────────────────────
// Update the active channel's topic line and persist it.
document.getElementById("save-topic-btn").addEventListener("click", () => {
  topicDisplay.textContent = topicInput.value;
  localStorage.setItem("topic", topicInput.value);
});

// ── Status / settings ─────────────────────────────────────────────────
// Set the current status from the selector and persist it.
document.getElementById("set-status-btn").addEventListener("click", () => {
  const value = statusSelector.value;
  switch (value) {
    case "online":
    case "away":
    case "busy":
      currentStatus.textContent = value;
      localStorage.setItem("status", value);
      break;
    case "offline":
      currentStatus.textContent = value;
      localStorage.setItem("status", value);
      break;
  }
});

// Snapshot the current theme, swap the display, then persist.
document.getElementById("save-settings-btn").addEventListener("click", () => {
  const current = themeDisplay.textContent;
  themeDisplay.textContent = themeInput.value;
  localStorage.setItem("theme", JSON.stringify({ value: current }));
});

// Toggle in-app notifications on/off. Only persist when enabling
// since "off" is the default state we restore on load.
document.getElementById("toggle-notifications-btn").addEventListener("click", () => {
  notificationsOn = !notificationsOn;
  notificationsEnabled.textContent = notificationsOn ? "on" : "off";
  if (notificationsOn) {
    localStorage.setItem("notification-prefs", JSON.stringify({ enabled: true }));
  }
});

// ── Online roster ─────────────────────────────────────────────────────
// Show the static set of currently online teammates.
document.getElementById("show-online-btn").addEventListener("click", () => {
  onlineRosterDisplay.textContent = "alice, bob, carol";
});

// ── Stats ─────────────────────────────────────────────────────────────
// Show the total of sent messages from the cached stats record so the
// display paints immediately even before the live counter rehydrates.
document.getElementById("show-stats-btn").addEventListener("click", () => {
  const cached = JSON.parse(localStorage.getItem("message-stats") || '{"count":0}');
  statsDisplay.textContent = String(cached.count);
});
