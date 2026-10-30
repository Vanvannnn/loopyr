"""À lancer sur ton PC (pip install -r requirements-data.txt) : crée data.db pour une zone.
Ce fichier (carte + altitudes) est embarqué dans l'app : plus aucun appel réseau sur le téléphone.
  python prepare_data.py                              # zone par défaut
  python prepare_data.py --lat 44.84 --lon -0.58 --rayon 4000
"""
import argparse, json, os, sqlite3, time

import osmnx as ox
import requests

from stockage import ecrire_json

URL = "https://api.opentopodata.org/v1/eudem25m"  # modèle européen 25 m, 100 points par requête
CACHE = "elev_cache.json"  # altitudes déjà reçues : si le script s'arrête, relance-le, il reprend


def altitudes(noeuds):
    elev = {}
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            elev = {int(k): v for k, v in json.load(f).items()}
    manquants = [x for x in noeuds if x[0] not in elev]
    for i in range(0, len(manquants), 100):
        lot = manquants[i:i + 100]
        for essai in range(5):
            time.sleep(1.1)  # limite : 1 requête par seconde
            r = requests.post(URL, timeout=30, json={
                "locations": "|".join(f"{d['y']:.5f},{d['x']:.5f}" for _, d in lot)})
            if r.status_code != 429:
                break
            print("Limite atteinte, pause de 10 s…")
            time.sleep(10)
        if r.status_code == 429:
            raise SystemExit("Quota OpenTopoData atteint. Relance le script plus tard (demain si besoin) : "
                             "il reprend où il s'est arrêté.")
        r.raise_for_status()
        for (n, _), res in zip(lot, r.json()["results"]):
            elev[n] = res["elevation"] if res["elevation"] is not None else 0
        ecrire_json(CACHE, elev)
        print(f"{len(elev)}/{len(noeuds)} altitudes")
    return elev


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--lat", type=float, default=44.823, help="centre de la zone")
    a.add_argument("--lon", type=float, default=-0.445, help="centre de la zone")
    a.add_argument("--rayon", type=int, default=5000, help="mètres couverts (plus grand = plus de requêtes)")
    a.add_argument("--sortie", default="data.db")
    args = a.parse_args()

    G = ox.graph_from_point((args.lat, args.lon), dist=args.rayon, network_type="walk")
    noeuds = list(G.nodes(data=True))
    elev = altitudes(noeuds)

    tmp = args.sortie + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.executescript("""
    CREATE TABLE nodes(id INTEGER PRIMARY KEY, lat REAL, lon REAL, ele REAL);
    CREATE TABLE edges(u INTEGER, v INTEGER, length REAL, trail INTEGER, geom TEXT);
    CREATE TABLE meta(lat REAL, lon REAL, rayon INTEGER);""")
    db.executemany("INSERT INTO nodes VALUES (?,?,?,?)", [(n, d["y"], d["x"], elev[n]) for n, d in noeuds])
    lignes = []
    for u, v, d in G.edges(data=True):
        hw, sf = str(d.get("highway", "")), str(d.get("surface", ""))
        trail = int("path" in hw or "track" in hw or "dirt" in sf)
        geom = [[round(y, 5), round(x, 5)] for x, y in d["geometry"].coords] if "geometry" in d else None
        lignes.append((u, v, d["length"], trail, json.dumps(geom)))
    db.executemany("INSERT INTO edges VALUES (?,?,?,?,?)", lignes)
    db.execute("INSERT INTO meta VALUES (?,?,?)", (args.lat, args.lon, args.rayon))
    db.commit()
    db.close()
    os.replace(tmp, args.sortie)  # l'ancien data.db reste intact si quelque chose échoue avant
    print(f"{args.sortie} créé")


if __name__ == "__main__":
    main()
