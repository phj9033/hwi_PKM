// graph.js — bootstrap vis-network from #graph-data on page load.
(function () {
  var dataEl = document.getElementById("graph-data");
  if (!dataEl) return;
  var payload = JSON.parse(dataEl.textContent);
  if (!payload) return;

  var GROUP_COLORS = {
    concepts: "#4a7fc1",
    entities: "#5aa86b",
    notes: "#d6863e",
    reports: "#9b6bc8",
    writing: "#888",
    captures: "#bbb",
  };
  var EDGE_STYLES = {
    wikilink: { color: "#888", dashes: false, width: 1.5 },
    derived_from: { color: "#aaa", dashes: [4, 4], width: 1 },
    suggested: { color: "#e25b3b", dashes: [2, 6], width: 1.2 },
  };

  var nodes = payload.nodes.map(function (n) {
    return {
      id: n.id,
      label: n.label,
      x: n.x,
      y: n.y,
      color: { background: GROUP_COLORS[n.group] || "#999", border: "#444" },
      shape: "dot",
      size: 10,
    };
  });
  var allEdges = payload.edges.map(function (e, i) {
    var style = EDGE_STYLES[e.type] || EDGE_STYLES.wikilink;
    return {
      id: i,
      from: e.from,
      to: e.to,
      type: e.type,
      color: style.color,
      dashes: style.dashes,
      width: style.width,
    };
  });

  var data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(allEdges) };
  var options = {
    physics: { stabilization: { iterations: 100 }, barnesHut: { springLength: 120 } },
    interaction: { hover: true },
    nodes: { font: { size: 11 } },
  };
  var container = document.getElementById("graph-canvas");
  var network = new vis.Network(container, data, options);

  function applyFilter() {
    var qEl = document.getElementById("filter-q");
    var q = (qEl ? qEl.value : "").toLowerCase().trim();
    var showWiki = document.getElementById("t-wikilink").checked;
    var showDerived = document.getElementById("t-derived").checked;
    var showSuggested = document.getElementById("t-suggested").checked;
    var keep = allEdges.filter(function (e) {
      if (e.type === "wikilink" && !showWiki) return false;
      if (e.type === "derived_from" && !showDerived) return false;
      if (e.type === "suggested" && !showSuggested) return false;
      if (q) {
        var fromHit = e.from.toLowerCase().indexOf(q) !== -1;
        var toHit = e.to.toLowerCase().indexOf(q) !== -1;
        if (!fromHit && !toHit) return false;
      }
      return true;
    });
    data.edges.clear();
    data.edges.add(keep);
  }

  ["t-wikilink", "t-derived", "t-suggested"].forEach(function (id) {
    document.getElementById(id).addEventListener("change", applyFilter);
  });
  document.getElementById("filter-q").addEventListener("input", applyFilter);

  network.on("click", function (params) {
    var sidebar = document.getElementById("graph-sidebar");
    if (!params.nodes.length) {
      sidebar.innerHTML = '<p class="empty">Click a node to see its connections.</p>';
      return;
    }
    var nodeId = params.nodes[0];
    var inc = allEdges.filter(function (e) { return e.to === nodeId; });
    var out = allEdges.filter(function (e) { return e.from === nodeId; });
    var sug = allEdges.filter(function (e) {
      return (e.from === nodeId || e.to === nodeId) && e.type === "suggested";
    });
    function fmt(list) {
      return list.length
        ? "<ul>" + list.map(function (e) {
            var other = e.from === nodeId ? e.to : e.from;
            return "<li>" + other + " <small>(" + e.type + ")</small></li>";
          }).join("") + "</ul>"
        : '<p class="empty">none</p>';
    }
    sidebar.innerHTML =
      "<h2>" + nodeId + "</h2>" +
      "<h3>incoming</h3>" + fmt(inc) +
      "<h3>outgoing</h3>" + fmt(out) +
      "<h3>suggested</h3>" + fmt(sug);
  });
})();
