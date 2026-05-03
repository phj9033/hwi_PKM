// search.js — client for /search.html.
// Fetches sibling search-index.json, filters by substring of title+snippet
// and tag intersection, renders top-50 results.

(async function () {
  let data;
  try {
    const resp = await fetch("search-index.json");
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    data = await resp.json();
  } catch (e) {
    console.error("search: failed to load index", e);
    const el = document.getElementById("results");
    if (el) {
      el.innerHTML =
        '<li class="empty">no index available — run pkm dashboard build</li>';
    }
    return;
  }
  const q = document.getElementById("q");
  const tag = document.getElementById("tag");
  const results = document.getElementById("results");

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[c];
    });
  }

  function render(items) {
    results.innerHTML = items
      .slice(0, 50)
      .map(function (d) {
        const title = d.url
          ? '<a href="' + escapeHtml(d.url) + '">' + escapeHtml(d.title) + "</a>"
          : escapeHtml(d.title);
        const tags = (d.tags || [])
          .map(function (t) {
            return '<span class="tag">' + escapeHtml(t) + "</span>";
          })
          .join(" ");
        return (
          "<li><h3>" +
          title +
          "</h3><p>" +
          escapeHtml(d.snippet || "") +
          "</p><p>" +
          tags +
          "</p></li>"
        );
      })
      .join("");
  }

  function filter() {
    const qs = (q.value || "").toLowerCase().trim();
    const ts = (tag.value || "").toLowerCase().trim();
    let items = data;
    if (qs) {
      items = items.filter(function (d) {
        return (d.title + " " + (d.snippet || ""))
          .toLowerCase()
          .includes(qs);
      });
    }
    if (ts) {
      items = items.filter(function (d) {
        return (d.tags || [])
          .map(function (t) {
            return t.toLowerCase();
          })
          .includes(ts);
      });
    }
    render(items);
  }

  q.addEventListener("input", filter);
  tag.addEventListener("input", filter);
  filter();
})();
