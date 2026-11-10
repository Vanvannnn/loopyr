"""PC uniquement : un sportif virtuel suit la boucle et écrit ses positions dans le journal, exactement comme le
fait le service GPS sur le téléphone (avec une altitude GPS bruitée, comme un vrai téléphone).
Touche D : détour (sortie du parcours). Touche I : demi-tour (parcourir la boucle dans l'autre sens).
LOOPY_SIM_SENS=-1 : partir dès le départ dans le mauvais sens. LOOPY_SIM_VITESSE : m/s (3 par défaut)."""
import math, os, random, time

from kivy.clock import Clock
from kivy.core.window import Window

from geo import Plan, haversine


class Simulateur:
    def __init__(self, journal, coords, ele=None):
        self.journal, self.pts, self.ele = journal, list(coords), list(ele or [])
        self.d, self.detour, self.t0 = 0.0, False, time.time()
        self.sens = -1 if os.environ.get("LOOPY_SIM_SENS") == "-1" else 1
        self.vitesse = float(os.environ.get("LOOPY_SIM_VITESSE") or 3)
        self.i = 0 if self.sens > 0 else len(self.pts) - 1
        self.plan = Plan(*coords[0])
        self.hasard = random.Random(1)

    def demarrer(self):
        Clock.schedule_interval(self._pas, 1)
        Window.bind(on_key_down=self._touche)
        self._ecrire(*self.pts[self.i], self._altitude(self.i, 0))

    def arreter(self):
        Clock.unschedule(self._pas)
        Window.unbind(on_key_down=self._touche)

    def _touche(self, _win, _key, _scancode, texte, _mod):
        if texte == "d":
            self.detour = not self.detour
            print(f"[simulateur] détour {'activé' if self.detour else 'terminé'}")
        elif texte == "i":
            self.sens = -self.sens
            print(f"[simulateur] demi-tour (sens {self.sens})")

    def _altitude(self, i, f):
        if not self.ele:
            return None
        j = min(max(i + self.sens, 0), len(self.ele) - 1)
        a, b = self.ele[i], self.ele[j]
        if a is None or b is None:
            return None
        return a + (b - a) * f + self.hasard.gauss(0, 2.5)  # le GPS donne l'altitude à quelques mètres près

    def _ecrire(self, lat, lon, ele):
        if self.detour:  # 80 m au nord du parcours
            x, y = self.plan.xy(lat, lon)
            lat, lon = self.plan.latlon(x, y + 80)
        self.journal.ecrire("point", time.time(), lat, lon, ele, 5, None, 4)

    def _pas(self, dt):
        if self.journal.etat() == "pause":
            return
        reste = (self.vitesse + 0.6 * math.sin((time.time() - self.t0) / 8)) * dt  # avec des variations
        while 0 <= self.i + self.sens < len(self.pts):
            j = self.i + self.sens
            d = haversine(self.pts[self.i], self.pts[j])
            if self.d + reste < d:
                self.d += reste
                break
            reste -= d - self.d
            self.d, self.i = 0.0, j
        j = min(max(self.i + self.sens, 0), len(self.pts) - 1)
        a, b = self.pts[self.i], self.pts[j]
        f = self.d / (haversine(a, b) or 1e-6)
        self._ecrire(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, self._altitude(self.i, f))
