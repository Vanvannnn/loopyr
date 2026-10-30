"""Capteur d'orientation d'Android (téléphone uniquement)."""
import math

from capteurs.android import activite, systeme


def creer_ecoute(rappel):
    from jnius import PythonJavaClass, java_method

    class Ecoute(PythonJavaClass):
        __javainterfaces__ = ["android/hardware/SensorEventListener"]

        @java_method("(Landroid/hardware/Sensor;I)V")
        def onAccuracyChanged(self, sensor, precision):
            pass

        @java_method("(Landroid/hardware/SensorEvent;)V")
        def onSensorChanged(self, event):
            rappel(list(event.values))

    return Ecoute()


class Boussole:
    def __init__(self):
        self.ecoute, self.actif, self.az_brut, self.erreur = None, False, None, ""

    def activer(self, oui):
        """Active ou coupe le capteur. Renvoie False si indisponible (raison dans self.erreur)."""
        try:
            sm = systeme(activite(), "sensor", "android.hardware.SensorManager")
            if oui:
                capteur = sm.getDefaultSensor(11)  # TYPE_ROTATION_VECTOR
                if capteur is None:
                    self.erreur = "Pas de boussole sur ce téléphone"
                    return False
                if self.ecoute is None:  # créé une fois et gardé : Android peut encore l'appeler
                    self.ecoute = creer_ecoute(self._lire)
                self.actif = True
                sm.registerListener(self.ecoute, capteur, 2)
            elif self.actif:
                self.actif = False
                sm.unregisterListener(self.ecoute)
                self.az_brut = None
        except Exception as err:
            self.erreur = f"Boussole indisponible ({err})"
            return False
        return True

    def _lire(self, v):  # appelé par Android : on garde juste la valeur
        if not self.actif:
            return
        x, y, z = v[0], v[1], v[2]
        w = v[3] if len(v) > 3 else math.sqrt(max(0.0, 1 - x * x - y * y - z * z))
        r1, r2, r4 = 2 * (x * y - z * w), 2 * (x * z + y * w), 1 - 2 * (x * x + z * z)
        r5, r8 = 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)
        if abs(r8) > 0.7:  # téléphone à plat : on vise le haut de l'écran
            az = math.degrees(math.atan2(r1, r4))
        else:  # téléphone debout : on vise l'arrière (là où tu regardes)
            az = math.degrees(math.atan2(-r2, -r5))
        self.az_brut = az % 360
