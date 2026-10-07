// Grey relief base map shared by the mountain maps: Esri gray canvas, hillshade blended in
// (see .tiles-relief-* in map.css) and place names in a "labels" pane below the trails.
import L from 'leaflet'

const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services'

export function reliefLayers(theme) {
  const dark = theme === 'dark'
  const attribution = 'Tiles © Esri — Esri, HERE, Garmin, USGS, © OpenStreetMap contributors'
  return [
    L.tileLayer(`${ESRI}/Canvas/World_${dark ? 'Dark' : 'Light'}_Gray_Base/MapServer/tile/{z}/{y}/{x}`, { maxZoom: 18, maxNativeZoom: 16, attribution }),
    L.tileLayer(`${ESRI}/Elevation/World_Hillshade${dark ? '_Dark' : ''}/MapServer/tile/{z}/{y}/{x}`, { maxZoom: 18, maxNativeZoom: 16, className: dark ? 'tiles-relief-dark' : 'tiles-relief-light' }),
    L.tileLayer(`${ESRI}/Canvas/World_${dark ? 'Dark' : 'Light'}_Gray_Reference/MapServer/tile/{z}/{y}/{x}`, { maxZoom: 18, maxNativeZoom: 16, pane: 'labels' }),
  ]
}

// Pane for base-map place names, kept under the trail lines.
export function addLabelsPane(map) {
  map.createPane('labels')
  map.getPane('labels').style.zIndex = 380
  map.getPane('labels').style.pointerEvents = 'none'
}
