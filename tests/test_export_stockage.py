import json, os
import xml.etree.ElementTree as ET
from aide import ligne_droite
from course import Course
from gpx import exportable, gpx
from stockage import Stockage

NS = {"g": "http://www.topografix.com/GPX/1/1"}


def activite():
    c = Course(debut=1_700_000_000.0)
    pts = ligne_droite(500, t0=1_700_000_000.0)
    for t, la, lo in pts[:50]:
        c.ajouter(t, la, lo, 20.0)
    c.pause(pts[49][0] + 1)
    c.reprendre(pts[49][0] + 30)
    for t, la, lo in pts[50:]:
        c.ajouter(t + 30, la, lo, None)
    c.terminer(pts[-1][0] + 31)
    return c.resume()


def test_gpx_valide_avec_un_segment_par_pause():
    act = activite()
    racine = ET.fromstring(gpx(act, nom="Sortie <test> & co"))
    segs = racine.findall("g:trk/g:trkseg", NS)
    assert len(segs) == 2
    heures = [p.find("g:time", NS).text for s in segs for p in s.findall("g:trkpt", NS)]
    assert heures == sorted(heures) and heures[0] == "2023-11-14T22:13:20Z"
    assert segs[0].find("g:trkpt/g:ele", NS).text == "20.0"
    assert segs[1].find("g:trkpt/g:ele", NS) is None
    assert racine.find("g:trk/g:name", NS).text == "Sortie <test> & co"


def test_stockage_enregistre_liste_supprime(tmp_path):
    s = Stockage(str(tmp_path / "activites"))
    a = activite()
    s.enregistrer(a)
    s.enregistrer({**a, "id": "plus-ancienne", "debut": a["debut"] - 99})
    assert [x["id"] for x in s.lister()] == [a["id"], "plus-ancienne"]
    assert "segments" not in s.lister()[0]
    assert exportable(s.charger(a["id"]))
    s.supprimer("plus-ancienne")
    assert [x["id"] for x in s.lister()] == [a["id"]]
    assert not [f for f in os.listdir(tmp_path / "activites") if f.endswith(".tmp")]


def test_index_corrompu_reconstruit_sans_perte(tmp_path):
    s = Stockage(str(tmp_path / "activites"))
    s.enregistrer(activite())
    (tmp_path / "activites" / "index.json").write_text("{pas du json")
    assert len(s.lister()) == 1
    assert any(f.endswith(".bak") for f in os.listdir(tmp_path / "activites"))


def test_migration_ancien_profil(tmp_path):
    ancien = tmp_path / "profil.json"
    ancien.write_text(json.dumps([{"date": "2026-10-03 13:35", "distance": 5012, "duree": 1650,
                                   "trace": [[44.82, -0.44], [44.83, -0.45]]}]))
    s = Stockage(str(tmp_path / "activites"), ancien_profil=str(ancien))
    (r,) = s.lister()
    assert r["distance"] == 5012 and r["id"] == "20261003-133500"
    assert not exportable(s.charger(r["id"]))
    assert not ancien.exists() and (tmp_path / "profil.json.migre").exists()


def test_ancien_profil_corrompu_mis_de_cote(tmp_path):
    ancien = tmp_path / "profil.json"
    ancien.write_text("[{tronqué")
    s = Stockage(str(tmp_path / "activites"), ancien_profil=str(ancien))
    assert s.lister() == []
    assert any(f.name.endswith(".bak") for f in tmp_path.iterdir())
