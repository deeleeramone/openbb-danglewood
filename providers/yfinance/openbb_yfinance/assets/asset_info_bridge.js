(function () {
  // OpenBB Workspace iframe handshake for the Asset Info widget. Mirrors the
  // screener builder: announce the widget and its `symbol` param via
  // `openbb-connect` so the Workspace wires the shared Symbol group (and MCP)
  // into this iframe, answer `openbb-request` with the current overview as
  // `openbb-data`, and reload to the new symbol when the group changes.
  var island = window.__obbAssetInfo || {};
  var widgetId = island.widgetId || "yfinance_asset_info_obb";
  var symbol = String(island.symbol || "").toUpperCase();
  var summary = island.data || { symbol: symbol };
  var target = window.top || window.parent;
  if (!target || target === window) return;

  var manifest = {
    widgetId: widgetId,
    name: "Asset Info (Yahoo Finance)",
    description: "Styled asset overview for the current symbol.",
    dataType: "table",
  };

  function connect() {
    // Announce the widget for the openbb-data feed and MCP, but do NOT declare
    // params here — the visible `symbol` param comes from the server-side
    // widget_config, and re-declaring it over openbb-connect renders it as a
    // hidden connection-internal param instead.
    target.postMessage({ type: "openbb-connect", widgets: [manifest] }, "*");
  }
  function pushData() {
    // Match the screener's accepted shape: dataType "table" with the overview as
    // a single-row array (the Workspace rejects a bare "object" data response).
    target.postMessage(
      { type: "openbb-data", widgetId: widgetId, dataType: "table", data: [summary] },
      "*"
    );
  }
  function incomingSymbol(d) {
    if (d.type === "openbb-connect" || d.type === "openbb-data") return null;
    var p = d.params || d.data || d;
    var s = p && (p.symbol || p.ticker);
    return s ? String(s).toUpperCase() : null;
  }
  function reloadTo(sym) {
    var u = new URL(window.location.href);
    u.searchParams.set("symbol", sym);
    window.location.replace(u.toString());
  }

  window.addEventListener("message", function (event) {
    var d = event.data;
    if (!d || typeof d !== "object") return;
    if (d.type === "openbb-request") {
      pushData();
      return;
    }
    var sym = incomingSymbol(d);
    if (sym && sym !== symbol) reloadTo(sym);
  });

  connect();
  pushData();
})();
