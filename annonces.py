"""Annonces pendant la course (splits, sortie du parcours), à partir du journal. Python pur.
Sur Android, c'est le service GPS qui les fait : elles continuent écran éteint."""
from journal import appliquer
from progression import Progression


def phrase_allure(sec):
    m, s = divmod(int(round(sec)), 60)
    return f"{m} minutes {s:02d}" if s else f"{m} minutes"


class Annonceur:
    def __init__(self, coords, dire, vibrer=None, voix_active=lambda: True):
        self.course, self.km, self.hors = None, 0, False
        self.prog = Progression(coords) if len(coords or ()) >= 2 else None
        self.dire, self.vibrer, self.voix_active = dire, vibrer, voix_active

    def _annoncer(self, texte):
        if self.voix_active():
            self.dire(texte)

    def traiter(self, evt):
        self.course = appliquer(self.course, evt)
        if self.course is None:
            return
        if evt[1] == "point" and self.prog and not self.course.en_pause:
            self.prog.maj(evt[3], evt[4], evt[2])
        while len(self.course.splits) > self.km:
            self.km += 1
            self._annoncer(f"Kilomètre {self.km}. Allure {phrase_allure(self.course.splits[self.km - 1])}.")
        if self.prog and self.prog.hors_trace != self.hors:
            self.hors = self.prog.hors_trace
            if self.hors and self.vibrer:
                self.vibrer()
            self._annoncer("Attention, tu sors du parcours." if self.hors else "Retour sur le parcours.")
