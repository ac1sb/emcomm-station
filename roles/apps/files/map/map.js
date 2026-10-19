// Station map: offline Natural Earth base map, Maidenhead grid, this station,
// Winlink gateways, stations heard, stations that heard us (PSKReporter) and
// repeaters (RepeaterBook). Data comes from window.BASEMAP
// (emcomm-map-prepare) and window.MAPDATA (emcomm-map).
(function () {
  "use strict";
  var B = window.BASEMAP || {}, D = window.MAPDATA || {}, S = D.station || {};
  var home = (S.lat != null) ? [S.lat, S.lon] : [39, -98];
  var map = L.map("map", { preferCanvas: true, zoomSnap: 0.5, worldCopyJump: true })
    .setView(home, S.lat != null ? 7 : 4);
  var renderer = L.canvas({ padding: 0.3 });

  // ---- base map -------------------------------------------------------
  function layer(data, style) {
    return L.geoJSON(data || { type: "FeatureCollection", features: [] },
      { style: style, renderer: renderer, interactive: false });
  }
  L.layerGroup([
    layer(B.countries, { color: "#9C9483", weight: 1, fillColor: "#F2EFE6", fillOpacity: 1 }),
    layer(B.lakes, { color: "#7FA4C2", weight: 0.5, fillColor: "#AAC3D6", fillOpacity: 1 }),
    layer(B.states, { color: "#8C7F6A", weight: 1.2, dashArray: "4 3" })
  ]).addTo(map);
  var counties = layer(B.counties, { color: "#C2B9A6", weight: 0.6, fill: false });
  var roads = layer(B.roads, function (f) {
    return { color: f.properties.type === "Major Highway" ? "#D98E4A" : "#E0B27A",
             weight: f.properties.type === "Major Highway" ? 1.6 : 1 };
  });
  var places = L.layerGroup().addTo(map);
  var placeData = B.places ? B.places.features : [];

  // Counties, roads and smaller towns only once zoomed in, to keep it readable and quick.
  function detail() {
    var z = map.getZoom(), b = map.getBounds();
    toggle(counties, z >= 6);
    toggle(roads, z >= 6);
    places.clearLayers();
    placeData.forEach(function (f) {
      var c = f.geometry.coordinates;
      if (f.properties.scalerank > z - 2 || !b.contains([c[1], c[0]])) return;
      places.addLayer(L.marker([c[1], c[0]], { interactive: false,
        icon: L.divIcon({ className: "place-label", html: "· " + esc(f.properties.name), iconSize: null }) }));
    });
  }
  function toggle(l, on) {
    if (on && !map.hasLayer(l)) l.addTo(map);
    if (!on && map.hasLayer(l)) map.removeLayer(l);
  }

  // ---- Maidenhead grid ------------------------------------------------
  var grid = L.layerGroup().addTo(map);
  function drawGrid() {
    grid.clearLayers();
    if (!document.getElementById("show-grid").checked) return;
    var z = map.getZoom(), b = map.getBounds().pad(0.1);
    var fields = z < 5, dLon = fields ? 20 : 2, dLat = fields ? 10 : 1;
    var west = Math.max(-180, Math.floor(b.getWest() / dLon) * dLon), east = Math.min(180, b.getEast());
    var south = Math.max(-90, Math.floor(b.getSouth() / dLat) * dLat), north = Math.min(90, b.getNorth());
    var style = { color: "#B07A20", weight: fields ? 1.2 : 0.9, opacity: 0.7, interactive: false, renderer: renderer };
    for (var x = west; x <= east; x += dLon) grid.addLayer(L.polyline([[south, x], [north, x]], style));
    for (var y = south; y <= north; y += dLat) grid.addLayer(L.polyline([[y, west], [y, east]], style));
    if (z < 3) return;
    for (x = west; x < east; x += dLon) {
      for (y = south; y < north; y += dLat) {
        var name = locator(y + dLat / 2, x + dLon / 2, fields ? 2 : 4);
        grid.addLayer(L.marker([y + dLat * 0.85, x + dLon * 0.08],
          { icon: L.divIcon({ className: "grid-label", html: name, iconSize: null }), interactive: false }));
      }
    }
  }
  function locator(lat, lon, len) {
    lon += 180; lat += 90;
    var s = String.fromCharCode(65 + Math.floor(lon / 20), 65 + Math.floor(lat / 10));
    if (len >= 4) s += Math.floor((lon % 20) / 2) + "" + Math.floor(lat % 10);
    return s;
  }

  // ---- station, gateways, heard ---------------------------------------
  if (S.lat != null) {
    L.circleMarker(home, { radius: 9, color: "#101214", weight: 2, fillColor: "#F2A33A", fillOpacity: 1 })
      .bindPopup("<b>" + esc(S.call) + "</b><br>This station · " + esc(S.grid)).addTo(map);
  }
  var gateways = L.layerGroup().addTo(map);
  function isHF(ch) { return ch.dial < 30000000; }
  function drawGateways() {
    gateways.clearLayers();
    if (!document.getElementById("show-gateways").checked) return;
    var want = document.getElementById("gateway-filter").value;
    // HF gateways are fewer, so they're drawn last, on top.
    (D.gateways || []).slice().sort(function (a, b) {
      return a.channels.some(isHF) - b.channels.some(isHF);
    }).forEach(function (g) {
      var chans = g.channels.filter(function (c) { return want === "all" || (want === "hf") === isHF(c); });
      if (!chans.length) return;
      var hf = chans.some(isHF);
      var rows = chans.map(function (c) {
        return "<tr><td>" + (c.dial / 1e6).toFixed(4) + "</td><td>" + esc(c.modes) + "</td><td>" + esc(c.hours) + "</td></tr>";
      }).join("");
      L.circleMarker([g.lat, g.lon], { radius: 6, weight: 1.5, color: "#FFFFFF",
                                       fillColor: hf ? "#2E6FD8" : "#2E9D5A", fillOpacity: 0.95 })
        .bindPopup("<b>" + esc(g.call) + "</b> · Winlink gateway<table>" +
                   "<tr><td>MHz (dial)</td><td>Mode</td><td>Hours UTC</td></tr>" + rows + "</table>")
        .addTo(gateways);
    });
  }
  var heard = L.layerGroup().addTo(map);
  function drawHeard() {
    heard.clearLayers();
    if (!document.getElementById("show-heard").checked) return;
    (D.heard || []).forEach(function (h) {
      L.circleMarker([h.lat, h.lon], { radius: 6, weight: 1.5, color: "#FFFFFF", fillColor: "#C2410C", fillOpacity: 0.95 })
        .bindPopup("<b>" + esc(h.call) + "</b> · " + esc(h.grid) + "<br>Heard on " + esc(h.via) +
                   "<br>" + esc(h.when))
        .addTo(heard);
    });
  }
  var heardMe = L.layerGroup().addTo(map);
  function drawHeardMe() {
    heardMe.clearLayers();
    if (!document.getElementById("show-heard-me").checked) return;
    (D.heardMe || []).forEach(function (h) {
      if (S.lat != null) {
        L.polyline([home, [h.lat, h.lon]], { color: "#7C3AED", weight: 1.2, opacity: 0.6, interactive: false,
                                              renderer: renderer }).addTo(heardMe);
      }
      L.circleMarker([h.lat, h.lon], { radius: 6, weight: 1.5, color: "#FFFFFF", fillColor: "#7C3AED", fillOpacity: 0.95 })
        .bindPopup("<b>" + esc(h.call) + "</b> · " + esc(h.grid) + "<br>Heard you on " +
                   (h.freq ? (h.freq / 1e6).toFixed(3) + " MHz " : "") + esc(h.mode) +
                   (h.snr != null ? ", SNR " + h.snr + " dB" : "") + "<br>" + ago(h.time) + " · PSKReporter")
        .addTo(heardMe);
    });
  }
  var repeaters = L.layerGroup().addTo(map);
  function drawRepeaters() {
    repeaters.clearLayers();
    if (!document.getElementById("show-repeaters").checked) return;
    (D.repeaters || []).forEach(function (r) {
      var shift = r.input ? Math.round((r.input - r.freq) * 1000) / 1000 : null;
      L.circleMarker([r.lat, r.lon], { radius: 5, weight: 1.5, color: "#FFFFFF", fillColor: "#0E7490", fillOpacity: 0.95 })
        .bindPopup("<b>" + esc(r.call) + "</b> · " + esc(r.city) + "<br>" + r.freq.toFixed(3) + " MHz" +
                   (shift ? " (" + (shift > 0 ? "+" : "") + shift + ")" : "") +
                   (r.tone ? " · tone " + esc(r.tone) : "") + "<br>" +
                   esc((r.modes || []).concat(r.nets || []).join(", ")) + "<br>RepeaterBook")
        .addTo(repeaters);
    });
  }
  function ago(t) {
    if (!t) return "";
    var m = Math.round((Date.now() / 1000 - t) / 60);
    return m < 60 ? m + " min ago" : Math.round(m / 60) + " h ago";
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // ---- panel -----------------------------------------------------------
  ["show-gateways", "gateway-filter"].forEach(function (id) {
    document.getElementById(id).addEventListener("change", drawGateways);
  });
  document.getElementById("show-heard").addEventListener("change", drawHeard);
  document.getElementById("show-heard-me").addEventListener("change", drawHeardMe);
  document.getElementById("show-repeaters").addEventListener("change", drawRepeaters);
  document.getElementById("show-grid").addEventListener("change", drawGrid);
  document.getElementById("home").addEventListener("click", function () { map.setView(home, 7); });
  document.getElementById("note").textContent =
    (D.gatewaysUpdated ? "Gateway list " + D.gatewaysUpdated : "No gateway list yet");

  map.on("zoomend moveend", function () { detail(); drawGrid(); });
  detail(); drawGrid(); drawRepeaters(); drawGateways(); drawHeard(); drawHeardMe();
})();
