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
  if (!pale) fleches(groupe, coords);
  return groupe;
}

// sens de parcours : petits chevrons clairs posés sur le tracé, environ 16 par boucle (300 m au moins entre deux)
function fleches(groupe, coords) {
  const rad = Math.PI / 180, R = 6371000;
  const seg = (a, b) => { const x = (b[1] - a[1]) * rad * Math.cos((a[0] + b[0]) / 2 * rad), y = (b[0] - a[0]) * rad;
    return [Math.hypot(x, y) * R, Math.atan2(x, y) / rad]; };
  let total = 0;
  for (let i = 1; i < coords.length; i++) total += seg(coords[i - 1], coords[i])[0];
  const pas = Math.max(300, total / 16);
  let reste = pas / 2;
  for (let i = 1; i < coords.length; i++) {
    const a = coords[i - 1], b = coords[i], [d, cap] = seg(a, b);
    while (d && reste <= d) {
      const k = reste / d;
      L.marker([a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k], { interactive: false, keyboard: false,
        icon: L.divIcon({ className: "fleche", iconSize: [16, 16],
          html: `<svg viewBox="0 0 16 16" aria-hidden="true" style="transform:rotate(${cap.toFixed(0)}deg)"><path d="M4 10.5 8 6.5l4 4"/><path d="M4 10.5 8 6.5l4 4"/></svg>` }) }).addTo(groupe);
      reste += pas;
    }
    reste -= d;
  }
}

export function depart(m, p) {  // le point du logo : pêche cerclé d'encre
  return L.circleMarker(p, { radius: 9, color: "#22322B", weight: 3, fillColor: "#F4BFA3", fillOpacity: 1 }).addTo(m);
}

export function cadrer(m, coords) {
  if (coords.length > 1) m.fitBounds(L.latLngBounds(coords), { padding: [28, 28] });
}
