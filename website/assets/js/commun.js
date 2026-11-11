// Code partagé par toutes les pages : appels à l'API (même compte que l'app), formats, en-tête, GPX.
export const SPORTS = {
  course: { nom: "Course à pied", court: "course", suggestions: [5, 10, 15, 20], mini: 1, maxi: 100, defaut: 10 },
  velo: { nom: "Vélo", court: "vélo", suggestions: [20, 30, 50, 75, 100], mini: 3, maxi: 300, defaut: 30 },
};
export const mouvementReduit = matchMedia("(prefers-reduced-motion: reduce)").matches;

export async function api(chemin, { methode = "GET", corps, fichier } = {}) {
  const opts = { method: methode, credentials: "same-origin", headers: { "X-Loopy": "1" } };
  if (fichier) opts.body = fichier;
  else if (corps !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(corps); }
  let rep;
  try { rep = await fetch(chemin, opts); } catch { throw new Error("Pas de connexion au serveur Loopy"); }
  if (rep.status === 204) return null;
  const texte = await rep.text();
  let data = null;
  try { data = texte ? JSON.parse(texte) : null; } catch { /* réponse non JSON */ }
  if (!rep.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map((e) => (e.msg || "").replace(/^Value error, /, "")).join(" ; ");
    const err = new Error(msg || `Erreur ${rep.status}`);
    err.status = rep.status;
    throw err;
  }
  return data;
}

let _moi;
export function moi() {  // l'utilisateur connecté, ou null
  if (_moi === undefined) _moi = api("/api/moi").catch(() => null);
  return _moi;
}

export function exigerConnexion() {
  return moi().then((u) => {
    if (!u) location.replace(`/connexion.html?suite=${encodeURIComponent(location.pathname + location.search + location.hash)}`);
    return u;
  });
}

// iPhone et iPad (iPadOS se présente comme un Mac tactile) ; installée = ouverte depuis l'écran d'accueil
export const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
export const installee = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

// en-tête : le bouton « Télécharger » mène aux étapes iPhone sur iOS (pas d'APK), disparaît dans l'appli installée
function boutonTelecharger() {
  const b = document.querySelector(".nav .telecharger");
  if (!b) return;
  if (installee) b.remove();
  else if (ios) { b.href = "/telecharger.html#iphone"; b.firstChild.textContent = "Installer"; }
}

// en-tête : le lien de compte selon la session
export async function entete() {
  const lien = document.querySelector("[data-compte]");
  if (!lien) return;
  const u = await moi();
  if (u) { lien.textContent = "Mon espace"; lien.href = "/espace.html"; }
}

export function toast(texte, ms = 3200) {
  const t = document.createElement("div");
  t.className = "toast"; t.setAttribute("role", "status"); t.textContent = texte;
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

// --- formats (à la française) ---
export const km = (m, d = 1) => (m / 1000).toFixed(d).replace(".", ",");
export function duree(s) {
  if (!s) return "–";
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
  return h ? `${h} h ${String(m).padStart(2, "0")}` : `${m} min ${String(ss).padStart(2, "0")}`;
}
export function allure(m, s) {  // min/km
  if (!m || !s) return "–";
  const sk = s / (m / 1000);
  return `${Math.floor(sk / 60)}:${String(Math.round(sk % 60)).padStart(2, "0")} /km`;
}
export const vitesse = (m, s) => (!m || !s ? "–" : `${(m / s * 3.6).toFixed(1).replace(".", ",")} km/h`);
export const rythme = (a) => (a.sport === "velo" ? vitesse(a.distance, a.duree) : allure(a.distance, a.duree));
export function date(t) {
  return new Date(t * 1000).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}
export const echapper = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// --- revêtement et types de voies (les mêmes catégories que le moteur) ---
export const VOIES = [["cyclable", "Pistes cyclables", "var(--trace)"], ["chemin", "Chemins et voies piétonnes", "var(--chemin)"],
  ["rue", "Rues et routes calmes", "var(--route)"], ["grand_axe", "Grands axes", "var(--peche)"], ["escaliers", "Escaliers", "var(--alerte)"]];
export const REVETEMENTS = [["revetu", "Revêtu", "var(--trace)"], ["pave", "Pavés", "var(--chemin)"],
  ["non_revetu", "Non revêtu", "var(--peche)"], ["inconnu", "Inconnu", "var(--fond-3)"]];

export function barre(valeurs, categories) {
  const total = Object.values(valeurs || {}).reduce((a, b) => a + b, 0) || 1;
  const parts = categories.filter(([k]) => valeurs[k] / total >= 0.005);
  return `<div class="barre-voies" role="img" aria-label="${parts.map(([k, n]) => `${n} ${Math.round(valeurs[k] / total * 100)} %`).join(", ")}">
    ${parts.map(([k, , c]) => `<span style="width:${valeurs[k] / total * 100}%;background:${c}"></span>`).join("")}</div>
    <div class="legende">${parts.map(([k, n, c]) => `<span><i style="background:${c}"></i>${n} ${Math.round(valeurs[k] / total * 100)} %</span>`).join("")}</div>`;
}

// --- GPX de l'itinéraire prévu : tracé seul, sans heure ni performance (même format que gpx.py) ---
export function gpxItineraire(coords, sport, distance, montee, ele, nom) {
  const kmT = km(distance);
  nom = nom || `Boucle Loopy ${kmT} km (${sport === "velo" ? "vélo" : "course à pied"})`;
  const desc = `Itinéraire prévu par Loopy : ${kmT} km` + (montee != null ? `, ${Math.round(montee)} m de D+` : "");
  const pts = coords.map(([la, lo], i) => {
    const e = ele && ele[i] != null ? `<ele>${ele[i].toFixed(1)}</ele>` : "";
    return `      <trkpt lat="${la.toFixed(6)}" lon="${lo.toFixed(6)}">${e}</trkpt>`;
  });
  return ['<?xml version="1.0" encoding="UTF-8"?>',
    '<gpx version="1.1" creator="Loopy" xmlns="http://www.topografix.com/GPX/1/1">',
    `  <metadata><name>${echapper(nom)}</name><desc>${echapper(desc)}</desc></metadata>`,
    `  <trk><name>${echapper(nom)}</name><desc>${echapper(desc)}</desc><type>${sport === "velo" ? "cycling" : "running"}</type>`,
    "    <trkseg>", ...pts, "    </trkseg>", "  </trk>", "</gpx>", ""].join("\n");
}
export const nomItineraire = (distance, sport) => `boucle_${Math.round(distance / 1000)}km_${sport}.gpx`;

export function telecharger(nom, texte, type = "application/gpx+xml") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([texte], { type }));
  a.download = nom;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// pictogrammes (trait 2 px, même grille 24 px)
export const ICONES = {
  velo: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="5.5" cy="16.5" r="3.5"/><circle cx="18.5" cy="16.5" r="3.5"/><path d="M5.5 16.5 9 9h6l3.5 7.5M9 9 12 16.5h-2M14 6h2.5l-1.5 3"/></svg>',
  course: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="14.5" cy="4" r="2"/><path d="m8 21 3-5 3 2v4M6.5 12.5 9 9.5l4-.5 2.5 3.5 3 .5M11.5 16 13 9"/></svg>',
};

boutonTelecharger();
entete();
