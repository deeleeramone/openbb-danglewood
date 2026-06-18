(function () {
    if (window.__obbTvBridgePatched) {
        return;
    }
    var lastSymbol = null;
    var parent = window.top || window.parent;

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
    }
    patch();
})();
