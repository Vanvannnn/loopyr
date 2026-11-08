"""Génère les boucles d'exemple du site (website/assets/exemples.json) avec le vrai moteur.
python outils/exemples_site.py   (une génération à la fois, avec des pauses : le serveur public est partagé)"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import boucles  # noqa: E402
from geo import reduire  # noqa: E402

CAS = [("Paris", (48.8530, 2.3499), 10000, "course"), ("Pessac", (44.8067, -0.6311), 50000, "velo"),
       ("Amsterdam", (52.3676, 4.9041), 8000, "course"), ("Montréal", (45.5019, -73.5674), 30000, "velo"),
       ("Kyoto", (35.0116, 135.7681), 10000, "course"), ("Bordeaux", (44.8378, -0.5792), 20000, "velo")]
SORTIE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "website", "assets", "exemples.json")

r, out = boucles.BRouter(), []
for ville, dep, d, sport in CAS:
    res = boucles.generer(dep, d, sport, r, n=1, graine=7)
    if res["propositions"]:
        p = res["propositions"][0]
        out.append({"ville": ville, "sport": sport, "cible": d, "distance": round(p["distance"]),
                    "montee": round(p["montee"]), "coords": reduire(p["coords"], 260),
                    "voies": {k: round(v) for k, v in p["resume_voies"]["voies"].items()},
                    "revetement": {k: round(v) for k, v in p["resume_voies"]["revetement"].items()},
                    "surface_connue": round(p["resume_voies"]["surface_connue"], 2)})
        print(ville, sport, p["distance"], flush=True)
    else:
        print(ville, "échec :", res["message"], flush=True)
    time.sleep(8)
with open(SORTIE, "w", encoding="utf-8") as f:
    json.dump({"genere": time.strftime("%Y-%m-%d"), "exemples": out}, f, ensure_ascii=False)
print("écrit", SORTIE)
