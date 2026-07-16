(function () {
    "use strict";
    var island = window.__obbRrg || {};
    var ids = island.tableWidgetIds || {};
    var STUDY = ids.study_data || "yfinance_rrg_study_data_obb";
    var RATIOS = ids.rs_ratios || "yfinance_rrg_ratios_obb";
    var MOMENTUM = ids.rs_momentum || "yfinance_rrg_momentum_obb";
    var target = window.top || window.parent;
    if (!target || target === window) return;

    var MANIFESTS = [
        { widgetId: STUDY, name: "RRG Study Data (Yahoo Finance)", description: "Price/volume/volatility series for the symbols and benchmark.", dataType: "table" },
        { widgetId: RATIOS, name: "RRG RS-Ratio (Yahoo Finance)", description: "Relative strength ratio by date and symbol.", dataType: "table" },
        { widgetId: MOMENTUM, name: "RRG RS-Momentum (Yahoo Finance)", description: "Relative strength momentum by date and symbol.", dataType: "table" },
    ];
    var KEY_BY_ID = {};
    KEY_BY_ID[STUDY] = "study_data";
    KEY_BY_ID[RATIOS] = "rs_ratios";
    KEY_BY_ID[MOMENTUM] = "rs_momentum";
    var WIDGET_DATA = {};
    MANIFESTS.forEach(function (m) {
        WIDGET_DATA[m.widgetId] = { type: "openbb-data", widgetId: m.widgetId, dataType: "table", data: [] };
    });

    function seed(data) {
        if (!data) return;
        Object.keys(KEY_BY_ID).forEach(function (id) {
            var rows = data[KEY_BY_ID[id]];
            if (Array.isArray(rows)) WIDGET_DATA[id].data = rows;
        });
    }
    function connect() {
        target.postMessage({ type: "openbb-connect", widgets: MANIFESTS }, "*");
    }
    function pushData(id) {
        if (WIDGET_DATA[id]) target.postMessage(WIDGET_DATA[id], "*");
    }
    function pushAll() { Object.keys(WIDGET_DATA).forEach(pushData); }

    window.addEventListener("message", function (event) {
        var d = event.data;
        if (!d || typeof d !== "object") return;
        if (d.type === "openbb-request") {
            if (d.widgetId == null) pushAll();
            else pushData(d.widgetId);
        }
    });

    function register() {
        if (!window.pywry || typeof window.pywry.on !== "function") { setTimeout(register, 20); return; }
        window.pywry.on("rrg:data", function (detail) {
            if (detail && detail.data) { seed(detail.data); pushAll(); }
        });
    }

    seed(island.data);
    connect();
    pushAll();
    register();
})();
