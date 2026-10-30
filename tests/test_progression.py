import pytest
from aide import PLAN, carre
from progression import Progression


def test_avance_le_long_de_la_boucle():
    p = Progression(carre(500))
    assert p.total == pytest.approx(2000, rel=0.01)
    p.maj(*PLAN.latlon(250, 5), t=0)
    assert p.fait == pytest.approx(250, abs=2)
    assert p.restant == pytest.approx(1750, abs=3)
    p.maj(*PLAN.latlon(500, 200), t=60)
    assert p.pourcent == pytest.approx(35, abs=0.5)
    assert len(p.partie_faite()) == 3


def test_le_depart_ne_saute_pas_a_l_arrivee():
    p = Progression(carre(500))  # départ et arrivée au même endroit
    p.maj(*PLAN.latlon(2, 2), t=0)
    assert p.pourcent < 1


def test_ne_saute_pas_sur_une_portion_qui_se_croise():
    # aller-retour sur la même rue : à l'aller, on ne doit pas sauter au retour
    pts = [PLAN.latlon(x, 0) for x in (0, 400, 800)] + [PLAN.latlon(x, 0) for x in (400, 0)]
    p = Progression(pts)
    for x in range(0, 800, 20):
        p.maj(*PLAN.latlon(x, 1), t=x)
    assert p.fait == pytest.approx(780, abs=2)
    for x in range(800, 0, -20):
        p.maj(*PLAN.latlon(x, 1), t=1000 + x)
    assert p.fait == pytest.approx(800 + 780, abs=25)
    fait = [p.fait]
    p.maj(*PLAN.latlon(10, 1), t=3000)
    assert p.fait >= fait[0]


def test_hors_trace_apres_le_delai():
    p = Progression(carre(500))
    p.maj(*PLAN.latlon(100, 0), t=0)
    p.maj(*PLAN.latlon(100, -50), t=1)
    assert not p.hors_trace
    p.maj(*PLAN.latlon(100, -50), t=12)
    assert p.hors_trace and p.ecart == pytest.approx(50, abs=1)
    p.maj(*PLAN.latlon(110, -5), t=13)
    assert not p.hors_trace


def test_raccourci_recale_la_progression():
    p = Progression(carre(500))
    p.maj(*PLAN.latlon(100, 0), t=0)
    p.maj(*PLAN.latlon(5, 400), t=200)  # on coupe directement vers le dernier côté
    assert p.fait == pytest.approx(1600, abs=5)
    assert not p.hors_trace
