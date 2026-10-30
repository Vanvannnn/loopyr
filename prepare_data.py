"""À lancer UNE FOIS sur ton PC (pip install osmnx requests) : crée data.db.
Ce fichier (carte + altitudes) est embarqué dans l'app : plus aucun appel réseau sur le téléphone."""
import json, os, sqlite3, time, requests, osmnx as ox

POINT = (44.823, -0.445)   # centre de ta zone
RAYON = 5000               # mètres couverts par l'app (plus grand = plus de requêtes)

G = ox.graph_from_point(POINT, dist=RAYON, network_type="walk")
noeuds = list(G.nodes(data=True))

# Altitude de chaque nœud (OpenTopoData, modèle européen 25 m, 100 points par requête).
# Les altitudes reçues sont gardées dans elev_cache.json : si le script s'arrête, relance-le, il reprend.
URL = "https://api.opentopodata.org/v1/eudem25m"
elev = {int(k): v for k, v in json.load(open("elev_cache.json")).items()} if os.path.exists("elev_cache.json") else {}
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
        raise SystemExit("Quota OpenTopoData atteint. Relance le script plus tard (demain si besoin) : il reprend où il s'est arrêté.")
    r.raise_for_status()
    for (n, _), res in zip(lot, r.json()["results"]):
        elev[n] = res["elevation"] if res["elevation"] is not None else 0
    json.dump(elev, open("elev_cache.json", "w"))
    print(f"{len(elev)}/{len(noeuds)} altitudes")

db = sqlite3.connect("data.db")
db.executescript("""
DROP TABLE IF EXISTS nodes; DROP TABLE IF EXISTS edges; DROP TABLE IF EXISTS meta;
CREATE TABLE nodes(id INTEGER PRIMARY KEY, lat REAL, lon REAL, ele REAL);
CREATE TABLE edges(u INTEGER, v INTEGER, length REAL, trail INTEGER, geom TEXT);
CREATE TABLE meta(lat REAL, lon REAL, rayon INTEGER);""")
db.executemany("INSERT INTO nodes VALUES (?,?,?,?)",
               [(n, d["y"], d["x"], elev[n]) for n, d in noeuds])
lignes = []
for u, v, d in G.edges(data=True):
    hw, sf = str(d.get("highway", "")), str(d.get("surface", ""))
    trail = int("path" in hw or "track" in hw or "dirt" in sf)
    geom = [[round(y, 5), round(x, 5)] for x, y in d["geometry"].coords] if "geometry" in d else None
    lignes.append((u, v, d["length"], trail, json.dumps(geom)))
db.executemany("INSERT INTO edges VALUES (?,?,?,?,?)", lignes)
db.execute("INSERT INTO meta VALUES (?,?,?)", (*POINT, RAYON))
db.commit()
print("data.db créé")