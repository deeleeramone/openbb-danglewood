(function () {
    "use strict";
    var island = window.__obbRrg || {};

    document.documentElement.setAttribute(
        "data-rrg-theme",
        String(island.theme).toLowerCase() === "light" ? "light" : "dark"
    );

    function plotDiv() {
        return document.getElementById("chart") || document.querySelector(".js-plotly-plot");
    }

    function applyFrames(frames) {
        var gd = plotDiv();
        if (!gd || !window.Plotly) return;
        var existing = (gd._transitionData && gd._transitionData._frames) || [];
        var indices = existing.map(function (_frame, i) { return i; });
        var cleared = indices.length
            ? window.Plotly.deleteFrames(gd, indices)
            : Promise.resolve();
        cleared.then(function () {
            if (!frames || !frames.length) return;
            window.Plotly.addFrames(gd, frames);
            var first = frames[0] && frames[0].name;
            if (first != null) {
                window.Plotly.animate(gd, [first],
                    { mode: "immediate", transition: { duration: 0 }, frame: { duration: 0, redraw: true } });
            }
        });
    }
    function applyFramesWhenReady(frames) {
        var tries = 0;
        (function attempt() {
            if (plotDiv() && window.Plotly) { applyFrames(frames); return; }
            if (tries++ < 60) setTimeout(attempt, 50);
        })();
    }

    function backfillTooltips() {
        var tips = island.tooltips || {};
        Object.keys(tips).forEach(function (id) {
            var el = document.getElementById(id);
            if (!el || el.hasAttribute("data-tooltip")) return;
            if (el.querySelector("[data-tooltip]") || el.closest("[data-tooltip]")) return;
            var target = el.closest(".pywry-input-group") || el;
            target.setAttribute("data-tooltip", tips[id]);
        });
    }

    function pinTheme() {
        var gd = plotDiv();
        var merge = window.__pywryMergeThemeTemplate;
        var templates = island.templates || {};
        if (!gd || !window.Plotly || !merge || !templates.dark) return;
        gd.__pywry_user_template_dark__ = templates.dark;
        gd.__pywry_user_template_light__ = templates.light;
        var name = gd.__pywry_theme_template__ ||
            (document.documentElement.dataset.theme === "light" ? "plotly_white" : "plotly_dark");
        window.Plotly.relayout(gd, { template: merge(gd, name) });
    }
    function watchTheme() {
        var tries = 0;
        (function attempt() {
            if (plotDiv() && window.Plotly && window.__pywryMergeThemeTemplate) {
                pinTheme();
                new MutationObserver(function () { setTimeout(pinTheme, 0); }).observe(
                    document.documentElement,
                    { attributes: true, attributeFilter: ["data-theme", "class", "style"] }
                );
                if (window.matchMedia) {
                    window.matchMedia("(prefers-color-scheme: dark)")
                        .addEventListener("change", function () { setTimeout(pinTheme, 0); });
                }
                return;
            }
            if (tries++ < 80) setTimeout(attempt, 50);
        })();
    }

    var overlay = null, label = null, watchdog = null;
    function armWatchdog() {
        if (watchdog) clearTimeout(watchdog);
        watchdog = setTimeout(hideOverlay, 60000);
    }
    function ensureOverlay() {
        if (overlay) return overlay;
        overlay = document.createElement("div");
        overlay.className = "rrg-overlay";
        var box = document.createElement("div");
        box.className = "rrg-overlay-box";
        var spinner = document.createElement("div");
        spinner.className = "rrg-spinner";
        label = document.createElement("span");
        label.className = "rrg-overlay-label";
        box.appendChild(spinner);
        box.appendChild(label);
        overlay.appendChild(box);
        document.body.appendChild(overlay);
        return overlay;
    }
    function showLoading(text) {
        var node = ensureOverlay();
        node.classList.remove("rrg-overlay-error");
        node.querySelector(".rrg-spinner").style.display = "";
        label.textContent = text || "Loading…";
        node.style.display = "flex";
    }
    function showError(message) {
        var node = ensureOverlay();
        node.classList.add("rrg-overlay-error");
        node.querySelector(".rrg-spinner").style.display = "none";
        label.textContent = message;
        node.style.display = "flex";
        setTimeout(hideOverlay, 6000);
    }
    function hideOverlay() {
        if (watchdog) { clearTimeout(watchdog); watchdog = null; }
        if (overlay) overlay.style.display = "none";
    }

    var REDRAW = ["study", "long_period", "short_period", "window",
                  "trading_periods", "show_tails", "tail_periods", "tail_interval"];
    function loadingFor(node) {
        if (node.closest("#rrg-submit")) return "Fetching data…";
        for (var i = 0; i < REDRAW.length; i++) {
            var host = node.closest("#" + REDRAW[i]);
            if (!host) continue;
            if (host.classList.contains("pywry-dropdown") &&
                !node.closest(".pywry-dropdown-option")) return null;
            return "Updating chart…";
        }
        return null;
    }
    function onInteract(event) {
        var text = loadingFor(event.target);
        if (text) { showLoading(text); armWatchdog(); }
    }
    function watchInteractions() {
        document.addEventListener("click", onInteract, true);
        document.addEventListener("change", onInteract, true);
    }

    function register() {
        if (!window.pywry || typeof window.pywry.on !== "function") {
            setTimeout(register, 20);
            return;
        }
        window.pywry.on("rrg:status", function (data) {
            if (!data) return;
            if (data.error) { showError(String(data.error)); return; }
            if (data.loading) {
                showLoading(data.fetching ? "Fetching data…" : "Updating chart…");
                return;
            }
            hideOverlay();
        });
        window.pywry.on("plotly:update-figure", function (data) {
            hideOverlay();
            var frames = (data && data.figure && data.figure.frames) || (data && data.frames) || [];
            setTimeout(function () { applyFrames(frames); pinTheme(); }, 120);
        });
    }

    function watchTooltips() {
        var tries = 0;
        (function attempt() {
            if (document.getElementById("study")) { backfillTooltips(); return; }
            if (tries++ < 80) setTimeout(attempt, 50);
        })();
    }

    function resizePlot() {
        var gd = plotDiv();
        if (gd && window.Plotly) window.Plotly.Plots.resize(gd);
    }
    function watchResize() {
        var tries = 0;
        (function attempt() {
            var gd = plotDiv();
            if (gd && window.Plotly && window.ResizeObserver) {
                var host = gd.parentElement || gd;
                var pending = false;
                new ResizeObserver(function () {
                    if (pending) return;
                    pending = true;
                    requestAnimationFrame(function () { pending = false; resizePlot(); });
                }).observe(host);
                return;
            }
            if (tries++ < 80) setTimeout(attempt, 50);
        })();
    }

    applyFramesWhenReady(island.frames || []);
    watchTheme();
    watchTooltips();
    watchInteractions();
    watchResize();
    register();
})();
