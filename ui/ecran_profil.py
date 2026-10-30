"""Écran 3 : l'historique des courses, et le détail d'une course (trace, splits, export GPX)."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from course import fmt_allure, fmt_temps
from gpx import exportable, gpx
from ui.carte import Trace, avec_zoom
from ui.ecran_course import texte_splits
from ui.widgets import ARDOISE, BLANC, CORAIL, GRIS, MINT, bouton, confirmer, lab


def allure_moy(act):
    return fmt_allure(act["distance"] / act["duree"]) if act.get("duree") else "--:--"


class EcranProfil(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="profil", **kw)
        self.app = app
        col = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        self.l_totaux = lab("", 22, MINT, True, size_hint_y=None, height=dp(70))
        self.liste = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.liste.bind(minimum_height=self.liste.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.liste)
        for w in (self.l_totaux, sv, bouton("Retour", lambda *_: setattr(app.sm, "current", "plan"))):
            col.add_widget(w)
        self.add_widget(col)
        self.bind(on_pre_enter=self.remplir)

    def remplir(self, *_):
        acts = self.app.stockage.lister()
        km = sum(a["distance"] for a in acts) / 1000
        temps = sum(a.get("duree") or 0 for a in acts)
        dplus = sum(a.get("denivele") or 0 for a in acts)
        self.l_totaux.text = (f"{len(acts)} courses   {km:.1f} km\n"
                              f"[size=16sp]{fmt_temps(temps)}   D+ {dplus:.0f} m[/size]")
        self.liste.clear_widgets()
        for a in acts:
            self.liste.add_widget(Button(
                text=f"{a['date']}\n{a['distance'] / 1000:.2f} km   {fmt_temps(a['duree'])}   {allure_moy(a)} /km",
                font_size="18sp", size_hint_y=None, height=dp(72), halign="center",
                background_normal="", background_color=ARDOISE, color=BLANC,
                on_release=lambda b, id_=a["id"]: self.app.ecran_detail.ouvrir(id_)))


class EcranDetail(Screen):
    def __init__(self, app, **kw):
        super().__init__(name="detail", **kw)
        self.app, self.act = app, None
        col = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        self.l_titre = lab("", 20, MINT, True, size_hint_y=None, height=dp(80))
        self.trace = Trace()
        self.l_splits = lab("", 16, GRIS, size_hint_y=None, height=dp(110))
        self.l_info = lab("", 14, GRIS, size_hint_y=None, height=dp(40))
        self.btn_gpx = bouton("Exporter GPX", self.exporter)
        bas = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        self.btn_suppr = bouton("Supprimer", self.supprimer, CORAIL, BLANC)
        bas.add_widget(self.btn_suppr)
        bas.add_widget(bouton("Retour", lambda *_: setattr(app.sm, "current", "profil"), ARDOISE, BLANC))
        for w in (self.l_titre, avec_zoom(self.trace), self.l_splits, self.l_info, self.btn_gpx, bas):
            col.add_widget(w)
        self.add_widget(col)

    def ouvrir(self, id_):
        a = self.act = self.app.stockage.charger(id_)
        self.l_titre.text = (f"{a['date']}\n{a['distance'] / 1000:.2f} km   {fmt_temps(a['duree'])}   "
                             f"{allure_moy(a)} /km   D+ {a.get('denivele') or 0:.0f} m")
        pts = [(p[1], p[2]) for seg in a.get("segments") or () for p in seg] or a.get("trace") or []
        pas = max(1, len(pts) // 1500)
        self.trace.coords = [tuple(p) for p in pts[::pas]]
        splits = texte_splits(a.get("splits") or ())
        self.l_splits.text = "   ".join(splits.split("\n")) if splits else ""
        self.btn_gpx.disabled = not exportable(a)
        self.l_info.text = "" if exportable(a) else "Ancienne course, sans heure par point : pas d'export"
        self.btn_suppr.arme, self.btn_suppr.text = False, "Supprimer"
        self.app.sm.current = "detail"

    def exporter(self, *_):
        a = self.act
        try:
            self.l_info.text = self.app.exporter_gpx(f"starva-{a['id']}.gpx", gpx(a))
        except Exception as err:
            self.l_info.text = f"Export impossible : {err}"

    def supprimer(self, btn):
        def go():
            self.app.stockage.supprimer(self.act["id"])
            self.app.sm.current = "profil"
        confirmer(btn, "Supprimer ? Touche encore", go)
