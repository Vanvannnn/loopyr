"""Annonces pendant la sortie (consignes de direction, splits, sortie du parcours), à partir du journal.
Python pur. Sur Android, c'est le service GPS qui les fait : elles continuent écran éteint."""
from journal import appliquer
from progression import Progression, arrondi

AVANCE_CONSIGNE = {"course": 60, "velo": 150}  # m : la consigne est dite à cette distance du carrefour


def phrase_allure(sec):
    m, s = divmod(int(round(sec)), 60)
    return f"{m} minutes {s:02d}" if s else f"{m} minutes"


class Annonceur:
    def __init__(self, coords, dire, vibrer=None, voix_active=lambda: True, consignes=None, sport="course",
                 boucle=None):
        """boucle : fonction qui relit la boucle du journal ({coords, hints}) quand elle change en route."""
        self.course, self.km, self.hors, self.dite = None, 0, False, None
        self.sport, self.boucle = sport, boucle
        self.prog = Progression(coords, consignes) if len(coords or ()) >= 2 else None
        self.dire, self.vibrer, self.voix_active = dire, vibrer, voix_active

    def _annoncer(self, texte):
        if self.voix_active():
            self.dire(texte)

    def traiter(self, evt):
        if evt[1] == "boucle" and self.boucle:  # boucle recalculée ou inversée dans l'app
            b = self.boucle() or {}
            if len(b.get("coords") or ()) >= 2:
                self.prog, self.dite = Progression(b["coords"], b.get("hints")), None
            return
        self.course = appliquer(self.course, evt)
        if self.course is None:
            return
        if evt[1] == "point" and self.prog and not self.course.en_pause:
            self.prog.maj(evt[3], evt[4], evt[2], evt[6])
            self._consigne()
        while len(self.course.splits) > self.km:
            self.km += 1
            self._annoncer(f"Kilomètre {self.km}. " + (f"Allure {phrase_allure(self.course.splits[self.km - 1])}."
                                                         if self.sport != "velo" else ""))
        if self.prog and self.prog.evenement == "inverse":
            self._annoncer("Tu fais la boucle dans l'autre sens : je te guide dans ce sens.")
        if self.prog and self.prog.hors_trace != self.hors:
            self.hors = self.prog.hors_trace
            if self.hors and self.vibrer:
                self.vibrer()
            self._annoncer("Attention, tu sors du parcours." if self.hors else "Retour sur le parcours.")
        if self.prog and self.prog.evenement == "arrivee":
            self._annoncer("Tu es arrivé. Boucle terminée.")

    def _consigne(self):
        """Chaque consigne est dite une fois, un peu avant le carrefour."""
        p = self.prog.prochaine()
        if not p or self.prog.hors_trace:
            return
        texte, d, _ = p
        cle = (round(self.prog.fait + d), texte)
        if d <= AVANCE_CONSIGNE.get(self.sport, 60) and cle != self.dite:
            self.dite = cle
            self._annoncer(f"Dans {arrondi(d).replace(' m', ' mètres').replace(' km', ' kilomètres')}, "
                           f"{texte[0].lower()}{texte[1:]}.")
