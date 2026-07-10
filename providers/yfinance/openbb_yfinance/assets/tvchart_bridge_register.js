(function () {
    if (window.__obbTvBridgePatched) {
        return;
    }
    var island = window.__obbTvChart || {};
    var parent = window.top || window.parent;
    var widgetId = island.widgetId || "yfinance_tvchart_obb";
    var chartId = island.chartId || (widgetId ? widgetId + "_chart" : "tvchart_chart");
    var symbol = String(island.symbol || "").toUpperCase();
    var interval = String(island.interval || "1d");
    var manifest = {
        widgetId: widgetId,
        name: "TradingView Chart (Yahoo Finance)",
        description: "Interactive TradingView chart for the current symbol.",
        dataType: "table",
    };

    function connect() {
        // Announce the widget for the openbb-data feed and MCP only. Do NOT
        // declare params here: the visible symbol/interval params come from the
        // server-side widget_config. Re-declaring them over openbb-connect
        // registers duplicate connection-internal params, and the Workspace then
        // echoes group changes back to this iframe as a reload.
        if (!parent || parent === window) return;
        parent.postMessage({ type: "openbb-connect", widgets: [manifest] }, "*");
    }

    function pushData() {
        if (!parent || parent === window) return;
        parent.postMessage(
            {
                type: "openbb-data",
                widgetId: widgetId,
                dataType: "table",
                data: [{ symbol: symbol, interval: interval, chartId: chartId }],
            },
            "*"
        );
    }

    function syncFromWorkspace(data) {
        // Workspace → chart. Apply symbol/interval changes live (no iframe
        // reload). Each branch commits the local value before emitting the chart
        // event, so the event the chart fires back is recognized as our own
        // (value unchanged) and never echoed to the Workspace.
        var payload = data && (data.params || data.data || data);
        if (!payload) return;
        var pywry = window.pywry;
        var canEmit = pywry && typeof pywry.emit === "function";
        var nextSymbol = payload.symbol || payload.ticker;
        if (nextSymbol) {
            nextSymbol = String(nextSymbol).toUpperCase();
            if (nextSymbol !== symbol) {
                symbol = nextSymbol;
                if (canEmit) {
                    pywry.emit("tvchart:symbol-search", {
                        query: nextSymbol,
                        autoSelect: true,
                        chartId: chartId,
                    });
                }
            }
        }
        var nextInterval = payload.interval;
        if (nextInterval) {
            nextInterval = String(nextInterval);
            if (nextInterval !== interval) {
                interval = nextInterval;
                if (canEmit) {
                    pywry.emit("tvchart:interval-change", {
                        value: nextInterval,
                        chartId: chartId,
                    });
                }
            }
        }
    }

    function handleWorkspaceMessage(d) {
        if (!d || typeof d !== "object") return;
        if (d.type === "openbb-request") {
            pushData();
            return;
        }
        if (d.type === "openbb-connect" || d.type === "openbb-data") return;
        syncFromWorkspace(d);
    }

    function syncSymbolToWorkspace(data) {
        // Chart → Workspace. When the chart's main series symbol changes (TV
        // search / symbol picker emits tvchart:data-request with seriesId
        // "main"), push it to the shared Symbol group so every linked widget —
        // e.g. Asset Info — follows.
        if (!data || data.seriesId !== "main" || !data.symbol) return;
        var sym = String(data.symbol).toUpperCase();
        if (sym === symbol || !parent || parent === window) return;
        symbol = sym;
        parent.postMessage(
            { type: "openbb:widget-params:update", params: { symbol: sym } },
            "*"
        );
    }

    function syncIntervalToWorkspace(data) {
        // Chart → Workspace. Mirror the chart's active interval into the
        // widget's interval param when the user picks one from the toolbar.
        var iv = data && data.value;
        if (!iv) return;
        iv = String(iv);
        if (iv === interval || !parent || parent === window) return;
        interval = iv;
        parent.postMessage(
            { type: "openbb:widget-params:update", params: { interval: iv } },
            "*"
        );
    }

    window.addEventListener("message", function (event) {
        handleWorkspaceMessage(event.data);
    });

    function patch() {
        if (!window.pywry || typeof window._tvRegisterEventHandlers !== "function") {
            setTimeout(patch, 10);
            return;
        }
        window.__obbTvBridgePatched = true;
        window._tvRegisterEventHandlers(window.pywry);
        var origEmit = window.pywry.emit.bind(window.pywry);
        window.pywry.emit = function (type, data) {
            origEmit(type, data);
            try {
                window.pywry._fire(type, data);
            } catch (e) {
                /* local dispatch is best-effort */
            }
            try {
                if (type === "tvchart:data-request") {
                    syncSymbolToWorkspace(data);
                } else if (type === "tvchart:interval-change") {
                    syncIntervalToWorkspace(data);
                }
            } catch (e) {
                /* workspace sync is best-effort */
            }
        };
        connect();
        pushData();
    }
    patch();
})();
