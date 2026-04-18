const searchInput   = document.getElementById("search-input");
const searchBtn     = document.getElementById("search-btn");
const searchResults = document.getElementById("search-results");

// ── Search ─────────────────────────────────────────────────────────────────

searchBtn.addEventListener("click", async function () {
  const query = searchInput.value.trim();
  if (!query) return;

  try {
    const response = await fetch("/api/search?q=" + encodeURIComponent(query));

    if (!response.ok) {
      throw new Error("Search failed: " + response.status);
    }

    const data = await response.json();

    searchResults.innerHTML = renderResults(data.results);

  } catch (err) {
    searchResults.innerHTML = "<p>Search error: " + err.message + "</p>";
  }
});

searchInput.addEventListener("input", function () {
  if (searchInput.value === "") {
    searchResults.innerHTML = "";
  }
});

// ── Helpers ────────────────────────────────────────────────────────────────

function renderResults(results) {
  if (!results.length) return "<p>No results.</p>";
  return results
    .map(r => `<div class="result-item">${r.name} — $${r.price}</div>`)
    .join("");
}
