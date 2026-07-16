(function () {
    "use strict";
    var API = window.location.pathname.replace(/\/view\/?$/, "");
    var overlay = null, input = null, results = null, active = -1;
    var targetInput = null, mode = "add";
    var SEARCH_ICON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4"/><line x1="10" y1="10" x2="14" y2="14"/></svg>';
    var CLOSE_ICON = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';

    function el(tag, cls) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        return node;
    }
    function normalize(item) {
        if (!item || typeof item !== "object") return null;
        var symbol = String(item.symbol || item.ticker || "").trim();
        if (!symbol) return null;
        var ticker = symbol.indexOf(":") >= 0 ? symbol.split(":").pop().trim().toUpperCase() : symbol.toUpperCase();
        return {
            symbol: symbol,
            ticker: ticker,
            displaySymbol: ticker || symbol,
            fullName: String(item.name || item.full_name || item.fullName || "").trim(),
            description: String(item.description || "").trim(),
            exchange: String(item.exchange || "").trim(),
            type: String(item.asset_type || item.type || "").trim(),
        };
    }

    function build() {
        overlay = el("div", "tv-settings-overlay");
        overlay.style.display = "none";
        var panel = el("div", "tv-symbol-search-panel");
        overlay.appendChild(panel);

        var header = el("div", "tv-compare-header");
        var h3 = document.createElement("h3");
        h3.textContent = "Symbol Search";
        header.appendChild(h3);
        var close = el("button", "tv-settings-close");
        close.innerHTML = CLOSE_ICON;
        close.addEventListener("click", hide);
        header.appendChild(close);
        panel.appendChild(header);

        var row = el("div", "tv-compare-search-row");
        var icon = el("span", "tv-compare-search-icon");
        icon.innerHTML = SEARCH_ICON;
        row.appendChild(icon);
        input = document.createElement("input");
        input.type = "text";
        input.className = "tv-compare-search-input";
        input.placeholder = "Search symbol...";
        input.autocomplete = "off";
        input.spellcheck = false;
        row.appendChild(input);
        panel.appendChild(row);

        results = el("div", "tv-symbol-search-results");
        panel.appendChild(results);

        overlay.addEventListener("click", function (e) { if (e.target === overlay) hide(); });
        var timer = null;
        input.addEventListener("input", function () {
            if (timer) clearTimeout(timer);
            timer = setTimeout(search, 180);
        });
        input.addEventListener("keydown", function (e) {
            var rows = results.querySelectorAll(".tv-compare-result-row");
            if (e.key === "Escape") { hide(); }
            else if (e.key === "ArrowDown") { e.preventDefault(); move(1, rows); }
            else if (e.key === "ArrowUp") { e.preventDefault(); move(-1, rows); }
            else if (e.key === "Enter") {
                e.preventDefault();
                var pick = rows[active >= 0 ? active : 0];
                if (pick) pick.click();
            }
        });
        document.body.appendChild(overlay);
    }
    function move(delta, rows) {
        if (!rows.length) return;
        active = Math.max(0, Math.min(active + delta, rows.length - 1));
        for (var i = 0; i < rows.length; i++) rows[i].classList.toggle("tv-active", i === active);
        rows[active].scrollIntoView({ block: "nearest" });
    }
    function render(rowsData) {
        results.innerHTML = "";
        active = -1;
        var items = (rowsData || []).map(normalize).filter(Boolean);
        if (!items.length) {
            if (input.value.trim()) {
                var empty = el("div", "tv-compare-search-empty");
                empty.textContent = "No symbols found";
                results.appendChild(empty);
            }
            return;
        }
        var list = el("div", "tv-compare-results-list");
        items.forEach(function (info) {
            var row = el("div", "tv-compare-result-row tv-symbol-search-result-row");
            var identity = el("div", "tv-compare-result-identity");
            var badge = el("div", "tv-compare-result-badge");
            badge.textContent = (info.symbol || "?").slice(0, 1);
            identity.appendChild(badge);
            var copy = el("div", "tv-compare-result-copy");
            var top = el("div", "tv-compare-result-top");
            var sym = el("span", "tv-compare-result-symbol");
            sym.textContent = info.displaySymbol;
            top.appendChild(sym);
            var parts = [];
            if (info.exchange) parts.push(info.exchange);
            if (info.type) parts.push(info.type);
            if (parts.length) {
                var meta = el("span", "tv-compare-result-meta");
                meta.textContent = parts.join(" · ");
                top.appendChild(meta);
            }
            copy.appendChild(top);
            var nameText = info.fullName || info.description;
            if (nameText) {
                var sub = el("div", "tv-compare-result-sub");
                sub.textContent = nameText;
                copy.appendChild(sub);
            }
            identity.appendChild(copy);
            row.appendChild(identity);
            row.addEventListener("click", function () { pick(info.ticker || info.symbol); });
            list.appendChild(row);
        });
        results.appendChild(list);
    }
    function search() {
        var q = input.value.trim();
        if (!q) { results.innerHTML = ""; return; }
        fetch(API + "/search?query=" + encodeURIComponent(q) + "&limit=50")
            .then(function (r) { return r.json(); })
            .then(function (rows) { render(Array.isArray(rows) ? rows : []); })
            .catch(function () { render([]); });
    }
    function setValue(node, value) {
        node.value = value;
        node.dispatchEvent(new Event("input", { bubbles: true }));
        node.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function pick(symbol) {
        symbol = String(symbol).toUpperCase();
        if (targetInput) {
            if (mode === "add") {
                var cur = targetInput.value.split(/[,;\s]+/).map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean);
                if (cur.indexOf(symbol) === -1) cur.push(symbol);
                setValue(targetInput, cur.join(","));
            } else {
                setValue(targetInput, symbol);
            }
        }
        hide();
    }
    function show(target, m) {
        if (!overlay) build();
        targetInput = target;
        mode = m;
        input.value = "";
        results.innerHTML = "";
        overlay.style.display = "";
        input.focus();
    }
    function hide() {
        if (overlay) overlay.style.display = "none";
    }

    function addIcon(node, m) {
        var group = (node.closest && node.closest(".pywry-input-group")) || node.parentNode;
        if (!group || group.querySelector(".rrg-search-icon")) return;
        var icon = el("span", "rrg-search-icon");
        icon.innerHTML = SEARCH_ICON;
        icon.title = "Search symbols";
        icon.addEventListener("click", function () { show(node, m); });
        group.appendChild(icon);
    }
    function attach() {
        var sym = document.getElementById("symbols");
        var ben = document.getElementById("benchmark");
        if (!sym || !ben) { setTimeout(attach, 60); return; }
        addIcon(sym, "add");
        addIcon(ben, "replace");
    }
    attach();
})();
