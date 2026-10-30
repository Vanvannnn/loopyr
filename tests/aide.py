"""Outils communs aux tests : traces synthétiques."""
from geo import Plan

PLAN = Plan(44.823, -0.445)


def ligne_droite(metres, pas=5.0, vitesse=3.0, t0=1000.0):
    """Points (t, lat, lon) vers l'est, tous les `pas` mètres, à `vitesse` m/s."""
    return [(t0 + i * pas / vitesse, *PLAN.latlon(i * pas, 0)) for i in range(int(metres / pas) + 1)]


def carre(cote):
    """Boucle carrée (lat, lon) de `cote` mètres, départ = arrivée."""
    coins = [(0, 0), (cote, 0), (cote, cote), (0, cote), (0, 0)]
    return [PLAN.latlon(x, y) for x, y in coins]
