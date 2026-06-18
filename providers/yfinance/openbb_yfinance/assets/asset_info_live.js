(function () {
    if (window.__obbAssetInfoLive) {
        return;
    }

    function fmt(value) {
        if (value === null || value === undefined) {
            return "—";
        }
        return Number(value).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function fmtCompact(value) {
        if (value === null || value === undefined) {
            return "—";
        }
        value = Number(value);
        var units = [["T", 1e12], ["B", 1e9], ["M", 1e6], ["K", 1e3]];
        for (var i = 0; i < units.length; i++) {
            if (Math.abs(value) >= units[i][1]) {
                return fmt(value / units[i][1]) + units[i][0];
            }
        }
        return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    }

    function attrNum(el, attr) {
        if (!el) {
            return null;
        }
        var v = parseFloat(el.getAttribute(attr));
        return isNaN(v) ? null : v;
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) {
            el.textContent = text;
        }
    }

    var dayEl = document.getElementById("ai-day-range");
    var weekEl = document.getElementById("ai-week-range");
    var dayHigh = attrNum(dayEl, "data-high");
    var dayLow = attrNum(dayEl, "data-low");
    var weekHigh = attrNum(weekEl, "data-high");
    var weekLow = attrNum(weekEl, "data-low");

    function renderRange(el, low, high) {
        if (el && low !== null && high !== null) {
            el.textContent = fmt(low) + " – " + fmt(high);
        }
    }

    function applyQuote(data) {
        if (!data) {
            return;
        }
        var price = data.price;

        if (price !== null && price !== undefined) {
            setText("ai-price", fmt(price));
        }

        if (
            data.change !== null &&
            data.change !== undefined &&
            data.changePercent !== null &&
            data.changePercent !== undefined
        ) {
            var changeEl = document.getElementById("ai-change");
            if (changeEl) {
                var up = Number(data.change) >= 0;
                var sign = up ? "+" : "";
                changeEl.textContent =
                    sign + fmt(data.change) + " (" + sign + fmt(data.changePercent) + "%)";
                changeEl.classList.remove("ai-up", "ai-down");
                changeEl.classList.add(up ? "ai-up" : "ai-down");
            }
        }

        if (data.dayHigh !== null && data.dayHigh !== undefined) {
            dayHigh = data.dayHigh;
        }
        if (data.dayLow !== null && data.dayLow !== undefined) {
            dayLow = data.dayLow;
        }
        if (price !== null && price !== undefined) {
            if (dayHigh === null || price > dayHigh) dayHigh = price;
            if (dayLow === null || price < dayLow) dayLow = price;
            if (weekHigh !== null && price > weekHigh) weekHigh = price;
            if (weekLow !== null && price < weekLow) weekLow = price;
        }
        renderRange(dayEl, dayLow, dayHigh);
        renderRange(weekEl, weekLow, weekHigh);

        if (data.marketCap !== null && data.marketCap !== undefined) {
            setText("ai-market-cap", fmtCompact(data.marketCap));
        }
        if (data.volume !== null && data.volume !== undefined) {
            setText("ai-volume", fmtCompact(data.volume));
        }
        if (data.vol24 !== null && data.vol24 !== undefined) {
            setText("ai-volume-24h", fmtCompact(data.vol24));
        }
    }

    function register() {
        if (!window.pywry || typeof window.pywry.on !== "function") {
            setTimeout(register, 20);
            return;
        }
        window.__obbAssetInfoLive = true;
        window.pywry.on("assetinfo:quote", applyQuote);
    }

    register();
})();
