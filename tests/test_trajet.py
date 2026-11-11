"""Trajet de A à B : variantes du moteur sans doublon, et navigation sans inversion ni fausse arrivée."""
import pytest
from aide import PLAN

from boucles import ErreurItineraire, trajets
from progression import Progression

A, B = PLAN.latlon(0, 0), PLAN.latlon(3000, 0)


class FauxMoteur:
    """Variante 0 : tout droit ; 1 : par le nord ; 2 : copie de 0 (doublon) ; 3 : erreur."""

    def __init__(self):
        self.vus = []

    def itineraire(self, points, sport, alternative=0):
        self.vus.append(alternative)
        if alternative == 3:
            raise ErreurItineraire("Pas de route")
        xs = [(x, 0) for x in range(0, 3001, 100)] if alternative != 1 else \
            [(0, 0), (0, 400), *[(x, 400) for x in range(100, 3000, 100)], (3000, 400), (3000, 0)]
        coords = [PLAN.latlon(x, y) for x, y in xs]
        return {"coords": coords, "ele": [10.0] * len(coords), "distance": 3000.0 + 800 * (alternative == 1),
                "montee": 5.0, "troncons": [(3000.0, {"highway": "cycleway", "surface": "asphalt"})], "hints": []}


def test_variantes_sans_doublon():
    m = FauxMoteur()
    r = trajets(A, B, "velo", m, n=4)
    assert sorted(m.vus) == [0, 1, 2, 3]
    assert len(r["propositions"]) == 2 and r["propositions"][0]["distance"] == 3000
    assert r["arrivee"] == list(B) and r["message"] == "" and "cible" not in r
    assert r["propositions"][1]["resume_voies"]["voies"]["cyclable"] > 0


def test_points_invalides():
    with pytest.raises(ValueError, match="trop proches"):
        trajets(A, PLAN.latlon(50, 0), "course", FauxMoteur())
    with pytest.raises(ValueError, match="trop loin"):
        trajets(A, PLAN.latlon(150000, 0), "course", FauxMoteur())


def test_aucun_itineraire_explique():
    class Panne:
        def itineraire(self, *a, **k):
            raise ErreurItineraire("Pas de route ou de chemin praticable à cet endroit")
    r = trajets(A, B, "course", Panne())
    assert r["propositions"] == [] and r["message"].startswith("Pas de route")


def test_trajet_remonte_n_est_pas_inverse():
    p = Progression([PLAN.latlon(x, 0) for x in range(0, 3001, 100)])
    assert not p.boucle
    for k, x in enumerate(range(0, 1500, 10)):  # on avance jusqu'à 1,5 km
        p.maj(*PLAN.latlon(x, 0), t=k * 3, precision=5)
    evts = []
    for k, x in enumerate(range(1490, 1000, -10)):  # puis on revient vers A
        p.maj(*PLAN.latlon(x, 0), t=500 + k * 3, precision=5)
        evts.append(p.evenement)
    assert not p.inversee and evts.count("mauvais_sens") == 1 and not p.arrive
    for k, x in enumerate(range(1010, 3001, 10)):  # demi-tour, puis jusqu'à B
        p.maj(*PLAN.latlon(x, 0), t=700 + k * 3, precision=5)
    assert p.arrive and not p.mauvais_sens


def test_boucle_reste_une_boucle():
    from aide import carre
    assert Progression(carre(500)).boucle
