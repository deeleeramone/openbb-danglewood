(function () {
    if (window.__obbTvBridgePatched) {
        return;
    }
    var island = window.__obbTvChart || {};
    var lastSymbol = null;
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
        if (!parent || parent === window) return;
        parent.postMessage(
            {
                type: "openbb-connect",
                widgets: [manifest],
                params: [{ paramName: "symbol", label: "Symbol", type: "text", value: symbol }],
            },
            "*"
        );
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
        var payload = data && (data.params || data.data || data);
        var nextSymbol = payload && (payload.symbol || payload.ticker);
        if (!nextSymbol) return;
        nextSymbol = String(nextSymbol).toUpperCase();
        if (nextSymbol === symbol) return;
        symbol = nextSymbol;
        lastSymbol = nextSymbol;
        if (window.pywry && typeof window.pywry.emit === "function") {
            window.pywry.emit("tvchart:symbol-search", {
                query: nextSymbol,
                autoSelect: true,
                chartId: chartId,
            });
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
        // When the chart's main series symbol changes (TV search / symbol picker
        // emits tvchart:data-request with seriesId "main"), push it to the
        // OpenBB Workspace so the shared symbol group — and every linked widget,
        // e.g. Asset Info — follows.
        if (!data || data.seriesId !== "main" || !data.symbol) return;
        var sym = String(data.symbol).toUpperCase();
        if (sym === lastSymbol || !parent || parent === window) return;
        lastSymbol = sym;
        parent.postMessage(
            { type: "openbb:widget-params:update", params: { symbol: sym } },
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
            if (type === "tvchart:data-request") {
                try {
                    syncSymbolToWorkspace(data);
                } catch (e) {
                    /* workspace sync is best-effort */
                }
            }
        };
        connect();
        pushData();
    }
    patch();
})();
