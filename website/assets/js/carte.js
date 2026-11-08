// Cartes Leaflet (tuiles OpenStreetMap, attribution obligatoire) et dessin des boucles aux couleurs de Loopy.
const L = window.L;
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

export function carte(el, centre = [46.6, 2.4], zoom = 5, interactive = true) {
  const m = L.map(el, { zoomControl: interactive, dragging: interactive, scrollWheelZoom: interactive, doubleClickZoom: interactive,
    touchZoom: interactive, keyboard: interactive, attributionControl: true }).setView(centre, zoom);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">contributeurs OpenStreetMap</a>',
  }).addTo(m);
  return m;
}

export function boucle(m, coords, { pale = false, epaisseur = 5 } = {}) {
  const groupe = L.layerGroup().addTo(m);
  L.polyline(coords, { color: css("--fond"), weight: epaisseur + 4, opacity: pale ? 0 : .9 }).addTo(groupe);
  L.polyline(coords, { color: pale ? css("--trace-pale") : css("--trace"), weight: epaisseur, opacity: pale ? .9 : 1 }).addTo(groupe);
  return groupe;
}

export function depart(m, p) {  // le point du logo : pêche cerclé d'encre
  return L.circleMarker(p, { radius: 9, color: "#22322B", weight: 3, fillColor: "#F4BFA3", fillOpacity: 1 }).addTo(m);
}

export function cadrer(m, coords) {
  if (coords.length > 1) m.fitBounds(L.latLngBounds(coords), { padding: [28, 28] });
}
