"""Version 0.5 : dénivelé en direct, altimètre, journal, annonces de navigation, nom proposé, export GPX."""
import sqlite3
import time

import pytest
from aide import PLAN, carre, ligne_droite

from annonces import Annonceur
from course import Course, nom_auto
from geo import Altimetre, Altitudes, altitude_pression
from gpx import gpx
from journal import Journal, appliquer


def test_denivele_progresse_pendant_la_sortie():
    """Test 5 : sur une montée régulière, le D+ avance au fil des positions (pas seulement à la fin)."""
    c = Course(debut=1000.0)
    vus = []
    for i, (t, la, lo) in enumerate(ligne_droite(600, pas=10)):
        c.ajouter(t, la, lo, 20 + i * 0.5)  # +5 m tous les 100 m
        vus.append(c.dplus)
    assert vus[20] == pytest.approx(10, abs=3) and vus[40] == pytest.approx(20, abs=3)
    assert vus[-1] == pytest.approx(30, abs=3)
    assert c.dmoins == 0 and c.alt == pytest.approx(50) and c.alt_min == 20 and c.alt_max == pytest.approx(50)


def test_plat_bruite_ne_cree_pas_de_denivele():
    """Sur le plat, l'altitude GPS oscille de plusieurs mètres : passée par l'altimètre (lissage), elle ne doit
    pas faire monter le D+ (l'ancien défaut : du dénivelé « gagné » en courant sur du plat)."""
    import random
    h = random.Random(4)
    c, alt = Course(debut=1000.0), Altimetre(None)
    for t, la, lo in ligne_droite(2000, pas=5):
        c.ajouter(t, la, lo, alt(la, lo, gps=30 + h.gauss(0, 2.5), vprec=6))
    c.seuil = 5  # ce que fait journal.appliquer quand la source est le GPS
    assert alt.source == "gps" and c.dplus <= 6 and c.dmoins <= 6


def test_vraie_montee_gps_comptee_malgre_le_bruit():
    import random
    h = random.Random(7)
    c, alt = Course(debut=1000.0), Altimetre(None)
    c.seuil = 5
    for i, (t, la, lo) in enumerate(ligne_droite(2000, pas=5)):
        c.ajouter(t, la, lo, alt(la, lo, gps=30 + i * 0.1 + h.gauss(0, 2.5), vprec=6))  # +40 m sur 2 km
    assert c.dplus == pytest.approx(40, abs=8)


def test_denivele_negatif():
    c = Course(debut=1000.0)
    for i, (t, la, lo) in enumerate(ligne_droite(400, pas=10)):
        c.ajouter(t, la, lo, 100 - i)  # descente de 40 m
    assert c.dmoins == pytest.approx(39, abs=3) and c.dplus == 0


def test_altimetre_terrain_puis_baro():
    terrain = Altitudes([PLAN.latlon(0, 0), PLAN.latlon(1000, 0)], [10.0, 60.0])
    a = Altimetre(terrain)
    assert a(*PLAN.latlon(500, 0)) == pytest.approx(35, abs=0.5) and a.source == "terrain"
    assert a(*PLAN.latlon(500, 500), gps=80, vprec=30) is None  # hors boucle, GPS trop imprécis : rien d'inventé
    # baromètre : calé sur le terrain, puis ses variations comptent (−0,12 hPa ≈ +1 m)
    b = Altimetre(terrain)
    h0 = b(*PLAN.latlon(0, 0), pression=1013.0)
    assert h0 == pytest.approx(10, abs=0.01) and b.source == "baro"
    assert b(*PLAN.latlon(10, 0), pression=1012.0) - h0 == pytest.approx(altitude_pression(1012) - altitude_pression(1013),
                                                                           abs=0.01)


def test_altimetre_gps_lisse_sans_boucle():
    a = Altimetre(None)
    vals = [a(44.8, -0.6, gps=g, vprec=5) for g in (50, 58, 42, 51, 49)]
    assert a.source == "gps" and max(vals) - min(vals) < 8  # le bruit de ±8 m est amorti


def test_journal_ancien_format_complete(tmp_path):
    """Un journal créé par la version 0.4 (sortie en cours pendant la mise à jour) reste lisible."""
    chemin = str(tmp_path / "j.db")
    db = sqlite3.connect(chemin)
    db.executescript("""CREATE TABLE evts(id INTEGER PRIMARY KEY, type TEXT, t REAL, lat REAL, lon REAL, ele REAL, prec REAL);
                        CREATE TABLE meta(cle TEXT PRIMARY KEY, valeur TEXT);
                        INSERT INTO evts(type, t) VALUES ('debut', 1000);
                        INSERT INTO evts(type, t, lat, lon, prec) VALUES ('point', 1001, 44.8, -0.6, 5);""")
    db.commit()
    db.close()
    j = Journal(chemin)
    j.ecrire("point", 1010, 44.8003, -0.6, 31.0, 5, 1012.5, 3)
    evts = j.lire()
    assert len(evts) == 3 and len(evts[0]) == 9 and evts[2][7] == 1012.5
    c = None
    for e in evts:
        c = appliquer(c, e, Altimetre(None))
    assert c.dist > 20


def test_annonce_des_virages_et_boucle_recalculee():
    dits = []
    hints = [[1, 2, 0, 500.0, -90]]  # à gauche au premier coin
    a = Annonceur(carre(500), dits.append, consignes=hints, sport="course")
    a.traiter((1, "debut", 0, None, None, None, None, None, None))
    for k, x in enumerate(range(0, 480, 10)):
        a.traiter((k + 2, "point", k * 3, *PLAN.latlon(x, 0), None, 5, None, None))
    assert any(d.startswith("Dans") and "tourne à gauche" in d for d in dits)
    assert sum("tourne à gauche" in d for d in dits) == 1  # dite une seule fois
    # l'app a inversé / recalculé la boucle : le service la relit
    nouvelle = {"coords": list(reversed(carre(500))), "hints": [[1, 5, 0, 500.0, 90]]}
    b = Annonceur(carre(500), dits.append, boucle=lambda: nouvelle)
    b.traiter((1, "boucle", 0, None, None, None, None, None, None))
    assert b.prog.pts[1] == pytest.approx(nouvelle["coords"][1]) and b.prog.consignes[0][1] == 5


def test_nom_auto():
    matin = time.mktime((2026, 11, 8, 8, 30, 0, 0, 0, -1))
    soir = time.mktime((2026, 11, 8, 19, 0, 0, 0, 0, -1))
    assert nom_auto("course", matin, 8000, "Pessac") == "Course matinale à Pessac"
    assert nom_auto("velo", soir, 120000) == "Sortie vélo longue distance du soir"
    assert nom_auto("velo", soir, 30000, "Bordeaux") == "Sortie vélo du soir à Bordeaux"


def test_gpx_activite_avec_nom_et_heures():
    c = Course(debut=1000.0)
    for t, la, lo in ligne_droite(200):
        c.ajouter(t, la, lo, 12.0)
    c.terminer(1100)
    act = {**c.resume(), "sport": "velo", "nom": "Sortie vélo matinale à Pessac", "description": "Belle sortie"}
    texte = gpx(act)
    assert "<time>" in texte and "Sortie vélo matinale à Pessac" in texte and "<type>cycling</type>" in texte
    assert act["denivele_neg"] == 0 and act["vmax"] > 0
