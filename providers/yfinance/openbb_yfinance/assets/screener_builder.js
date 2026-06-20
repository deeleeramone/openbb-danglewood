(function () {
  var J = window.json_data || {};
  var FIELDS = J.fields || {};
  var OPERATORS = J.operators || {};
  var SORT_OPTIONS = J.sortOptions || {};
  var DEFAULT_SORT = J.defaultSort || {};

  var CONFIG_WID = J.configWidgetId || "yfinance_screener_config";
  var RESULTS_WID = J.resultsWidgetId || "yfinance_screener_results";
  var RESULTS_GID = J.resultsGridId || "ob-results-grid";
  var TRANSPORT = J.transport || "iframe";
  var MODAL_ID = J.addFilterModalId || "ob-add-filter";
  var TEMPLATE_SELECT_ID = J.templateSelectId || "ob-template";
  var SAVE_MODAL_ID = J.saveModalId || "ob-save-template";
  var DELETE_MODAL_ID = J.deleteModalId || "ob-delete-template";
  var TEMPLATES = J.templates || [];
  var COLUMN_DEFS_BY_ASSET = J.columnDefsByAsset || {};

  var target = window.top || window.parent;
  var PARAM_DEFS = [
    { paramName: "config", label: "Screener Config", type: "text", value: "" },
  ];
  var MANIFESTS = [
    {
      widgetId: CONFIG_WID,
      name: "Screener Configuration",
      description: "The active screener filter configuration.",
      dataType: "table",
    },
    {
      widgetId: RESULTS_WID,
      name: "Screener Results",
      description: "Yahoo Finance screener results for the current configuration.",
      dataType: "table",
    },
  ];
  var WIDGET_DATA = {};
  MANIFESTS.forEach(function (m) {
    WIDGET_DATA[m.widgetId] = {
      type: "openbb-data",
      widgetId: m.widgetId,
      dataType: "table",
      data: [],
    };
  });

  var STATE = {
    asset: J.defaultAsset || "equity",
    limit: 100,
    sortType: "DESC",
    sortField: DEFAULT_SORT[J.defaultAsset] || "",
    filters: [],
    currentTemplate: null,
  };

  function el(id) {
    return document.getElementById(id);
  }
  function fieldsFor(asset) {
    return FIELDS[asset] || [];
  }
  function normLimit(v) {
    if (v === "" || v === null || v === undefined) return 100;
    var n = Math.floor(Number(v));
    return Number.isFinite(n) && n >= 0 ? n : 100;
  }
  function patchGridCsvExport() {
    // Inside the cross-origin Workspace iframe, AG-Grid's CSV export can't open
    // the file picker (SecurityError) and falls back to emitting a notebook-only
    // 'grid_export_csv' event — which isn't a valid Workspace event and, because
    // the emit "succeeds", suppresses PyWry's own Blob download. Intercept that
    // event and download via a Blob instead. Native PyWry windows (self === top)
    // keep the real file picker untouched.
    if (window.self === window.top || window.__obbGridExportPatched) return;
    if (!window.pywry || typeof window.pywry.emit !== "function") {
      setTimeout(patchGridCsvExport, 50);
      return;
    }
    window.__obbGridExportPatched = true;
    try {
      delete window.showSaveFilePicker;
    } catch (e) {
      /* not deletable on this browser */
    }
    try {
      window.showSaveFilePicker = undefined;
    } catch (e) {
      /* not writable on this browser */
    }
    var origEmit = window.pywry.emit.bind(window.pywry);
    window.pywry.emit = function (type, payload) {
      if (type === "grid_export_csv") {
        try {
          var blob = new Blob([(payload && payload.csvContent) || ""], {
            type: "text/csv;charset=utf-8;",
          });
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url;
          a.download = (payload && payload.fileName) || "export.csv";
          a.style.display = "none";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        } catch (e) {
          /* best effort */
        }
        return;
      }
      return origEmit(type, payload);
    };
  }
  function fieldByName(asset, name) {
    var list = fieldsFor(asset);
    for (var i = 0; i < list.length; i++) {
      if (list[i].field === name) return list[i];
    }
    return null;
  }
  function categoriesFor(asset) {
    var seen = {};
    var out = [];
    fieldsFor(asset).forEach(function (f) {
      if (!seen[f.category]) {
        seen[f.category] = true;
        out.push({ value: f.category, label: f.category_label });
      }
    });
    return out.sort(function (a, b) {
      return a.label.localeCompare(b.label);
    });
  }
  function fieldsInCategory(asset, category) {
    return fieldsFor(asset).filter(function (f) {
      return f.category === category;
    });
  }

  function pushData(id) {
    if (target !== window && WIDGET_DATA[id]) target.postMessage(WIDGET_DATA[id], "*");
  }
  function emitParams(params) {
    if (target !== window)
      target.postMessage({ type: "openbb:widget-params:update", params: params }, "*");
  }
  function applyTheme(t) {
    var dark = t !== "light";
    var h = document.documentElement;
    h.classList.toggle("pywry-theme-dark", dark);
    h.classList.toggle("pywry-theme-light", !dark);
  }
  function extractTheme(d) {
    var r = d && (d.theme || d.colorScheme || (d.params && d.params.theme));
    if (r && typeof r === "object") r = r.value;
    return r === "light" || r === "dark" ? r : null;
  }

  function delegateDropdown(id) {
    // PyWry's setValue rebuilds dropdown options via innerHTML, which drops the
    // per-option click handlers initToolbarHandlers bound at load. Delegate from
    // the (persistent) dropdown element instead, reading the option's data-value,
    // so any rebuilt option works without re-binding. Bound once per dropdown.
    var dropdown = el(id);
    if (
      !dropdown ||
      dropdown.__obbDelegated ||
      !dropdown.classList ||
      !dropdown.classList.contains("pywry-dropdown")
    )
      return;
    dropdown.__obbDelegated = true;
    dropdown.addEventListener("click", function (e) {
      var option = e.target.closest(".pywry-dropdown-option");
      if (!option || !dropdown.contains(option)) return;
      e.stopPropagation();
      var v = option.getAttribute("data-value");
      dropdown.querySelectorAll(".pywry-dropdown-option").forEach(function (o) {
        o.classList.remove("pywry-selected");
      });
      option.classList.add("pywry-selected");
      var textEl = dropdown.querySelector(".pywry-dropdown-text");
      if (textEl) textEl.textContent = option.textContent;
      dropdown.classList.remove("pywry-open");
      var menu = dropdown.querySelector(".pywry-dropdown-menu");
      if (menu) menu.style.cssText = "";
      var eventName = dropdown.getAttribute("data-event");
      if (eventName && window.pywry && window.pywry.emit) {
        window.pywry.emit(eventName, { value: v, componentId: dropdown.id });
      }
    });
  }

  function setSelect(id, value, options) {
    if (window.__PYWRY_TOOLBAR__ && window.__PYWRY_TOOLBAR__.setValue) {
      window.__PYWRY_TOOLBAR__.setValue(id, value, options ? { options: options } : {});
    }
    delegateDropdown(id);
  }

  var MF = { field: null, operator: null };

  function operatorOptionsFor(type) {
    var ops = OPERATORS[type] || OPERATORS.number || [];
    return ops.map(function (o) {
      return { value: o.value, label: o.label };
    });
  }

  function renderValueInput() {
    var wrap = el("ob-mf-value");
    if (!wrap) return;
    var f = MF.field;
    if (!f) {
      wrap.innerHTML = "";
      return;
    }
    var op = MF.operator;
    if (f.type === "number") {
      if (op === "btwn") {
        wrap.innerHTML =
          '<div class="ob-mf-range">' +
          '<label><span>Min</span><input type="number" id="ob-mf-v0" class="ob-mf-input"></label>' +
          '<label><span>Max</span><input type="number" id="ob-mf-v1" class="ob-mf-input"></label>' +
          "</div>";
      } else {
        wrap.innerHTML =
          '<input type="number" id="ob-mf-v0" class="ob-mf-input" placeholder="value">';
      }
      return;
    }
    if (f.type === "enum") {
      var multi = op !== "eq";
      var items = (f.values || [])
        .map(function (v) {
          return (
            '<label class="ob-msi" data-search="' +
            ((v.label || "") + " " + v.value).toLowerCase() +
            '">' +
            '<input type="' +
            (multi ? "checkbox" : "radio") +
            '" name="ob-mf-enum" class="ob-msi-cb" value="' +
            v.value +
            '" data-label="' +
            (v.label || v.value) +
            '">' +
            "<span>" +
            (v.label || v.value) +
            "</span></label>"
          );
        })
        .join("");
      wrap.innerHTML =
        '<input type="text" class="ob-mf-search" placeholder="Search…">' +
        '<div class="ob-msi-list">' +
        items +
        "</div>";
      var search = wrap.querySelector(".ob-mf-search");
      search.addEventListener("input", function () {
        var q = search.value.toLowerCase();
        wrap.querySelectorAll(".ob-msi").forEach(function (it) {
          it.style.display =
            !q || it.getAttribute("data-search").indexOf(q) !== -1 ? "" : "none";
        });
      });
      return;
    }
    wrap.innerHTML =
      '<input type="text" id="ob-mf-v0" class="ob-mf-input" placeholder="value">';
  }

  function readValue(f, op) {
    if (!f) return null;
    var wrap = el("ob-mf-value");
    if (f.type === "number") {
      if (op === "btwn") {
        var mn = el("ob-mf-v0").value.trim();
        var mx = el("ob-mf-v1").value.trim();
        if (mn === "" || mx === "" || isNaN(Number(mn)) || isNaN(Number(mx))) return null;
        return [Number(mn), Number(mx)];
      }
      var raw = el("ob-mf-v0").value.trim();
      if (raw === "" || isNaN(Number(raw))) return null;
      return Number(raw);
    }
    if (f.type === "enum") {
      var checked = Array.prototype.slice
        .call(wrap.querySelectorAll(".ob-msi-cb:checked"))
        .map(function (cb) {
          return cb.value;
        });
      if (!checked.length) return null;
      return op === "eq" ? checked[0] : checked;
    }
    var txt = el("ob-mf-v0").value.trim();
    return txt || null;
  }

  function valueLabel(f, op, value) {
    if (f.type === "enum") {
      var byVal = {};
      (f.values || []).forEach(function (v) {
        byVal[v.value] = v.label || v.value;
      });
      var arr = Array.isArray(value) ? value : [value];
      var labels = arr.map(function (v) {
        return byVal[v] || v;
      });
      return labels.length > 2 ? labels.length + " selected" : labels.join(", ");
    }
    if (op === "btwn" && Array.isArray(value)) return value[0] + " – " + value[1];
    return String(value);
  }

  function opLabel(type, op) {
    var ops = OPERATORS[type] || [];
    for (var i = 0; i < ops.length; i++) {
      if (ops[i].value === op) return ops[i].label;
    }
    return op;
  }

  function resetModal() {
    var cats = categoriesFor(STATE.asset);
    var firstCat = cats[0] ? cats[0].value : "";
    setSelect("ob-mf-category", firstCat, cats);
    var joinSel = el("ob-mf-join-row");
    if (joinSel) joinSel.style.display = STATE.filters.length ? "" : "none";
    selectCategory(firstCat);
  }

  function selectCategory(category) {
    var fields = fieldsInCategory(STATE.asset, category);
    var opts = fields.map(function (f) {
      return { value: f.field, label: f.label };
    });
    var firstField = fields[0] ? fields[0].field : "";
    setSelect("ob-mf-field", firstField, opts);
    selectField(firstField);
  }

  function selectField(name) {
    var f = fieldByName(STATE.asset, name);
    MF.field = f;
    var type = f ? f.type : "number";
    var ops = operatorOptionsFor(type);
    MF.operator = ops[0] ? ops[0].value : "gt";
    setSelect("ob-mf-operator", MF.operator, ops);
    renderValueInput();
  }

  function selectOperator(op) {
    MF.operator = op;
    renderValueInput();
  }

  function tbGet(componentId) {
    // Read a component's current value through the documented toolbar bridge,
    // keyed by componentId (falls back to the selected option's data-value).
    var TB = window.__PYWRY_TOOLBAR__;
    if (TB && TB.getValue) return TB.getValue(componentId);
    var dd = el(componentId);
    var sel = dd && dd.querySelector(".pywry-dropdown-option.pywry-selected");
    return sel ? sel.getAttribute("data-value") : null;
  }

  function addFilter() {
    // One submit handler reads the whole form's state by componentId via the
    // toolbar bridge — no per-field JS state tracking needed.
    var f = fieldByName(STATE.asset, tbGet("ob-mf-field"));
    if (!f) return;
    var op = tbGet("ob-mf-operator") || "gt";
    var value = readValue(f, op);
    if (value === null) return;
    var join = STATE.filters.length ? tbGet("ob-mf-join") || "and" : "and";
    STATE.filters.push({
      field: f.field,
      fieldLabel: f.label,
      category: f.category_label,
      type: f.type,
      operator: op,
      value: value,
      join: join,
    });
    renderChips();
    recount();
    if (window.pywry && window.pywry.emit)
      window.pywry.emit("modal:close:" + MODAL_ID, {});
  }

  function removeFilter(i) {
    STATE.filters.splice(i, 1);
    if (STATE.filters.length) STATE.filters[0].join = "and";
    renderChips();
    recount();
  }

  function renderChips() {
    var bar = el("ob-filterbar");
    if (!bar) return;
    if (!STATE.filters.length) {
      bar.innerHTML =
        '<span class="ob-filter-empty">No filters — showing the US market default. ' +
        'Click “+ Add Filter” to refine.</span>';
      return;
    }
    bar.innerHTML = STATE.filters
      .map(function (flt, i) {
        var join =
          i === 0
            ? ""
            : '<span class="ob-chip-join">' + flt.join.toUpperCase() + "</span>";
        return (
          join +
          '<span class="ob-chip">' +
          '<span class="ob-chip-cat">' +
          flt.category +
          "</span>" +
          '<span class="ob-chip-body">' +
          flt.fieldLabel +
          " " +
          opLabel(flt.type, flt.operator) +
          " " +
          valueLabel(flt, flt.operator, flt.value) +
          "</span>" +
          '<button type="button" class="ob-chip-x" data-i="' +
          i +
          '" aria-label="Remove">×</button>' +
          "</span>"
        );
      })
      .join("");
  }

  function buildConfig() {
    return {
      type: STATE.asset,
      limit: normLimit(STATE.limit),
      sort_field: STATE.sortField || DEFAULT_SORT[STATE.asset] || "",
      sort_type: STATE.sortType || "DESC",
      filters: STATE.filters.map(function (f) {
        return {
          field: f.field,
          operator: f.operator,
          value: f.value,
          join: f.join,
        };
      }),
    };
  }

  function recount() {
    var cfg = buildConfig();
    var n = cfg.filters.length;
    var count = el("ob-count");
    if (count) count.textContent = n + " filter" + (n === 1 ? "" : "s");
    WIDGET_DATA[CONFIG_WID].data = STATE.filters.map(function (f) {
      return {
        join: f.join,
        field: f.field,
        operator: f.operator,
        value: Array.isArray(f.value) ? f.value.join(", ") : String(f.value),
      };
    });
    pushData(CONFIG_WID);
  }

  function setResults(rows) {
    rows = rows || [];
    WIDGET_DATA[RESULTS_WID].data = rows;
    pushData(RESULTS_WID);
    if (!(window.pywry && window.pywry.emit)) return;
    var cols = COLUMN_DEFS_BY_ASSET[STATE.asset];
    if (cols) {
      // grid:update-grid swaps columns + data atomically without restoring the
      // previous column state, so the asset's column order is respected.
      window.pywry.emit("grid:update-grid", {
        columnDefs: cols,
        data: rows,
        gridId: RESULTS_GID,
      });
    } else {
      window.pywry.emit("grid:update-data", { data: rows, gridId: RESULTS_GID });
    }
  }

  function setStatus(text) {
    var s = el("ob-results-status");
    if (s) s.textContent = text;
  }

  function renderResults(rows, isDefault) {
    rows = rows || [];
    setResults(rows);
    var n = rows.length;
    var noun = n + " result" + (n === 1 ? "" : "s");
    setStatus(
      n
        ? isDefault
          ? noun + " · US market default"
          : noun
        : "No results for this configuration"
    );
  }

  function runUrl() {
    var p = window.location.pathname.replace(/\/+$/, "").replace(/\/view$/, "");
    return p + "/run";
  }

  function runScreener(cfg) {
    var isDefault = !cfg.filters.length;
    setStatus("Loading results…");
    if (TRANSPORT === "bridge") {
      if (window.pywry && window.pywry.emit)
        window.pywry.emit("screener:run", {
          config: JSON.stringify(cfg),
          limit: normLimit(cfg.limit),
          isDefault: isDefault,
        });
      return;
    }
    fetch(
      runUrl() +
        "?config=" +
        encodeURIComponent(JSON.stringify(cfg)) +
        "&limit=" +
        normLimit(cfg.limit)
    )
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        if (res && res.error) {
          setStatus("Error: " + res.error);
          setResults([]);
          return;
        }
        renderResults((res && res.rows) || [], isDefault);
      })
      .catch(function () {
        setStatus("Request failed");
      });
  }

  function apply() {
    var cfg = buildConfig();
    emitParams({ config: JSON.stringify(cfg) });
    runScreener(cfg);
  }

  function setAsset(a) {
    STATE.asset = a;
    STATE.filters = [];
    STATE.sortField = DEFAULT_SORT[a] || "";
    setSelect("ob-sort-field", STATE.sortField, SORT_OPTIONS[a] || []);
    renderChips();
    recount();
    runScreener(buildConfig());
  }

  function reset() {
    STATE.filters = [];
    renderChips();
    recount();
    runScreener(buildConfig());
  }

  function tmplUrl(suffix) {
    var p = window.location.pathname.replace(/\/+$/, "").replace(/\/view$/, "");
    return p + "/templates" + (suffix || "");
  }

  function refreshTemplateOptions(list) {
    if (list) TEMPLATES = list;
    var opts = [{ value: "", label: "— Templates —" }].concat(
      TEMPLATES.map(function (t) {
        return { value: t.name, label: t.label };
      })
    );
    setSelect(TEMPLATE_SELECT_ID, STATE.currentTemplate || "", opts);
  }

  function applyConfig(cfg, name) {
    if (!cfg || typeof cfg !== "object") return;
    var asset = cfg.type && FIELDS[cfg.type] ? cfg.type : STATE.asset;
    STATE.asset = asset;
    STATE.limit = normLimit(cfg.limit);
    STATE.sortType = cfg.sort_type === "ASC" ? "ASC" : "DESC";
    STATE.sortField = cfg.sort_field || DEFAULT_SORT[asset] || "";
    STATE.currentTemplate = name || null;
    STATE.filters = (cfg.filters || []).map(function (f, i) {
      var meta = fieldByName(asset, f.field) || {};
      return {
        field: f.field,
        fieldLabel: meta.label || f.field,
        category: meta.category_label || "",
        type: meta.type || "number",
        operator: f.operator,
        value: f.value,
        join:
          i === 0 ? "and" : String(f.join).toLowerCase() === "or" ? "or" : "and",
      };
    });
    setSelect("ob-asset", asset);
    setSelect("ob-sort-field", STATE.sortField, SORT_OPTIONS[asset] || []);
    setSelect("ob-sort-type", STATE.sortType);
    setSelect("ob-limit", STATE.limit);
    refreshTemplateOptions();
    renderChips();
    recount();
    runScreener(buildConfig());
  }

  function templatesRefresh() {
    if (TRANSPORT === "bridge") {
      if (window.pywry && window.pywry.emit)
        window.pywry.emit("screener:templates-list", {});
      return;
    }
    fetch(tmplUrl(""))
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        refreshTemplateOptions((res && res.templates) || []);
      })
      .catch(function () {});
  }

  function templateLoad(name) {
    if (!name) return;
    if (TRANSPORT === "bridge") {
      if (window.pywry && window.pywry.emit)
        window.pywry.emit("screener:template-load", { name: name });
      return;
    }
    fetch(tmplUrl("/load") + "?name=" + encodeURIComponent(name))
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        if (res && res.error) {
          setStatus("Error: " + res.error);
          return;
        }
        applyConfig(res && res.config, name);
      })
      .catch(function () {
        setStatus("Failed to load template");
      });
  }

  function onTemplateSaved(res) {
    var name = res && res.name;
    if (name) STATE.currentTemplate = name;
    if (res && res.templates) refreshTemplateOptions(res.templates);
    else templatesRefresh();
    if (window.pywry && window.pywry.emit)
      window.pywry.emit("modal:close:" + SAVE_MODAL_ID, {});
    setStatus('Saved template "' + (name || "") + '"');
  }

  function templateSave(name) {
    var cfg = buildConfig();
    if (TRANSPORT === "bridge") {
      if (window.pywry && window.pywry.emit)
        window.pywry.emit("screener:template-save", {
          name: name,
          config: JSON.stringify(cfg),
        });
      return;
    }
    fetch(
      tmplUrl("/save") +
        "?name=" +
        encodeURIComponent(name) +
        "&config=" +
        encodeURIComponent(JSON.stringify(cfg)),
      { method: "POST" }
    )
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        if (res && res.error) {
          setStatus("Error: " + res.error);
          return;
        }
        onTemplateSaved(res);
      })
      .catch(function () {
        setStatus("Failed to save template");
      });
  }

  function onTemplateDeleted(res) {
    STATE.currentTemplate = null;
    if (res && res.templates) refreshTemplateOptions(res.templates);
    else templatesRefresh();
    if (window.pywry && window.pywry.emit)
      window.pywry.emit("modal:close:" + DELETE_MODAL_ID, {});
    setStatus("Template deleted");
  }

  function templateDelete(name) {
    if (!name) return;
    if (TRANSPORT === "bridge") {
      if (window.pywry && window.pywry.emit)
        window.pywry.emit("screener:template-delete", { name: name });
      return;
    }
    fetch(tmplUrl("/delete") + "?name=" + encodeURIComponent(name), {
      method: "POST",
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (res) {
        if (res && res.error) {
          setStatus("Error: " + res.error);
          return;
        }
        onTemplateDeleted(res);
      })
      .catch(function () {
        setStatus("Failed to delete template");
      });
  }

  function openSaveModal(prefill) {
    var input = el("ob-save-name");
    if (input) input.value = prefill || "";
    if (window.pywry && window.pywry.emit)
      window.pywry.emit("modal:open:" + SAVE_MODAL_ID, {});
  }

  function on(ev, cb) {
    if (window.pywry && window.pywry.on) window.pywry.on(ev, cb);
  }

  on("screener:asset", function (d) {
    if (d && d.value) setAsset(d.value);
  });
  on("screener:sortfield", function (d) {
    if (d) STATE.sortField = d.value;
  });
  on("screener:sorttype", function (d) {
    if (d) STATE.sortType = d.value;
  });
  on("screener:limit", function (d) {
    if (d) STATE.limit = normLimit(d.value);
  });
  on("screener:open-add-filter", function () {
    resetModal();
    if (window.pywry && window.pywry.emit)
      window.pywry.emit("modal:open:" + MODAL_ID, {});
  });
  on("screener:mf-category", function (d) {
    if (d) selectCategory(d.value);
  });
  on("screener:mf-field", function (d) {
    if (d) selectField(d.value);
  });
  on("screener:mf-operator", function (d) {
    if (d) selectOperator(d.value);
  });
  on("screener:add-filter", addFilter);
  on("screener:apply", apply);
  on("screener:reset", reset);

  on("screener:template-pick", function (d) {
    if (d && d.value) templateLoad(d.value);
  });
  on("screener:template-new", function () {
    STATE.filters = [];
    STATE.currentTemplate = null;
    refreshTemplateOptions();
    renderChips();
    recount();
    runScreener(buildConfig());
  });
  on("screener:template-save", function () {
    if (STATE.currentTemplate) templateSave(STATE.currentTemplate);
    else openSaveModal("");
  });
  on("screener:template-saveas", function () {
    openSaveModal(STATE.currentTemplate || "");
  });
  on("screener:template-do-save", function () {
    var input = el("ob-save-name");
    var name = ((input && input.value) || "").trim();
    if (!name) {
      if (input) input.focus();
      return;
    }
    templateSave(name);
  });
  on("screener:template-delete-click", function () {
    if (!STATE.currentTemplate) {
      setStatus("Select a template to delete");
      return;
    }
    var msg = el("ob-delete-msg");
    if (msg)
      msg.textContent =
        'Delete template "' + STATE.currentTemplate + '"? This cannot be undone.';
    if (window.pywry && window.pywry.emit)
      window.pywry.emit("modal:open:" + DELETE_MODAL_ID, {});
  });
  on("screener:template-do-delete", function () {
    if (STATE.currentTemplate) templateDelete(STATE.currentTemplate);
  });
  on("screener:templates", function (d) {
    if (d && d.templates) refreshTemplateOptions(d.templates);
  });
  on("screener:template-loaded", function (d) {
    if (!d) return;
    if (d.error) {
      setStatus("Error: " + d.error);
      return;
    }
    applyConfig(d.config, d.name);
  });
  on("screener:template-saved", function (d) {
    if (!d) return;
    if (d.error) {
      setStatus("Error: " + d.error);
      return;
    }
    onTemplateSaved(d);
  });
  on("screener:template-deleted", function (d) {
    if (!d) return;
    if (d.error) {
      setStatus("Error: " + d.error);
      return;
    }
    onTemplateDeleted(d);
  });
  on("screener:results", function (d) {
    if (!d) return;
    if (d.error) {
      setStatus("Error: " + d.error);
      setResults([]);
      return;
    }
    renderResults(d.rows || [], d.isDefault);
  });

  document.addEventListener("click", function (e) {
    var x = e.target.closest(".ob-chip-x");
    if (x) removeFilter(Number(x.getAttribute("data-i")));
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target && e.target.id === "ob-save-name") {
      e.preventDefault();
      var name = (e.target.value || "").trim();
      if (name) templateSave(name);
    }
  });

  window.addEventListener("message", function (event) {
    var d = event.data;
    if (!d || typeof d !== "object") return;
    var th = extractTheme(d);
    if (th) applyTheme(th);
    if (d.type === "openbb-request") {
      if (d.widgetId == null) Object.keys(WIDGET_DATA).forEach(pushData);
      else pushData(d.widgetId);
    }
  });

  var params = new URLSearchParams(window.location.search);
  applyTheme(params.get("theme") || J.theme || "dark");
  var initialConfig = null;
  var rawConfig = params.get("config");
  if (rawConfig) {
    try {
      initialConfig = JSON.parse(rawConfig);
    } catch (e) {
      initialConfig = null;
    }
  }
  if (initialConfig && typeof initialConfig === "object" && initialConfig.type)
    applyConfig(initialConfig);
  else setAsset(STATE.asset);
  if (target !== window)
    target.postMessage({ type: "openbb-connect", widgets: MANIFESTS, params: PARAM_DEFS }, "*");
  patchGridCsvExport();
})();
