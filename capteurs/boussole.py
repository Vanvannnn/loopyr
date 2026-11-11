"""Capteur d'orientation d'Android (téléphone uniquement).
L'écoute est une petite classe Java (java/org/starva/loopy/EcouteBoussole.java) qui garde la dernière mesure :
Python la lit à son rythme, Android ne rappelle jamais Python depuis son propre fil."""
import math


def azimut(v):
    """Direction visée (0-360°) à partir du vecteur de rotation."""
    x, y, z = v[0], v[1], v[2]
    w = v[3] if len(v) > 3 else math.sqrt(max(0.0, 1 - x * x - y * y - z * z))
    r1, r2, r4 = 2 * (x * y - z * w), 2 * (x * z + y * w), 1 - 2 * (x * x + z * z)
    r5, r8 = 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)
    if abs(r8) > 0.7:  # téléphone à plat : on vise le haut de l'écran
        az = math.degrees(math.atan2(r1, r4))
    else:  # téléphone debout : on vise l'arrière (là où tu regardes)
        az = math.degrees(math.atan2(-r2, -r5))
    return az % 360


class Boussole:
    def __init__(self):
        self.ecoute, self.actif, self.erreur = None, False, ""

    def activer(self, oui):
        """Active ou coupe le capteur. Renvoie False si indisponible (raison dans self.erreur)."""
        try:
            from capteurs.android import activite, systeme  # jnius : téléphone uniquement
            sm = systeme(activite(), "sensor", "android.hardware.SensorManager")
            if oui:
                capteur = sm.getDefaultSensor(11)  # TYPE_ROTATION_VECTOR
                if capteur is None:
                    self.erreur = "Pas de boussole sur ce téléphone"
                    return False
                if self.ecoute is None:
                    from jnius import autoclass
                    self.ecoute = autoclass("org.starva.loopy.EcouteBoussole")()
                self.actif = True
                sm.registerListener(self.ecoute, capteur, 2)
            elif self.actif:
                self.actif = False
                sm.unregisterListener(self.ecoute)
        except Exception as err:
            self.erreur = f"Boussole indisponible ({err})"
            return False
        return True

    @property
    def az_brut(self):
        v = self.ecoute.valeurs if (self.actif and self.ecoute) else None
        return azimut(list(v)) if v and len(v) >= 3 else None
