// Petit aperçu SVG d'un tracé (sans fond de carte), pour les listes.
import { ICONES, SPORTS, km, duree, rythme, date, echapper } from "/assets/js/commun.js";

export function apercu(coords) {
  if (!coords || coords.length < 2) return `<p class="doux petit" style="padding:16px">Tracé non partagé</p>`;
  const k = Math.cos(coords[0][0] * Math.PI / 180), pts = coords.map(([a, b]) => [b * k, -a]);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]), x0 = Math.min(...xs), y0 = Math.min(...ys);
  const t = Math.max(Math.max(...xs) - x0, Math.max(...ys) - y0) || 1;
  const dx = (t - (Math.max(...xs) - x0)) / 2, dy = (t - (Math.max(...ys) - y0)) / 2;
  return `<svg viewBox="0 0 100 100" aria-hidden="true"><path fill="none" stroke="var(--trace)" stroke-width="2.5" stroke-linejoin="round" vector-effect="non-scaling-stroke"
    d="M${pts.map(([x, y]) => `${((x - x0 + dx) / t * 100).toFixed(1)} ${((y - y0 + dy) / t * 100).toFixed(1)}`).join("L")}"/></svg>`;
}
export const avatar = (x) => x.avatar ? `<img class="avatar" src="${x.avatar}" alt="">` : `<span class="avatar" aria-hidden="true">${echapper(x.nom[0].toUpperCase())}</span>`;

export function tuileActivite(a) {
  return `<article class="tuile"><a href="/activite.html?id=${a.id}" aria-label="${echapper(a.nom)}"><div class="apercu">${apercu(a.trace)}</div></a>
    <h3><a href="/activite.html?id=${a.id}">${echapper(a.nom)}</a></h3>
    <div class="chiffres"><a href="/u.html?nom=${encodeURIComponent(a.auteur)}">${echapper(a.auteur)}</a><span>${SPORTS[a.sport].nom}</span><span>${date(a.debut)}</span></div>
    <div class="chiffres"><strong>${km(a.distance, 2)} km</strong><span>${duree(a.duree)}</span><span>${rythme(a)}</span><span class="doux">${a.jaimes} j'aime</span></div></article>`;
}
export function tuileItineraire(i) {
  return `<article class="tuile"><div class="apercu">${apercu(i.trace)}</div><h3>${echapper(i.nom)}</h3>
    <div class="chiffres"><a href="/u.html?nom=${encodeURIComponent(i.auteur)}">${echapper(i.auteur)}</a><span>${SPORTS[i.sport].nom}</span>
      <strong>${km(i.distance)} km</strong><span>${i.montee != null ? Math.round(i.montee) + " m D+" : ""}</span></div></article>`;
}
