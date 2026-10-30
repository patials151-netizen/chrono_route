/**
 * ChronoRoute - Leaflet Map & Tactical Visualization Controller
 * Renders metropolitan road networks, animated emergency vehicles,
 * DSRC radar preemption radius, and dynamic traffic signal state indicators.
 */

class ChronoMap {
  constructor(containerId) {
    this.containerId = containerId;
    this.map = null;
    this.roadLayers = [];
    this.signalMarkers = {};
    this.facilityMarkers = [];
    this.evpRoutePolyline = null;
    this.stdRoutePolyline = null;
    this.vehicleMarker = null;
    this.preemptionRadarCircle = null;
    this.heatLayerGroup = null;
    this.showsHeatmap = false;
  }

  init(centerLat = 40.7150, centerLng = -74.0050, zoom = 14) {
    if (this.map) return;

    this.map = L.map(this.containerId, {
      center: [centerLat, centerLng],
      zoom: zoom,
      zoomControl: false,
      attributionControl: false
    });

    // Add zoom control at bottom-right
    L.control.zoom({ position: 'bottomright' }).addTo(this.map);

    // Dark-themed tiles (CartoDB Dark Matter or OSM with CSS dark filter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd',
      fallback: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    }).addTo(this.map);

    this.heatLayerGroup = L.layerGroup().addTo(this.map);
  }

  // Render Network Roads and Geometry
  renderNetwork(geojsonData) {
    // Clear previous
    this.roadLayers.forEach(l => this.map.removeLayer(l));
    this.roadLayers = [];

    // LineStrings (Roads)
    geojsonData.features.forEach(feat => {
      if (feat.geometry.type === 'LineString') {
        const coords = feat.geometry.coordinates.map(c => [c[1], c[0]]);
        const props = feat.properties;

        // Determine road color and weight
        let color = '#334155';
        let weight = 3;
        let opacity = 0.6;

        if (props.road_class === 'EXPRESSWAY') {
          color = '#38bdf8';
          weight = 5;
          opacity = 0.85;
        } else if (props.road_class === 'ARTERIAL_BOULEVARD') {
          color = '#64748b';
          weight = 4;
          opacity = 0.75;
        } else if (props.road_class === 'HISTORIC_NARROW') {
          color = '#f59e0b';
          weight = 2.5;
        } else if (props.road_class === 'RIVER_CROSSING') {
          color = '#a855f7';
          weight = 4;
        }

        if (props.blocked) {
          color = '#ef4444';
          weight = 6;
          opacity = 1.0;
        }

        const poly = L.polyline(coords, {
          color: color,
          weight: weight,
          opacity: opacity
        }).addTo(this.map);

        // Tooltip
        const tipText = `
          <strong>${props.name}</strong><br>
          Class: ${props.road_class}<br>
          Width: ${props.width_m}m | Lanes: ${props.lanes}<br>
          Congestion: ${Math.round(props.congestion * 100)}% | Speed: ${props.speed_limit_kmh} km/h
          ${props.blocked ? '<br><span style="color:#ef4444;font-weight:bold;">⚠️ ROAD IMPASSE / COLLISION</span>' : ''}
        `;
        poly.bindTooltip(tipText, { sticky: true, className: 'tactical-map-tooltip' });
        this.roadLayers.push(poly);
      }
    });
  }

  // Render Facilities (Hospitals, Fire Stations, EMS Depots)
  renderFacilities(facilities) {
    this.facilityMarkers.forEach(m => this.map.removeLayer(m));
    this.facilityMarkers = [];

    // Hospitals
    (facilities.hospitals || []).forEach(h => {
      const icon = L.divIcon({
        className: 'custom-facility-pin',
        html: `<div class="facility-marker HOSPITAL" title="${h.name}">🏥</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });
      const marker = L.marker([h.lat, h.lng], { icon: icon }).addTo(this.map);
      marker.bindPopup(`<strong>${h.name}</strong><br>Type: Level-1 Trauma Hospital<br>Capacity: ${h.capacity} Critical Beds`);
      this.facilityMarkers.push(marker);
    });

    // Fire Stations
    (facilities.fire_stations || []).forEach(f => {
      const icon = L.divIcon({
        className: 'custom-facility-pin',
        html: `<div class="facility-marker FIRE_STATION" title="${f.name}">🚒</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });
      const marker = L.marker([f.lat, f.lng], { icon: icon }).addTo(this.map);
      marker.bindPopup(`<strong>${f.name}</strong><br>Vehicles: ${f.vehicles.join(', ')}`);
      this.facilityMarkers.push(marker);
    });

    // EMS Depots
    (facilities.ems_depots || []).forEach(e => {
      const icon = L.divIcon({
        className: 'custom-facility-pin',
        html: `<div class="facility-marker EMS_DEPOT" title="${e.name}">🚑</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });
      const marker = L.marker([e.lat, e.lng], { icon: icon }).addTo(this.map);
      marker.bindPopup(`<strong>${e.name}</strong><br>Squads: ${e.vehicles.join(', ')}`);
      this.facilityMarkers.push(marker);
    });
  }

  // Render/Update Traffic Signals
  updateSignals(signalsData, nodesData) {
    Object.keys(signalsData).forEach(nodeId => {
      const sig = signalsData[nodeId];
      const node = nodesData[nodeId];
      if (!node) return;

      const stateClass = sig.preempted ? 'PREEMPTED_GREEN' : sig.state;
      const queueDisplay = Math.round(sig.queue_count);
      const iconHtml = `
        <div class="signal-marker-badge ${stateClass}" id="sig-${nodeId}">
          ${sig.preempted ? '⚡' : (stateClass === 'RED' ? queueDisplay : '●')}
        </div>
      `;

      if (this.signalMarkers[nodeId]) {
        // Update existing marker icon
        const icon = L.divIcon({
          className: 'custom-signal-pin',
          html: iconHtml,
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        });
        this.signalMarkers[nodeId].setIcon(icon);
      } else {
        const icon = L.divIcon({
          className: 'custom-signal-pin',
          html: iconHtml,
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        });
        const marker = L.marker([node.lat, node.lng], { icon: icon }).addTo(this.map);
        marker.bindTooltip(`Signal ${nodeId}<br>State: ${stateClass}<br>Queued Cars: ${queueDisplay}`);
        this.signalMarkers[nodeId] = marker;
      }
    });
  }

  // Draw ChronoRoute EVP Path & Standard Civilian Path
  renderRoutes(chronoCoords, stdCoords) {
    if (this.evpRoutePolyline) this.map.removeLayer(this.evpRoutePolyline);
    if (this.stdRoutePolyline) this.map.removeLayer(this.stdRoutePolyline);

    // Standard GPS Polyline (Dashed Amber/Orange)
    if (stdCoords && stdCoords.length > 1) {
      this.stdRoutePolyline = L.polyline(stdCoords, {
        color: '#f59e0b',
        weight: 4,
        opacity: 0.75,
        dashArray: '8, 8'
      }).addTo(this.map);
    }

    // ChronoRoute EVP Polyline (Glowing Solid Cyan)
    if (chronoCoords && chronoCoords.length > 1) {
      this.evpRoutePolyline = L.polyline(chronoCoords, {
        color: '#00f3ff',
        weight: 6,
        opacity: 0.95
      }).addTo(this.map);
    }
  }

  // Update Moving Emergency Vehicle Marker & Radar Lookahead Circle
  updateVehiclePosition(lat, lng, heading = 0, vehicleType = 'AMBULANCE', radarRadiusM = 350) {
    const isFire = vehicleType.includes('FIRE');
    const symbol = isFire ? '🚒' : '🚑';

    const vehicleHtml = `
      <div class="vehicle-marker-icon" style="transform: rotate(${heading}deg); font-size: 26px; text-shadow: 0 0 12px ${isFire ? '#ef4444' : '#00f3ff'};">
        ${symbol}
      </div>
    `;

    const icon = L.divIcon({
      className: 'vehicle-div-icon',
      html: vehicleHtml,
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });

    if (this.vehicleMarker) {
      this.vehicleMarker.setLatLng([lat, lng]);
      this.vehicleMarker.setIcon(icon);
    } else {
      this.vehicleMarker = L.marker([lat, lng], { icon: icon, zIndexOffset: 1000 }).addTo(this.map);
    }

    // Radar lookahead circle
    if (this.preemptionRadarCircle) {
      this.preemptionRadarCircle.setLatLng([lat, lng]);
      this.preemptionRadarCircle.setRadius(radarRadiusM);
    } else {
      this.preemptionRadarCircle = L.circle([lat, lng], {
        radius: radarRadiusM,
        className: 'evp-pulse-cone',
        color: '#00f3ff',
        weight: 1.5,
        fillColor: '#00f3ff',
        fillOpacity: 0.1
      }).addTo(this.map);
    }
  }

  // Toggle Bottleneck Heat Layer
  toggleBottleneckHeat(show, heatRecords) {
    this.showsHeatmap = show;
    this.heatLayerGroup.clearLayers();
    if (!show || !heatRecords) return;

    heatRecords.forEach(rec => {
      const coords = rec.coordinates.map(c => [c[1], c[0]]);
      let color = '#10b981';
      if (rec.risk_score_pct >= 75) color = '#ef4444';
      else if (rec.risk_score_pct >= 45) color = '#f59e0b';

      const poly = L.polyline(coords, {
        color: color,
        weight: 8,
        opacity: 0.55
      }).addTo(this.heatLayerGroup);

      poly.bindTooltip(`⚠️ ${rec.name}<br>Risk: ${rec.risk_score_pct}% (${rec.risk_tier})`);
    });
  }

  toggleEvpPath(visible) {
    if (this.evpRoutePolyline) {
      if (visible) this.map.addLayer(this.evpRoutePolyline);
      else this.map.removeLayer(this.evpRoutePolyline);
    }
  }

  toggleStdPath(visible) {
    if (this.stdRoutePolyline) {
      if (visible) this.map.addLayer(this.stdRoutePolyline);
      else this.map.removeLayer(this.stdRoutePolyline);
    }
  }

  toggleSignals(visible) {
    Object.values(this.signalMarkers).forEach(m => {
      if (visible) this.map.addLayer(m);
      else this.map.removeLayer(m);
    });
  }
}

window.chronoMap = new ChronoMap('chrono-map');
