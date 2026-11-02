"""Activité -> fichier GPX 1.1, importable sur strava.com (Importer > Fichier). Python pur."""
from datetime import datetime, timezone
from xml.sax.saxutils import escape


def heure_iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def exportable(act):
    """Les anciennes activités (avant l'horodatage des points) ne peuvent pas être exportées."""
    return any(seg for seg in act.get("segments") or ())


def gpx(act, nom=None):
    nom = escape(nom or f"Course Loopy {act['date']}")
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<gpx version="1.1" creator="Loopy" xmlns="http://www.topografix.com/GPX/1/1">',
              f"  <metadata><name>{nom}</name><time>{heure_iso(act['debut'])}</time></metadata>",
              f"  <trk><name>{nom}</name><type>running</type>"]
    for seg in act["segments"]:  # un segment par période sans pause
        lignes.append("    <trkseg>")
        for t, lat, lon, ele in seg:
            e = "" if ele is None else f"<ele>{ele:.1f}</ele>"
            lignes.append(f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}">{e}<time>{heure_iso(t)}</time></trkpt>')
        lignes.append("    </trkseg>")
    lignes += ["  </trk>", "</gpx>", ""]
    return "\n".join(lignes)
