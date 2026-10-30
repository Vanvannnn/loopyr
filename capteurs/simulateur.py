"""PC uniquement : un coureur virtuel suit la boucle et écrit ses positions dans le journal,
exactement comme le fait le service GPS sur le téléphone. Touche D : détour (sortie du parcours)."""
import math, time

from kivy.clock import Clock
from kivy.core.window import Window

from geo import Plan, haversine


class Simulateur:
    def __init__(self, journal, coords):
        self.journal, self.pts = journal, coords
        self.i, self.d, self.detour, self.t0 = 0, 0.0, False, time.time()
        self.plan = Plan(*coords[0])

    def demarrer(self):
        Clock.schedule_interval(self._pas, 1)
        Window.bind(on_key_down=self._touche)
        self._ecrire(*self.pts[0])

    def arreter(self):
        Clock.unschedule(self._pas)
        Window.unbind(on_key_down=self._touche)

    def _touche(self, _win, _key, _scancode, texte, _mod):
        if texte == "d":
            self.detour = not self.detour
            print(f"[simulateur] détour {'activé' if self.detour else 'terminé'}")

    def _ecrire(self, lat, lon):
        if self.detour:  # 80 m au nord du parcours
            x, y = self.plan.xy(lat, lon)
            lat, lon = self.plan.latlon(x, y + 80)
        self.journal.ecrire("point", time.time(), lat, lon, None, 5)

    def _pas(self, dt):
        if self.journal.etat() == "pause":
            return
        reste = (3 + 0.6 * math.sin((time.time() - self.t0) / 8)) * dt  # ~3 m/s, avec des variations
        while self.i < len(self.pts) - 1:
            d = haversine(self.pts[self.i], self.pts[self.i + 1])
            if self.d + reste < d:
                self.d += reste
                break
            reste -= d - self.d
            self.d, self.i = 0.0, self.i + 1
        a, b = self.pts[self.i], self.pts[min(self.i + 1, len(self.pts) - 1)]
        f = self.d / (haversine(a, b) or 1e-6)
        self._ecrire(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
