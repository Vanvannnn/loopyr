"""Deux exports GPX 1.1 bien distincts. Python pur.
- gpx_itineraire : la boucle PRÉVUE (tracé seul, sans heure ni performance) : à importer dans un GPS, une
  montre, ou sur Strava comme itinéraire.
- gpx : une activité RÉELLEMENT FAITE (points horodatés par le GPS, un segment par période sans pause) :
  importable sur strava.com (Importer > Fichier) ou envoyée par l'API Strava."""
from datetime import datetime, timezone
from xml.sax.saxutils import escape

TYPES = {"course": "running", "velo": "cycling"}
NOMS = {"course": "Course", "velo": "Sortie vélo"}
ENTETE = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<gpx version="1.1" creator="Loopy" xmlns="http://www.topografix.com/GPX/1/1">']


def heure_iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def exportable(act):
    """Les anciennes activités (avant l'horodatage des points) ne peuvent pas être exportées."""
    return any(seg for seg in act.get("segments") or ())


def _pt(lat, lon, ele, t=None):
    e = "" if ele is None else f"<ele>{ele:.1f}</ele>"
    h = "" if t is None else f"<time>{heure_iso(t)}</time>"
    return f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}">{e}{h}</trkpt>'


def gpx(act, nom=None):
    sport = act.get("sport", "course")
    nom = escape(nom or act.get("nom") or f"{NOMS.get(sport, 'Sortie')} Loopy {act['date']}")
    lignes = ENTETE + [f"  <metadata><name>{nom}</name><time>{heure_iso(act['debut'])}</time></metadata>",
                       f"  <trk><name>{nom}</name><type>{TYPES.get(sport, 'running')}</type>"]
    for seg in act["segments"]:  # un segment par période sans pause
        lignes.append("    <trkseg>")
        lignes += [_pt(lat, lon, ele, t) for t, lat, lon, ele in seg]
        lignes.append("    </trkseg>")
    lignes += ["  </trk>", "</gpx>", ""]
    return "\n".join(lignes)


def nom_itineraire(distance, sport):
    """boucle_10km_velo.gpx"""
    return f"boucle_{round(distance / 1000)}km_{sport}.gpx"


def gpx_itineraire(coords, sport, distance, montee=None, ele=None, nom=None):
    """Le tracé prévu : coordonnées et altitude seulement. Aucune durée ni vitesse : rien n'a été couru."""
    km = f"{distance / 1000:.1f}".replace(".", ",")
    nom = escape(nom or f"Boucle Loopy {km} km ({'vélo' if sport == 'velo' else 'course à pied'})")
    desc = f"Itinéraire prévu par Loopy : {km} km" + (f", {montee:.0f} m de D+" if montee is not None else "")
    ele = ele or [None] * len(coords)
    lignes = ENTETE + [f"  <metadata><name>{nom}</name><desc>{escape(desc)}</desc></metadata>",
                       f"  <trk><name>{nom}</name><desc>{escape(desc)}</desc><type>{TYPES[sport]}</type>",
                       "    <trkseg>"]
    lignes += [_pt(lat, lon, e) for (lat, lon), e in zip(coords, ele)]
    lignes += ["    </trkseg>", "  </trk>", "</gpx>", ""]
    return "\n".join(lignes)
