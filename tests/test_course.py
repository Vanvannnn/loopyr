import pytest
from aide import PLAN, ligne_droite
from course import Course, fmt_allure, fmt_temps


def courir(c, pts, ele=None):
    for t, lat, lon in pts:
        c.ajouter(t, lat, lon, ele)


def test_distance_et_duree():
    c = Course(debut=1000.0)
    courir(c, ligne_droite(1000))
    assert c.dist == pytest.approx(1000, rel=0.01)
    c.terminer(1000 + 1000 / 3)
    assert c.duree() == pytest.approx(333.3, abs=0.1)


def test_saut_gps_ignore():
    c = Course(debut=1000.0)
    courir(c, ligne_droite(100))
    t, lat, lon = ligne_droite(100)[-1]
    c.ajouter(t + 1, *PLAN.latlon(600, 0))  # 500 m en 1 s
    assert c.dist == pytest.approx(100, rel=0.01)


def test_point_imprecis_ignore():
    c = Course(debut=1000.0)
    c.ajouter(1000, 44.823, -0.445)
    assert not c.ajouter(1010, *PLAN.latlon(30, 0), precision=40)
    assert c.dist == 0


def test_premier_point_aberrant_ne_bloque_pas_la_course():
    c = Course(debut=1000.0)
    c.ajouter(1000, *PLAN.latlon(5000, 0))  # premier fix très loin
    courir(c, ligne_droite(200, t0=1001))
    assert c.dist > 150


def test_pause_gele_duree_et_distance_sans_trait_droit():
    c = Course(debut=1000.0)
    courir(c, ligne_droite(100))  # jusqu'à t ≈ 1033
    c.pause(1040)
    c.ajouter(1050, *PLAN.latlon(150, 0))  # ignoré : en pause
    c.reprendre(1100)
    c.ajouter(1101, *PLAN.latlon(400, 0))  # reprise 300 m plus loin : pas de distance comptée
    c.ajouter(1103, *PLAN.latlon(406, 0))
    assert c.dist == pytest.approx(106, rel=0.02)
    c.terminer(1110)
    assert c.duree() == pytest.approx(110 - 60)
    assert c.duree_totale() == 110
    assert len([s for s in c.segments if s]) == 2


def test_vitesse_nulle_en_pause():
    c = Course(debut=1000.0, horloge=lambda: 1030.0)
    courir(c, ligne_droite(90))
    assert c.vitesse() == pytest.approx(3, rel=0.05)
    c.pause(1030)
    assert c.vitesse() == 0


def test_splits():
    c = Course(debut=1000.0)
    courir(c, ligne_droite(3100))
    assert len(c.splits) == 3
    for s in c.splits:
        assert s == pytest.approx(1000 / 3, rel=0.02)


def test_split_excluant_la_pause():
    c = Course(debut=1000.0)
    pts = ligne_droite(1200)
    courir(c, pts[:100])  # 495 m
    t = pts[99][0]
    c.pause(t)
    c.reprendre(t + 60)
    courir(c, [(tt + 60, la, lo) for tt, la, lo in pts[100:]])
    assert c.splits[0] == pytest.approx(1000 / 3, rel=0.02)


def test_denivele_avec_hysteresis():
    c = Course(debut=1000.0)
    eles = [10, 11, 10, 11, 10, 14, 13, 18, 12]  # bruit de 1 m ignoré ; +4, puis +5
    for (t, lat, lon), e in zip(ligne_droite(40), eles):
        c.ajouter(t, lat, lon, e)
    assert c.dplus == 9


def test_resume_garde_tous_les_points_horodates():
    c = Course(debut=1000.0)
    courir(c, ligne_droite(3000), ele=20)
    c.terminer(2000)
    r = c.resume()
    assert sum(len(s) for s in r["segments"]) == 601
    assert r["segments"][0][0][0] == 1000.0
    assert r["distance"] == pytest.approx(3000, rel=0.01)
    assert r["strava_id"] is None


def test_formats():
    assert fmt_temps(3725) == "01:02:05"
    assert fmt_allure(1000 / 312) == "5:12"
    assert fmt_allure(0) == "--:--"
