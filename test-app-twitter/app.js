// Chirp — micro-feed.
// Static ids only. Every handler bound via getElementById(...).addEventListener(...).

const TWEETS = {
  "1": "Just brewed the best espresso of my life",
  "2": "Hiking Mt. Rainier was unreal",
  "3": "Finally fixed that gnarly bug",
};

// Cached element refs so isElementRef matches via the const pattern.
const tweetInput         = document.getElementById("tweet-input");
const charCount          = document.getElementById("char-count");
const postedBanner       = document.getElementById("posted-banner");
const notificationCount  = document.getElementById("notification-count");
const bioInput           = document.getElementById("bio-input");
const bioDisplay         = document.getElementById("bio-display");
const searchInput        = document.getElementById("search-input");
const searchResultCount  = document.getElementById("search-result-count");
const totalEngagement    = document.getElementById("total-engagement");

const like1Count    = document.getElementById("like-1-count");
const like2Count    = document.getElementById("like-2-count");
const like3Count    = document.getElementById("like-3-count");
const retweet1Count = document.getElementById("retweet-1-count");
const retweet2Count = document.getElementById("retweet-2-count");
const retweet3Count = document.getElementById("retweet-3-count");

// ── Compose ───────────────────────────────────────────────────────────
// Typing updates the character counter and auto-saves the draft to
// localStorage so refresh restores in-flight tweets.
tweetInput.addEventListener("input", () => {
  charCount.textContent = String(280 - tweetInput.value.length);
  localStorage.setItem("draft", tweetInput.value);
});

// Post: when the tweet has content, show the success banner, clear the
// textarea, reset the char counter, and clear the saved draft (it's
// posted now, no need to keep persisting it).
document.getElementById("post-tweet-btn").addEventListener("click", () => {
  if (tweetInput.value.length > 0) {
    postedBanner.textContent = "Tweet posted!";
    tweetInput.value = "";
    charCount.textContent = "280";
    localStorage.setItem("draft", "");
  }
});

// ── Likes / retweets — direct per-id handlers, each self-incrementing
document.getElementById("like-1-btn").addEventListener("click", () => {
  like1Count.textContent = String((parseInt(like1Count.textContent, 10) || 0) + 1);
});
document.getElementById("like-2-btn").addEventListener("click", () => {
  like2Count.textContent = String((parseInt(like2Count.textContent, 10) || 0) + 1);
});
document.getElementById("like-3-btn").addEventListener("click", () => {
  like3Count.textContent = String((parseInt(like3Count.textContent, 10) || 0) + 1);
});
document.getElementById("retweet-1-btn").addEventListener("click", () => {
  retweet1Count.textContent = String((parseInt(retweet1Count.textContent, 10) || 0) + 1);
});
document.getElementById("retweet-2-btn").addEventListener("click", () => {
  retweet2Count.textContent = String((parseInt(retweet2Count.textContent, 10) || 0) + 1);
});
document.getElementById("retweet-3-btn").addEventListener("click", () => {
  retweet3Count.textContent = String((parseInt(retweet3Count.textContent, 10) || 0) + 1);
});

// ── Notifications: mark-all-read sets the badge to literal "0" ────────
document.getElementById("mark-all-read-btn").addEventListener("click", () => {
  notificationCount.textContent = "0";
});

// ── Search: count how many tweets match ──────────────────────────────
document.getElementById("search-btn").addEventListener("click", () => {
  const term = searchInput.value.trim().toLowerCase();
  let n = 0;
  for (const id of Object.keys(TWEETS)) {
    if (!term || TWEETS[id].toLowerCase().includes(term)) n += 1;
  }
  searchResultCount.textContent = String(n);
});

// ── Profile: copy bio-input value to display + persist to storage ────
document.getElementById("save-bio-btn").addEventListener("click", () => {
  bioDisplay.textContent = bioInput.value;
  localStorage.setItem("settings", JSON.stringify({ bio: bioInput.value }));
});

// ── Engagement totals: sum every like count (Row D) ──────────────────
document.getElementById("refresh-engagement-btn").addEventListener("click", () => {
  totalEngagement.textContent = String(
    (parseInt(like1Count.textContent, 10) || 0) +
    (parseInt(like2Count.textContent, 10) || 0) +
    (parseInt(like3Count.textContent, 10) || 0)
  );
});

// ── Notifications panel ──────────────────────────────────────────────
const notificationPanelStatus = document.getElementById("notification-panel-status");
const notification1Status     = document.getElementById("notification-1-status");
const notification2Status     = document.getElementById("notification-2-status");
const notification3Status     = document.getElementById("notification-3-status");

let panelOpen = false;

// Bell toggles the panel and writes the visible status string.
document.getElementById("bell-btn").addEventListener("click", () => {
  panelOpen = !panelOpen;
  notificationPanelStatus.textContent = panelOpen ? "open" : "closed";
});

// Per-item mark-read. Each writes its own status and persists the
// combined notification state to localStorage.
document.getElementById("mark-notification-1-read-btn").addEventListener("click", () => {
  notification1Status.textContent = "read";
  localStorage.setItem("notification-state", JSON.stringify({
    1: "read",
    2: notification2Status.textContent,
    3: notification3Status.textContent,
  }));
});
document.getElementById("mark-notification-2-read-btn").addEventListener("click", () => {
  notification2Status.textContent = "read";
  localStorage.setItem("notification-state", JSON.stringify({
    1: notification1Status.textContent,
    2: "read",
    3: notification3Status.textContent,
  }));
});
document.getElementById("mark-notification-3-read-btn").addEventListener("click", () => {
  notification3Status.textContent = "read";
  localStorage.setItem("notification-state", JSON.stringify({
    1: notification1Status.textContent,
    2: notification2Status.textContent,
    3: "read",
  }));
});

// Clear-all wipes the badge AND each notification's visible status.
document.getElementById("clear-all-notifications-btn").addEventListener("click", () => {
  notification1Status.textContent = "—";
  notification2Status.textContent = "—";
  notification3Status.textContent = "—";
  notificationCount.textContent = "0";
  localStorage.setItem("notification-state", JSON.stringify({}));
});
