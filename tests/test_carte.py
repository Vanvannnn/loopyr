import math

from ui.carte import chevrons


def test_chevrons_sens_de_parcours():
    c = chevrons([(0, 0), (100, 0), (100, 100)], 50)
    assert [(round(x), round(y)) for x, y, _ in c] == [(25, 0), (75, 0), (100, 25), (100, 75)]
    assert [round(math.degrees(a)) for *_, a in c] == [0, 0, 90, 90]  # dans le sens du tracé
    assert chevrons([(0, 0), (0, 0)], 10) == []


def test_carte_pas_encore_mise_en_page_ne_bloque_pas():
    """Régression : à la 1re ouverture de l'écran de fin, la carte mesure 100 × 34 px ; l'échelle devenait négative
    et le placement des flèches tournait sans fin (écran noir puis fermeture forcée en touchant « Terminer »)."""
    import signal
    from ui.carte import Trace

    def bloque(*_):
        raise AssertionError("dessiner() ne se termine pas")
    ancien = signal.signal(signal.SIGALRM, bloque)
    signal.alarm(5)
    try:
        t = Trace(size=(100, 34))
        t.coords = [(44.80 + i * 0.0003, -0.63) for i in range(60)]
        t.dessiner()
        assert t.s > 0
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, ancien)
    assert chevrons([(0, 0), (10, 0)], 0) == [] and chevrons([(0, 0), (10, 0)], -5) == []
