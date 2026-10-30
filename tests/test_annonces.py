from aide import PLAN, carre
from annonces import Annonceur, phrase_allure


def test_annonces_splits_et_sortie_du_parcours():
    dits, vibrations = [], []
    a = Annonceur(carre(500), dits.append, lambda: vibrations.append(1))
    a.traiter((1, "debut", 0.0, None, None, None, None))
    t, i = 0.0, 2
    for x in range(0, 505, 5):  # 1er côté du carré, à 4 m/s
        t += 1.25
        a.traiter((i, "point", t, *PLAN.latlon(x, 0), None, 5)); i += 1
    for y in range(5, 600, 5):  # on continue tout droit vers le nord-est… hors du parcours
        t += 1.25
        a.traiter((i, "point", t, *PLAN.latlon(500 + 0.3 * y, y), None, 5)); i += 1
    assert "Kilomètre 1. Allure 4 minutes 06." in dits  # 500 m à 4 m/s puis 500 m à 4,2 m/s
    assert "Attention, tu sors du parcours." in dits and vibrations


def test_voix_coupee():
    dits = []
    a = Annonceur(carre(300), dits.append, voix_active=lambda: False)
    a.traiter((1, "debut", 0.0, None, None, None, None))
    for i, x in enumerate(range(0, 1300, 5)):
        a.traiter((i + 2, "point", i * 1.0, *PLAN.latlon(x, 0), None, 5))
    assert a.km == 1 and dits == []


def test_phrase_allure():
    assert phrase_allure(312) == "5 minutes 12"
    assert phrase_allure(300) == "5 minutes"
