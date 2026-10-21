// Animated publication map (https://jesnyder.github.io/mapClinical/ pattern).
//
// Behavior:
//  - Papers appear when the timeline reaches their publication year and then
//    STAY (cumulative) -- markers carry a far-future end date.
//  - Each marker GROWS from tiny at its publication year to its full size
//    (proportional to sqrt(citations)) by the present day.
//  - Larger markers sit BEHIND smaller ones (bucketed panes from
//    write_geojson.py) so every circle remains visible.
//  - A play/pause timeline slider runs from the earliest paper year to the
//    PRESENT year (never beyond), plus a second control with From/To year
//    sliders to restrict the animation to a specific range.
//
// Data: `pubs_timeline` GeoJSON written by user_provided/python/write_geojson.py.
// Requires: Leaflet + vendor/leaflet.timeline.js.

(function () {
  // Base maps (see docs/js/mapConfig.js for the API key):
  //  - Default: CARTO Positron WITHOUT labels ("light_nolabels") -- minimal,
  //    no place-name text on the map.
  //  - Satellite: ESRI World Imagery -- no labels or country lines at all.
  //  - If a Mapbox token is set in mapConfig.js, a "Mapbox" base layer is
  //    added; point cfg.mapboxStyle at a custom Studio style (e.g. one with
  //    border/label layers removed) to get a label-free Mapbox basemap too.
  // The layer control (top right) lets you switch between them.
  var cfg = window.MAP_CONFIG || {};

  var attribution =
    ' | Publication Data from <a href="https://www.crossref.org/" target="_blank" rel="noopener">Crossref</a>';

  var lightNoLabels = L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
    {
      subdomains: "abcd",
      maxZoom: 19,
      attribution:
        '&copy; <a href="http://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO' + attribution,
    }
  );

  var satellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 18,
      attribution:
        "Imagery &copy; Esri &mdash; Maxar, Earthstar Geographics" + attribution,
    }
  );

  var baseLayers = {
    "Light (no labels)": lightNoLabels,
    "Satellite": satellite,
  };
  var defaultBase = lightNoLabels;

  if (cfg.mapboxToken) {
    baseLayers["Mapbox"] = L.tileLayer(
      "https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=" +
        cfg.mapboxToken,
      {
        id: cfg.mapboxStyle || "mapbox/light-v11",
        tileSize: 512,
        zoomOffset: -1,
        maxZoom: 18,
        attribution:
          '&copy; <a href="https://www.mapbox.com/about/maps" target="_blank" rel="noopener">Mapbox</a> &copy; <a href="http://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap' + attribution,
      }
    );
    defaultBase = baseLayers["Mapbox"];
  }

  var map = L.map("map", {
    center: [20, 0],
    zoom: 2,
    minZoom: 2,
    maxZoom: 18,
    zoomSnap: 0.25,
    layers: [defaultBase],
  });

  L.control.layers(baseLayers, null, { position: "topright" }).addTo(map);

  // ---- time bounds -------------------------------------------------------
  var years = [];
  pubs_timeline.features.forEach(function (f) {
    if (f.properties.year) years.push(f.properties.year);
  });
  var MIN_YEAR = Math.min.apply(null, years);
  var NOW = Date.now();                       // markers reach full size "today"
  var PRESENT_YEAR = new Date(NOW).getFullYear(); // the timeline never exceeds this

  var range = { from: MIN_YEAR, to: PRESENT_YEAR }; // adjustable via range control

  // ---- marker rendering --------------------------------------------------
  function onEachPaper(feature, layer) {
    var p = feature.properties;
    layer.bindPopup(
      "<p><b>" + (p.title || "") + "</b><br>" +
      (p.aff || "") +
      "<br> Published: " + (p.year || "?") +
      "<br> Citations: " + (p.cites || 0) +
      '<br><a href="' + (p.url || "") + '" target="_blank" rel="noopener">' +
      (p.url || "") + "</a></p>"
    );
  }

  // Fraction grown: 0 at the paper's publication year, 1 at the present day,
  // evaluated at the CURRENT timeline time (so markers grow as it plays).
  function growth(p, timeMs) {
    var start = Date.UTC(p.year, 0, 1);
    var span = NOW - start;
    if (span <= 0) return 1;
    var frac = (timeMs - start) / span;
    return Math.max(0, Math.min(1, frac));
  }

  function markerRadius(p, timeMs) {
    // Floor of 10 px keeps every marker visible; growth scales from that
    // floor up to the full size p.radius (10 + sqrt(citations)) by today.
    var full = Math.max(10, p.radius || 10);
    return 10 + (full - 10) * growth(p, timeMs);
  }

  function paperToLayer(feature, latlng) {
    var p = feature.properties;
    // Bigger markers get LOWER z-index panes: drawn first, underneath smaller ones.
    if (p.paneName && !map.getPane(p.paneName)) {
      map.createPane(p.paneName);
      map.getPane(p.paneName).style.zIndex = p.zindex;
    }
    return L.circleMarker(latlng, {
      radius: markerRadius(p, timeline ? timeline.time : NOW),
      opacity: p.opacity,
      fillOpacity: p.opacity,
      fillColor: p.color,
      color: "black",
      weight: 1,
      pane: p.paneName,
    });
  }

  // ---- timeline (rebuilt when the range changes) --------------------------
  var timeline = null;
  var slider = null;
  var lastShownYear = null;

  function refreshRadii() {
    // Resize every displayed marker for the current timeline time. Throttled
    // to once per displayed year (see change handler) to keep playback smooth.
    var t = timeline.time;
    timeline.eachLayer(function (layer) {
      var p = layer.feature && layer.feature.properties;
      if (p) layer.setStyle({ radius: markerRadius(p, t) });
    });
  }

  function buildTimeline(autoPlay) {
    if (slider) map.removeControl(slider);
    if (timeline) map.removeLayer(timeline);

    var startMs = Date.UTC(range.from, 0, 1);
    // Cap at the present: end of the current year at latest, or the range end.
    var endMs = Date.UTC(Math.min(range.to, PRESENT_YEAR), 11, 31, 23, 59, 59);

    timeline = L.timeline(pubs_timeline, {
      start: startMs,
      end: endMs,
      onEachFeature: onEachPaper,
      pointToLayer: paperToLayer,
    }).addTo(map);

    timeline.on("change", function () {
      var year = new Date(timeline.time).getFullYear();
      if (year !== lastShownYear) {
        lastShownYear = year;
        refreshRadii();
      }
    });

    slider = L.timelineSliderControl({
      start: startMs,
      end: endMs,
      formatOutput: function (date) {
        return String(new Date(date).getFullYear());
      },
      duration: 20000,
      autoPlay: autoPlay,
      enableKeyboardControls: true,
    });
    map.addControl(slider);
    slider.addTimelines(timeline);
    lastShownYear = null;
    refreshRadii();
  }

  buildTimeline(true); // start animating on page load

  // ---- second slider: From/To year range control --------------------------
  var RangeControl = L.Control.extend({
    options: { position: "bottomright" },
    onAdd: function () {
      var div = L.DomUtil.create("div", "leaflet-bar");
      div.style.padding = "6px 10px";
      div.style.background = "white";
      div.style.fontFamily = "Calibri, sans-serif";
      div.style.fontSize = "13px";
      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);

      function makeYearSlider(label, value) {
        var wrap = document.createElement("label");
        var out = document.createElement("b");
        out.textContent = value;
        var input = document.createElement("input");
        input.type = "range";
        input.min = MIN_YEAR;
        input.max = PRESENT_YEAR;
        input.value = value;
        input.style.width = "160px";
        wrap.appendChild(document.createTextNode(label + " "));
        wrap.appendChild(out);
        wrap.appendChild(document.createElement("br"));
        wrap.appendChild(input);
        div.appendChild(wrap);
        div.appendChild(document.createElement("br"));
        return { input: input, out: out };
      }

      var fromS = makeYearSlider("From year", range.from);
      var toS = makeYearSlider("To year", range.to);

      function applyRange() {
        var f = parseInt(fromS.input.value, 10);
        var t = parseInt(toS.input.value, 10);
        if (f > t) { // keep the range valid: the edited slider snaps to the other
          if (this === fromS.input) { t = f; toS.input.value = t; }
          else { f = t; fromS.input.value = f; }
        }
        range.from = f;
        range.to = t;
        fromS.out.textContent = f;
        toS.out.textContent = t;
        buildTimeline(false); // rebuild for the new range, no auto-replay
      }

      fromS.input.addEventListener("change", applyRange);
      toS.input.addEventListener("change", applyRange);
      return div;
    },
  });
  map.addControl(new RangeControl());
})();
