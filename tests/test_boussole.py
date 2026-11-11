import math

from capteurs.boussole import azimut


def test_a_plat_vers_le_nord():
    assert azimut([0, 0, 0, 1]) == 0


def test_a_plat_tourne_vers_l_ouest():
    s = math.sin(math.radians(45))
    assert round(azimut([0, 0, s, s])) == 270  # rotation de 90° vers la gauche autour de la verticale


def test_sans_composante_w():
    assert round(azimut([0, 0, 0])) == 0
