"""Suivi de la boucle : chaque test rejoue une situation réelle de navigation (test 6 du cahier des charges)."""
import pytest
from aide import PLAN, carre
from progression import Progression, arrondi, texte_consigne

# boucle carrée de 500 m de côté : est, puis nord, ouest, sud. Consignes « BRouter » aux coins (indices des points).
CONSIGNES = [[1, 2, 0, 500.0, -90], [2, 2, 0, 500.0, -90], [3, 2, 0, 500.0, -90]]


def marcher(p, pts, t0=0, dt=2, precision=5):
    for k, (x, y) in enumerate(pts):
        p.maj(*PLAN.latlon(x, y), t=t0 + k * dt, precision=precision)
    return p


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
    assert p.pourcent < 1 and not p.arrive


def test_depart_dans_le_mauvais_sens_inverse_la_boucle():
    """Il fallait partir à l'est ; on part au sud (le dernier côté, à l'envers). Avant : « 99 %, 30 m restants »."""
    p = Progression(carre(500), CONSIGNES)
    marcher(p, [(0, -y) for y in range(0, 4)])  # quelques mètres : encore au départ
    vus = []
    for k, y in enumerate(range(5, 120, 5)):
        p.maj(*PLAN.latlon(0, y), t=10 + 2 * k, precision=5)  # vers le nord, le long du dernier côté, à l'envers
        vus.append((p.pourcent, p.evenement))
        assert p.pourcent < 50, "la boucle ne doit jamais sembler presque finie"
        assert not p.arrive
    assert p.inversee
    assert any(e == "inverse" for _, e in vus)
    assert p.fait == pytest.approx(115, abs=10)  # 115 m faits, dans le nouveau sens
    assert p.restant == pytest.approx(1885, abs=10)
    assert not p.hors_trace
    # les consignes suivent : au premier coin (0, 500), venant du sud, on tourne à droite vers l'est
    texte, distance, _ = p.prochaine()
    assert texte == "Tourne à droite" and distance == pytest.approx(385, abs=10)


def test_depart_dans_le_bon_sens_reste_dans_ce_sens():
    p = Progression(carre(500), CONSIGNES)
    marcher(p, [(x, 0) for x in range(0, 200, 5)])
    assert not p.inversee and p.fait == pytest.approx(195, abs=3)
    assert p.prochaine()[0] == "Tourne à gauche"


def test_trottoir_parallele_reste_sur_le_parcours():
    """Le parcours suit la route ; on court sur le trottoir 12 m à côté, GPS précis à 8 m."""
    p = Progression(carre(500))
    for k, x in enumerate(range(0, 480, 5)):
        p.maj(*PLAN.latlon(x, -12), t=k, precision=8)
        assert not p.hors_trace and p.evenement != "hors"
    assert p.fait == pytest.approx(475, abs=3)


def test_position_aberrante_ignoree():
    p = Progression(carre(500))
    marcher(p, [(x, 0) for x in range(0, 100, 5)])
    fait = p.fait
    p.maj(*PLAN.latlon(100, 300), t=100, precision=150)  # saut du GPS sous un pont
    assert p.fait == fait and not p.hors_trace


def test_sortie_reelle_puis_retour():
    p = Progression(carre(500))
    marcher(p, [(x, 0) for x in range(0, 105, 5)])
    p.maj(*PLAN.latlon(100, -60), t=50, precision=5)
    p.maj(*PLAN.latlon(100, -70), t=53, precision=5)
    assert not p.hors_trace  # pas d'alerte sur une ou deux positions
    p.maj(*PLAN.latlon(100, -80), t=58, precision=5)
    assert p.hors_trace and p.evenement == "hors" and p.ecart == pytest.approx(80, abs=1)
    p.maj(*PLAN.latlon(100, -85), t=60, precision=5)
    assert p.evenement is None  # pas d'alerte répétée
    p.maj(*PLAN.latlon(110, -5), t=70, precision=5)
    assert p.hors_trace  # une position ne suffit pas pour annoncer le retour
    p.maj(*PLAN.latlon(115, -3), t=72, precision=5)
    assert not p.hors_trace and p.evenement == "retour"


def test_imprecision_elargit_la_tolerance():
    p = Progression(carre(500))
    for k, x in enumerate(range(0, 300, 5)):
        p.maj(*PLAN.latlon(x, 35), t=k * 2, precision=30)  # ville dense : GPS à 30 m, 35 m d'écart apparent
    assert not p.hors_trace


def test_raccourci_recale_la_progression():
    p = Progression(carre(500))
    p.maj(*PLAN.latlon(100, 0), t=0)
    marcher(p, [(0, 420), (0, 400), (0, 380)], t0=20)  # on a coupé vers le dernier côté, et on le descend
    assert p.fait == pytest.approx(1620, abs=5) and p.evenement == "raccourci"
    assert not p.hors_trace and not p.inversee


def test_passage_pres_du_depart_au_milieu_n_est_pas_une_arrivee():
    """Boucle en huit qui repasse au départ à mi-parcours : ce n'est pas la fin."""
    pts = [PLAN.latlon(x, y) for x, y in ((0, 0), (400, 0), (400, 400), (0, 400), (0, 0), (-400, 0), (-400, -400),
                                          (0, -400), (0, 0))]
    p = Progression(pts)
    chemin = [(x, 0) for x in range(0, 400, 10)] + [(400, y) for y in range(0, 400, 10)] + \
             [(x, 400) for x in range(400, 0, -10)] + [(0, y) for y in range(400, -1, -10)]
    marcher(p, chemin)
    assert p.pourcent == pytest.approx(50, abs=2) and not p.arrive
    marcher(p, [(x, 0) for x in range(0, -400, -10)] + [(-400, y) for y in range(0, -400, -10)] +
            [(x, -400) for x in range(-400, 0, 10)] + [(0, y) for y in range(-400, 1, 10)], t0=1000)
    assert p.arrive


def test_consignes():
    assert texte_consigne(5) == "Tourne à droite"
    assert texte_consigne(14, 2) == "Au rond-point, prends la deuxième sortie"
    assert texte_consigne(14, 0) == "Au rond-point, suis le tracé"
    assert arrondi(18) == "20 m" and arrondi(1234) == "1,2 km"
    p = Progression(carre(500), [[1, 5, 0, 500.0, 90]])
    assert p.consigne_depart() == "Départ : pars vers l'est et suis le tracé sur 500 m"
    p2 = Progression(carre(500), [[1, 5, 0, 20.0, 90]])
    p2.cumul[1] = 20.0  # premier virage à 20 m
    p2.consignes = [(20.0, 5, 0)]
    assert p2.consigne_depart() == "Départ : tourne à droite dans 20 m"
    assert Progression(carre(500)).prochaine() is None  # boucle sans consignes (enregistrée avant la v0.5)
