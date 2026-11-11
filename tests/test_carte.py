import math

from ui.carte import chevrons


def test_chevrons_sens_de_parcours():
    c = chevrons([(0, 0), (100, 0), (100, 100)], 50)
    assert [(round(x), round(y)) for x, y, _ in c] == [(25, 0), (75, 0), (100, 25), (100, 75)]
    assert [round(math.degrees(a)) for *_, a in c] == [0, 0, 90, 90]  # dans le sens du tracé
    assert chevrons([(0, 0), (0, 0)], 10) == []
