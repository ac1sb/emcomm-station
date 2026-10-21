// Station map: offline Natural Earth base map with US towns (or, online, street,
// satellite or topographic maps), Maidenhead grid, this station, Winlink
// gateways, stations heard and stations that heard us (PSKReporter).
// Data comes from window.BASEMAP
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
  var offline = L.layerGroup([
    layer(B.countries, { color: "#9C9483", weight: 1, fillColor: "#F2EFE6", fillOpacity: 1 }),
    layer(B.lakes, { color: "#7FA4C2", weight: 0.5, fillColor: "#AAC3D6", fillOpacity: 1 }),
    layer(B.states, { color: "#8C7F6A", weight: 1.2, dashArray: "4 3" })
  ]).addTo(map);
  // Counties and roads are the bulk of the base map and show only from zoom 6, so
  // they come from a second script (basemap-detail.js, next to basemap.js) read the
  // first time they're needed. An older single-file base map carries them itself.
  var counties = null, roads = null, detailLoading = false;
  function detailLayers(d) {
    counties = layer(d.counties, { color: "#C2B9A6", weight: 0.6, fill: false });
    roads = layer(d.roads, function (f) {
      return { color: f.properties.type === "Major Highway" ? "#D98E4A" : "#E0B27A",
               weight: f.properties.type === "Major Highway" ? 1.6 : 1 };
    });
  }
  if (B.counties || B.roads) detailLayers(B);
  function loadDetail() {
    if (detailLoading) return;
    detailLoading = true;
    var tag = document.querySelector('script[src$="basemap.js"]');
    var script = document.createElement("script");
    script.src = tag ? tag.src.replace(/basemap\.js$/, "basemap-detail.js") : "basemap-detail.js";
    script.onload = function () {
      detailLayers(window.BASEMAP_DETAIL || {});
      detail();
    };
    script.onerror = function () { detailLayers({}); };  // not built yet: the map works without
    document.body.appendChild(script);
  }
  var places = L.layerGroup().addTo(map);
  var placeData = B.places ? B.places.features : [];
  // US towns (Census): [lat, lon, name, 1 = town or city, 2 = village or CDP].
  var towns = B.towns || [];
  // Names are kept in one-degree cells, so a pan or zoom looks only at those in view
  // rather than at every town in the country.
  function cells(items, position) {
    var index = {};
    items.forEach(function (item) {
      var p = position(item), key = Math.floor(p[0]) + "," + Math.floor(p[1]);
      (index[key] || (index[key] = [])).push(item);
    });
    return index;
  }
  var placeCells = cells(placeData, function (f) { return [f.geometry.coordinates[1], f.geometry.coordinates[0]]; });
  var townCells = cells(towns, function (t) { return [t[0], t[1]]; });
  function inView(index, b, each) {
    var south = Math.floor(b.getSouth()), north = Math.floor(b.getNorth());
    var west = Math.floor(b.getWest()), east = Math.floor(b.getEast());
    for (var lat = south; lat <= north; lat++) {
      for (var lon = west; lon <= east; lon++) {
        var items = index[lat + "," + lon];
        if (items) items.forEach(each);
      }
    }
  }

  // Counties, roads and smaller towns only once zoomed in, to keep it readable and quick.
  // A name is left off where it would sit on top of one already shown.
  function detail() {
    var z = map.getZoom(), b = map.getBounds(), taken = [];
    var online = base !== "offline";
    if (!online && z >= 6 && !counties) loadDetail();
    if (counties) toggle(counties, !online && z >= 6);
    if (roads) toggle(roads, !online && z >= 6);
    places.clearLayers();
    if (online) return;  // the online maps have their own names
    function label(lat, lon, name, cls) {
      if (!b.contains([lat, lon])) return;
      var p = map.latLngToContainerPoint([lat, lon]);
      for (var i = 0; i < taken.length; i++) {
        if (Math.abs(taken[i].x - p.x) < 8 * Math.max(name.length, taken[i].n) && Math.abs(taken[i].y - p.y) < 18) return;
      }
      taken.push({ x: p.x, y: p.y, n: name.length });
      places.addLayer(L.marker([lat, lon], { interactive: false,
        icon: L.divIcon({ className: cls, html: "· " + esc(name), iconSize: null }) }));
    }
    inView(placeCells, b, function (f) {
      var c = f.geometry.coordinates;
      if (f.properties.scalerank <= z - 2) label(c[1], c[0], f.properties.name, "place-label");
    });
    if (z >= 9) {
      inView(townCells, b, function (t) {
        if (t[3] === 1 || z >= 11) label(t[0], t[1], t[2], t[3] === 1 ? "place-label" : "place-label small");
      });
    }
  }
  function toggle(l, on) {
    if (on && !map.hasLayer(l)) l.addTo(map);
    if (!on && map.hasLayer(l)) map.removeLayer(l);
  }

  // ---- online base maps -------------------------------------------------
  // Esri's free map tiles, used with the internet; the built-in map is always
  // there without it. The choice is remembered.
  var ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/";
  function esri(name, attribution, opts) {
    return L.tileLayer(ESRI + name + "/MapServer/tile/{z}/{y}/{x}",
      L.extend({ maxZoom: 18, maxNativeZoom: 18, attribution: attribution }, opts || {}));
  }
  var ESRI_ATTR = "Tiles &copy; Esri";
  var bases = {
    streets: [esri("World_Street_Map", ESRI_ATTR + " &mdash; Esri, HERE, Garmin, USGS, OpenStreetMap contributors")],
    satellite: [esri("World_Imagery", ESRI_ATTR + " &mdash; Esri, Maxar, Earthstar Geographics"),
                esri("Reference/World_Transportation", "", { opacity: 0.8 }),
                esri("Reference/World_Boundaries_and_Places", "")],
    topo: [esri("World_Topo_Map", ESRI_ATTR + " &mdash; Esri, HERE, Garmin, USGS, NGA")]
  };
  bases.streets.label = "street"; bases.satellite.label = "satellite"; bases.topo.label = "topographic";
  var base = "offline", failed = 0;
  Object.keys(bases).forEach(function (k) {
    bases[k].forEach(function (l) {
      l.on("tileerror", function () {
        if (++failed === 4) warn("The " + bases[k].label + " map needs the internet. Tap Map for the built-in one.");
      });
      l.on("tileload", function () { if (failed) { failed = 0; warn(); } });
    });
  });
  function setBase(name) {
    if (!bases[name]) name = "offline";
    base = name; failed = 0;
    Object.keys(bases).forEach(function (k) {
      bases[k].forEach(function (l) { toggle(l, k === name); });
    });
    toggle(offline, name === "offline");
    // Satellite pictures need the overlays to stand out; the others don't.
    document.body.className = "base-" + name;
    var btns = document.querySelectorAll("#bases button");
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("on", btns[i].dataset.base === name);
    try { localStorage.setItem("emcomm-map-base", name); } catch (e) { /* not kept */ }
    warn();
    detail();
  }
  var BaseControl = L.Control.extend({
    options: { position: "topright" },
    onAdd: function () {
      var div = L.DomUtil.create("div", "leaflet-bar");
      div.id = "bases";
      [["offline", "Map"], ["streets", "Streets"], ["satellite", "Satellite"], ["topo", "Topo"]].forEach(function (b) {
        var btn = L.DomUtil.create("button", "", div);
        btn.textContent = b[1];
        btn.dataset.base = b[0];
        btn.title = b[0] === "offline" ? "Built-in map (no internet needed)" : "Needs the internet";
        L.DomEvent.on(btn, "click", function (e) { L.DomEvent.stop(e); setBase(b[0]); });
      });
      L.DomEvent.disableClickPropagation(div);
      return div;
    }
  });
  new BaseControl().addTo(map);

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
  // ---- aircraft (ADS-B) ---------------------------------------------------
  // emcomm-adsb rewrites ../adsb/aircraft.js every 2 seconds; a page opened from a
  // file can't read files, but it can load a script again.
  var aircraft = L.layerGroup().addTo(map);
  var planes = {};
  var PLANE = "M12 2c.8 0 1.3.7 1.3 1.6V9l7.7 4.6v2l-7.7-2.3v4.5l2.4 1.8V21L12 20l-3.7 1v-1.4l2.4-1.8v-4.5L3 15.6v-2L10.7 9V3.6C10.7 2.7 11.2 2 12 2z";
  function planeIcon(a) {
    var colour = a.emergency ? "#DC2626" : a.alt === "ground" ? "#6B7280" : "#0E7490";
    return L.divIcon({ className: "plane", iconSize: [28, 28], iconAnchor: [14, 14],
      html: '<svg viewBox="0 0 24 24" width="28" height="28" style="transform:rotate(' + (a.track || 0) +
            'deg)"><path d="' + PLANE + '" fill="' + colour + '" stroke="#fff" stroke-width="1.2"/></svg>' +
            '<span class="plane-label">' + esc(a.flight || a.hex.toUpperCase()) + '</span>' });
  }
  function planeText(a) {
    var alt = a.alt === "ground" ? "On the ground" : a.alt != null ? a.alt.toLocaleString() + " ft" : "Altitude unknown";
    return "<b>" + esc(a.flight || "No callsign") + "</b> · " + esc(a.hex.toUpperCase()) + "<br>" + alt +
      (a.speed != null ? " · " + Math.round(a.speed) + " kt" : "") +
      (a.track != null ? " · heading " + Math.round(a.track) + "°" : "") +
      (a.squawk ? "<br>Squawk " + esc(a.squawk) + (a.emergency ? " · <b>" + esc(a.emergency) + "</b>" : "") : "");
  }
  function drawAircraft() {
    var A = window.AIRCRAFT || { state: "none", aircraft: [] };
    var on = document.getElementById("show-aircraft").checked;
    var count = document.getElementById("aircraft-count");
    count.textContent = A.state === "running" ? "(" + A.aircraft.length + ")" : "(no rx)";
    count.title = A.text || "";
    var stale = Date.now() / 1000 - (A.time || 0) > 20;  // the receiver stopped writing
    var keep = {};
    if (on && !stale) {
      A.aircraft.forEach(function (a) {
        keep[a.hex] = true;
        var m = planes[a.hex];
        if (!m) {
          m = planes[a.hex] = L.marker([a.lat, a.lon], { icon: planeIcon(a) }).bindPopup("").addTo(aircraft);
        } else {
          m.setLatLng([a.lat, a.lon]);
          m.setIcon(planeIcon(a));
        }
        m.setPopupContent(planeText(a));
      });
    }
    Object.keys(planes).forEach(function (hex) {
      if (!keep[hex]) { aircraft.removeLayer(planes[hex]); delete planes[hex]; }
    });
  }
  // Load a data script again (its newest copy) and redraw once it's in.
  function reload(id, src, draw) {
    var old = document.getElementById(id);
    var s = document.createElement("script");
    s.id = id;
    s.src = src + "?" + Date.now();
    s.onload = s.onerror = function () { if (old) old.remove(); draw(); };
    document.body.appendChild(s);
  }
  function reloadAircraft() { reload("aircraft-data", "../adsb/aircraft.js", drawAircraft); }
  setInterval(reloadAircraft, 2000);

  // ---- NWS warning areas -------------------------------------------------
  // emcomm-online's alertmap: the station's state and its neighbours, refreshed when
  // online; the last ones stay offline, each until it ends.
  var warnings = L.layerGroup().addTo(map);
  var SEVERITY = { Extreme: "#B91C1C", Severe: "#EA580C", Moderate: "#CA8A04", Minor: "#2563EB" };
  function drawWarnings() {
    warnings.clearLayers();
    var W = window.ALERTMAP || {}, now = Date.now();
    var live = (((W.data || {}).alerts) || []).filter(function (a) { return !a.ends || Date.parse(a.ends) > now; });
    var count = document.getElementById("warnings-count");
    count.textContent = W.updated ? "(" + live.length + ")" : "";
    count.title = W.updated ? "NWS, " + ago(W.updated) + (W.error ? " · " + W.error : "") : (W.error || "Not fetched yet");
    if (!document.getElementById("show-warnings").checked) return;
    live.forEach(function (a) {
      var c = SEVERITY[a.severity] || "#6B7280";
      L.polygon(a.rings, { color: c, weight: 1.5, fillColor: c, fillOpacity: 0.16, renderer: renderer })
        .bindPopup("<b>" + esc(a.event) + "</b><br>" + esc(a.headline || a.area) +
                   (a.ends ? "<br>Until " + esc(new Date(a.ends).toLocaleString()) : "") + "<br>NWS · " + esc(a.severity))
        .addTo(warnings);
    });
  }
  function reloadWarnings() { reload("warnings-data", "../online/alertmap.js", drawWarnings); }
  setInterval(reloadWarnings, 60000);

  // ---- Meshtastic and MeshCore nodes --------------------------------------
  // emcomm-mesh-nodes asks the radios when the map opens; the last list stays.
  var mesh = L.layerGroup().addTo(map);
  var MESH = { meshtastic: ["Meshtastic", "#0F766E"], meshcore: ["MeshCore", "#BE185D"] };
  function drawMesh() {
    mesh.clearLayers();
    if (!document.getElementById("show-mesh").checked) return;
    var M = window.MESHNODES || {};
    Object.keys(MESH).forEach(function (kind) {
      ((M[kind] || {}).nodes || []).forEach(function (n) {
        var label = n.short || n.name || n.id;
        var icon = L.divIcon({ className: "mesh-node", iconSize: [14, 14], iconAnchor: [7, 7],
          html: '<span class="mesh-dot" style="background:' + MESH[kind][1] + '"></span>' +
                '<span class="mesh-label">' + esc(label) + "</span>" });
        L.marker([n.lat, n.lon], { icon: icon })
          .bindPopup("<b>" + esc(n.name || label) + "</b>" + (n.short ? " · " + esc(n.short) : "") + "<br>" +
                     MESH[kind][0] + (n.kind ? " " + esc(n.kind.toLowerCase()) : " node") +
                     (n.me ? " (this station's radio)" : "") +
                     (n.heard ? "<br>Heard " + ago(n.heard) : "") +
                     (n.snr != null ? " · SNR " + n.snr + " dB" : "") +
                     (n.hops != null && n.hops >= 0 ? " · " + n.hops + (n.hops === 1 ? " hop" : " hops") : "") +
                     (n.battery != null ? "<br>Battery " + n.battery + "%" : "") +
                     ((M[kind].time) ? "<br>Asked the radio " + ago(M[kind].time) : ""))
          .addTo(mesh);
      });
    });
  }
  function reloadMesh() { reload("mesh-data", "../mesh/nodes.js", drawMesh); }
  setInterval(reloadMesh, 5000);

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
  document.getElementById("show-grid").addEventListener("change", drawGrid);
  document.getElementById("show-aircraft").addEventListener("change", drawAircraft);
  document.getElementById("show-warnings").addEventListener("change", drawWarnings);
  document.getElementById("show-mesh").addEventListener("change", drawMesh);
  document.getElementById("home").addEventListener("click", function () { map.setView(home, 7); });
  function warn(text) {
    var w = document.getElementById("warning");
    w.textContent = text || "";
    w.style.display = text ? "block" : "none";
  }
  document.getElementById("note").textContent =
    (D.gatewaysUpdated ? "Gateway list " + D.gatewaysUpdated : "No gateway list yet");

  map.on("zoomend moveend", function () { detail(); drawGrid(); });
  var saved = "offline";
  try { saved = localStorage.getItem("emcomm-map-base") || "offline"; } catch (e) { /* first time */ }
  setBase(saved);
  drawGrid(); drawGateways(); drawHeard(); drawHeardMe(); reloadAircraft(); reloadWarnings(); reloadMesh();
})();
