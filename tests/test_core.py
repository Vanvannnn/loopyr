import os, random
import pytest
from conftest import RACINE
from core import Carte
from geo import haversine


@pytest.fixture(scope="module")
def carte():
    return Carte(os.path.join(RACINE, "data.db"))


def test_plus_proche_identique_a_la_recherche_complete(carte):
    random.seed(1)
    lat0, lon0, _ = carte.centre
    for _ in range(50):
        lat, lon = lat0 + random.uniform(-0.04, 0.04), lon0 + random.uniform(-0.06, 0.06)
        brut = min(carte.nodes, key=lambda n: carte._dist_m(lat, lon, *carte.nodes[n][:2]))
        assert carte._dist_m(lat, lon, *carte.nodes[carte.plus_proche(lat, lon)][:2]) == \
            pytest.approx(carte._dist_m(lat, lon, *carte.nodes[brut][:2]))


def test_altitude(carte):
    assert carte.altitude(*carte.centre[:2]) is not None
    assert carte.altitude(48.85, 2.35) is None  # Paris : hors zone


@pytest.mark.parametrize("dist,dp", [(3000, 20), (5000, 80), (10000, 150)])
def test_boucle_fermee_continue_et_a_la_bonne_distance(carte, dist, dp):
    random.seed(dist)
    res = carte.generer(dist, dp, max_s=3)
    c = res["coords"]
    assert res["distance"] == pytest.approx(dist, rel=0.2)
    assert haversine(c[0], c[-1]) < 1
    assert max(haversine(a, b) for a, b in zip(c, c[1:])) < 400  # pas de saut entre tronçons
    longueur = sum(haversine(a, b) for a, b in zip(c, c[1:]))
    assert longueur == pytest.approx(res["distance"], rel=0.03)  # le tracé = la distance annoncée
    assert res["recouvrement"] < 0.15


def test_le_denivele_demande_compte(carte):
    random.seed(3)
    plat = carte.generer(8000, 0, max_s=3)["denivele"]
    random.seed(3)
    bosses = carte.generer(8000, 250, max_s=3)["denivele"]
    assert bosses > 1.8 * plat
