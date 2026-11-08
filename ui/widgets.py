"""Identité visuelle de Loopy (logo « la rose des boucles », palette Sauge & Pêche) : sauge pour la boucle,
pêche « signal » pour l'action à faire maintenant et le point de départ, encre vert forêt sur un fond lin
le jour, l'inverse la nuit.
Les pastels du logo (Sauge #A8C3B1, Pêche #F4BFA3) sont trop pâles sur fond clair (1,4 à 1,9:1) : le jour,
la boucle passe en sauge profonde et la pêche n'apparaît que sous de l'encre (texte, contour, anneau).
Contrastes visés pour le plein soleil : texte ≥ 5:1 partout, boucle ≥ 4:1 contre les rues et les chemins.
Chiffres en Barlow Condensed (dessinée d'après la signalisation routière : lisible d'un coup d'œil),
texte en Atkinson Hyperlegible (dessinée pour rester lisible quand on voit mal).
Mouvement : tout ce qui change glisse, se remplit ou se fond ; seules l'échelle, la position et
l'opacité sont animées, jamais la mise en page pendant une course."""
import os

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.graphics import Color, Line, PopMatrix, PushMatrix, Rectangle, RoundedRectangle, Scale
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as hexa, get_hex_from_color

# contrastes (WCAG) entre parenthèses : sur FOND, puis sur FOND_2
THEMES = {
    "jour": dict(FOND="#F4EFE6", FOND_2="#E5DDCF", ENCRE="#22322B",  # 11,8 · 10,0
                 BRUME="#4A5952",  # 6,5 · 5,5
                 ROUTE="#CCC3B3", CHEMIN="#C9B993",  # sable, pas vert : la boucle ne s'y fond pas
                 TRACE="#2F5643",  # sauge profonde : 7,2 · 6,2 ; 4,8 sur les rues, 4,3 sur les chemins
                 TRACE_PALE="#A8C3B1",  # sauge du logo, sous le trait encre de ce qui est fait
                 SIGNAL="#F4BFA3", SUR_SIGNAL="#22322B",  # encre sur pêche 8,2
                 MARQUE="#22322B",  # le symbole sur fond clair : encre, point pêche cerclé d'encre
                 ALERTE="#B3361F", SUR_ALERTE="#FFFFFF"),  # blanc sur rouge 6,1
    "nuit": dict(FOND="#121A16", FOND_2="#1F2A24", ENCRE="#EDF1EC",  # 15,5 · 13,0
                 BRUME="#9FAEA5",  # 7,7 · 6,4
                 ROUTE="#34413A", CHEMIN="#544C3B",
                 TRACE="#A8C3B1",  # 9,4 · 7,9 ; 5,7 sur les rues, 4,5 sur les chemins
                 TRACE_PALE="#3A5045",
                 SIGNAL="#F4BFA3", SUR_SIGNAL="#22322B",  # pêche sur fond 10,8
                 MARQUE="#A8C3B1",  # le symbole sur fond sombre : sauge, point pêche
                 ALERTE="#FF7A66", SUR_ALERTE="#121A16"),  # 6,9
}
# des listes modifiées sur place : changer de thème recolore tout ce qui est construit ensuite
FOND, FOND_2, ENCRE, BRUME, ROUTE, CHEMIN, TRACE, TRACE_PALE, SIGNAL, SUR_SIGNAL, MARQUE, ALERTE, SUR_ALERTE = \
    ([0.0, 0.0, 0.0, 1.0] for _ in range(13))
theme = "jour"


def appliquer_theme(nom):
    global theme
    theme = nom
    for cle, valeur in THEMES[nom].items():
        globals()[cle][:] = hexa(valeur)


appliquer_theme("jour")

POLICES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "polices")
# « Roboto » est la police par défaut de Kivy : la remplacer change tous les textes d'un coup
LabelBase.register("Roboto", os.path.join(POLICES, "AtkinsonHyperlegible-Regular.ttf"),
                   fn_bold=os.path.join(POLICES, "AtkinsonHyperlegible-Bold.ttf"))
LabelBase.register("Chiffres", os.path.join(POLICES, "BarlowCondensed-SemiBold.ttf"),
                   fn_bold=os.path.join(POLICES, "BarlowCondensed-ExtraBold.ttf"))


def hexa_de(couleur):
    """Pour le markup [color=…]."""
    return get_hex_from_color(couleur)[:7]


def nombre(x, decimales=1):
    """Nombre à la française : virgule décimale."""
    return f"{x:.{decimales}f}".replace(".", ",")


def unite(texte, taille):
    """Unité en texte courant, collée au chiffre qui la précède (markup)."""
    return f"[font=Roboto][b][size={taille}sp] {texte}[/size][/b][/font]"


def fond(widget, couleur, rayon=0):
    """Fond plein qui suit le widget. Renvoie l'instruction Color, pour changer la teinte."""
    with widget.canvas.before:
        c = Color(*couleur)
        r = RoundedRectangle(radius=[rayon]) if rayon else Rectangle()
    widget.bind(pos=lambda w, v: setattr(r, "pos", v), size=lambda w, v: setattr(r, "size", v))
    return c


def lab(texte, taille, couleur=None, gras=False, chiffres=False, aligne="left", **kw):
    l = Label(text=texte, font_size=f"{taille}sp", color=couleur or ENCRE, bold=gras, markup=True,
              font_name="Chiffres" if chiffres else "Roboto", halign=aligne, **{"valign": "middle", **kw})
    l.bind(size=lambda i, s: setattr(i, "text_size", s))
    return l


# --- mouvement ---
def echelle(w):
    """Instruction Scale autour du widget (créée au premier appel), centrée sur lui."""
    if not hasattr(w, "_echelle"):
        with w.canvas.before:
            PushMatrix()
            w._echelle = Scale(1, 1, 1)
        with w.canvas.after:
            PopMatrix()

        def centrer(*_):
            w._echelle.origin = w.center
        w.bind(pos=centrer, size=centrer)
        centrer()
    return w._echelle


def pulser(w, k=1.08, d=0.45):
    """Petit battement : pour un kilomètre franchi, une valeur réglée."""
    sc = echelle(w)
    Animation.cancel_all(sc)
    sc.xyz = (k, k, 1)
    Animation(xyz=(1, 1, 1), d=d, t="out_back").start(sc)


def apparaitre(w, d=0.28, depuis=0.94):
    """Entrée d'un élément : il se fond et grandit légèrement jusqu'à sa taille."""
    sc = echelle(w)
    Animation.cancel_all(w, "opacity")
    Animation.cancel_all(sc)
    w.opacity, sc.xyz = 0, (depuis, depuis, 1)
    Animation(opacity=1, d=d, t="out_cubic").start(w)
    Animation(xyz=(1, 1, 1), d=d, t="out_back").start(sc)


def teinter(couleur_instr, rgba, d=0.2):
    Animation.cancel_all(couleur_instr)
    Animation(rgba=list(rgba), d=d, t="out_quad").start(couleur_instr)


# fond, texte, bord : un style par rôle, pas un bouton générique recoloré au cas par cas
def style(nom):
    return {
        "encre": (ENCRE, FOND, None),  # action courante
        # l'action à faire maintenant (une seule par écran) ; le contour encre détache la pêche du fond lin
        "signal": (SIGNAL, SUR_SIGNAL, SUR_SIGNAL),
        "alerte": (ALERTE, SUR_ALERTE, None),  # action destructrice armée
        "contour": (FOND, ENCRE, ENCRE),  # action secondaire
        "fond": (FOND, ENCRE, None),  # posé sur un panneau en négatif
        "carte": ((*FOND[:3], 0.94), ENCRE, FOND_2),  # posé sur la carte
        "discret": ((*FOND[:3], 0), ENCRE, None),  # navigation
        "selection": ((*ENCRE[:3], 0), FOND, None),  # option retenue, sur le curseur d'un Segmente
    }[nom]


class Bouton(ButtonBehavior, Label):
    """Un appui se sent : le bouton s'enfonce (échelle 0,96) et se teinte, puis rebondit au relâcher.
    Un changement de rôle (style) fond d'une couleur à l'autre."""
    style = StringProperty("encre")

    def __init__(self, texte, action=None, style="encre", hauteur=64, taille=19, **kw):
        reglages = dict(size_hint_y=None, height=dp(hauteur), font_size=f"{taille}sp", bold=True,
                        markup=True, halign="center", valign="middle")
        reglages.update(kw)
        super().__init__(text=texte, **reglages)
        echelle(self)  # avant le fond : le fond s'enfonce avec le texte
        with self.canvas.before:
            self._c_fond = Color(0, 0, 0, 0)
            self._fond = RoundedRectangle(radius=[dp(12)])
            self._c_bord = Color(0, 0, 0, 0)
            self._bord = Line(width=dp(1.4))
        self.bind(pos=self._placer, size=self._placer, state=self._appui, disabled=self._peindre,
                  style=self._peindre)
        self.style = style
        self._placer()
        self._peindre(d=0)
        if action:
            self.bind(on_release=action)

    def _placer(self, *_):
        self.text_size = self.size
        self._fond.pos, self._fond.size = self.pos, self.size
        self._bord.rounded_rectangle = (self.x + dp(0.7), self.y + dp(0.7), self.width - dp(1.4),
                                        self.height - dp(1.4), dp(12))

    def _peindre(self, *_, d=0.2):
        couleur, texte, bord = style(self.style)
        if self.state == "down":  # le fond fonce (ou se teinte s'il est clair)
            if couleur[3] < 0.5:  # bouton sans fond : un voile de la couleur du texte
                couleur = (*texte[:3], 0.12)
            else:
                couleur = FOND_2 if couleur is FOND else [v * 0.84 for v in couleur[:3]] + [1]
        self.color = self.disabled_color = texte
        bord = bord or (*couleur[:3], 0)
        if d:
            teinter(self._c_fond, couleur, d)
            teinter(self._c_bord, bord, d)
        else:
            self._c_fond.rgba, self._c_bord.rgba = couleur, bord
        Animation.cancel_all(self, "opacity")
        Animation(opacity=0.35 if self.disabled else 1, d=d or 0.01).start(self)

    def _appui(self, *_):
        sc = echelle(self)
        Animation.cancel_all(sc)
        if self.state == "down":
            Animation(xyz=(0.96, 0.96, 1), d=0.08, t="out_quad").start(sc)
        else:
            Animation(xyz=(1, 1, 1), d=0.35, t="out_back").start(sc)
        self._peindre(d=0.08)


def confirmer(bouton, texte, action):
    """Un premier appui arme le bouton (rouge, « texte ») pendant 4 s, le second lance l'action."""
    if getattr(bouton, "arme", False):
        desarmer(bouton)
        action()
        return
    bouton.arme, bouton.avant = True, (bouton.text, bouton.style)
    bouton.text, bouton.style = texte, "alerte"
    pulser(bouton, 1.04)
    Clock.schedule_once(lambda dt: desarmer(bouton), 4)


def desarmer(bouton):
    if getattr(bouton, "arme", False):
        bouton.arme = False
        bouton.text, bouton.style = bouton.avant


class Pas(BoxLayout):
    """Réglage au pouce : − valeur +. Rester appuyé fait défiler. Pas de clavier en tenue de course."""
    valeur = NumericProperty(0)

    def __init__(self, nom, symbole, valeur, pas, mini, maxi, decimales=0, **kw):
        super().__init__(size_hint_y=None, height=dp(64), spacing=dp(10), **kw)
        self.symbole, self.pas, self.mini, self.maxi, self.decimales = symbole, pas, mini, maxi, decimales
        self.add_widget(lab(nom, 17, BRUME, size_hint_x=0.8))
        self.l_val = lab("", 40, gras=True, chiffres=True, aligne="center", size_hint_x=1.3)
        for signe, sens in (("−", -1), (None, 0), ("+", 1)):
            if signe is None:
                self.add_widget(self.l_val)
                continue
            b = Bouton(signe, style="contour", hauteur=56, taille=28, size_hint_x=None, width=dp(56),
                       pos_hint={"center_y": 0.5})
            b.bind(on_press=lambda b, s=sens: self._appui(s), on_release=lambda b: self._lacher())
            self.add_widget(b)
        self.valeur = valeur
        self.on_valeur()

    def _appui(self, sens):
        self.changer(sens)
        self._sens = sens
        Clock.schedule_once(self._defiler, 0.45)

    def _defiler(self, dt):
        Clock.schedule_interval(self._repeter, 0.08)

    def _repeter(self, dt):
        self.changer(self._sens)

    def _lacher(self):
        Clock.unschedule(self._defiler)
        Clock.unschedule(self._repeter)

    def changer(self, sens):
        avant = self.valeur
        self.valeur = round(min(self.maxi, max(self.mini, self.valeur + sens * self.pas)), 3)
        if sens and self.valeur == avant:  # butée : la valeur refuse d'aller plus loin
            pulser(self.l_val, 0.94, 0.3)

    def borner(self, mini=None, maxi=None):
        self.mini = self.mini if mini is None else mini
        self.maxi = self.maxi if maxi is None else maxi
        self.changer(0)

    def on_valeur(self, *_):
        self.l_val.text = f"{nombre(self.valeur, self.decimales)}{unite(self.symbole, 16)}"
        if hasattr(self, "_sens"):
            pulser(self.l_val, 1.06, 0.25)

    @property
    def text(self):
        return str(self.valeur)


class Segmente(BoxLayout):
    """Choix exclusif : un curseur plein glisse sous l'option retenue."""
    choix = StringProperty("")

    def __init__(self, options, choix, hauteur=52, **kw):
        super().__init__(size_hint_y=None, height=dp(hauteur), spacing=dp(4), padding=dp(4), **kw)
        with self.canvas.before:
            Color(*FOND_2)
            self._rail = RoundedRectangle(radius=[dp(14)])
            Color(*ENCRE)
            self._curseur = RoundedRectangle(radius=[dp(11)])
        self.boutons = {}
        for valeur, texte in options:
            b = Bouton(texte, lambda b, v=valeur: setattr(self, "choix", v), "discret", hauteur - 8, 17)
            self.boutons[valeur] = b
            self.add_widget(b)
        self.bind(pos=self._placer, size=self._placer, choix=self._glisser)
        self.choix = choix

    def _cible(self):
        b = self.boutons[self.choix]
        return b.pos, b.size

    def _placer(self, *_):
        self._rail.pos, self._rail.size = self.pos, self.size
        Clock.schedule_once(lambda dt: self._glisser(d=0))  # après la mise en place des boutons

    def _glisser(self, *_, d=0.26):
        pos, taille = self._cible()
        Animation.cancel_all(self._curseur)
        if d:
            Animation(pos=pos, size=taille, d=d, t="out_cubic").start(self._curseur)
        else:
            self._curseur.pos, self._curseur.size = pos, taille
        for v, b in self.boutons.items():
            b.style = "selection" if v == self.choix else "discret"


class Bande(BoxLayout):
    """Avancement sur la boucle : un filet sauge qui se remplit en douceur, km restants et pourcentage.
    En alerte (hors du parcours), la bande vire au rouge."""
    part = NumericProperty(0)
    alerte = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(46),
                         padding=[dp(20), dp(10), dp(20), dp(2)], **kw)
        self._part = 0
        with self.canvas.before:
            self._c_fond = Color(*FOND)
            self._fond = Rectangle()
            Color(*FOND_2)
            self._rail = Rectangle()
            self._c_plein = Color(*TRACE)
            self._plein = Rectangle()
        ligne = BoxLayout()
        self.gauche = lab("", 16, gras=True)
        self.droite = lab("", 16, BRUME, gras=True, aligne="right")
        ligne.add_widget(self.gauche)
        ligne.add_widget(self.droite)
        self.add_widget(ligne)
        self.bind(pos=self._maj, size=self._maj, alerte=self._alerte)

    def on_part(self, *_):
        Animation.cancel_all(self, "_affiche")
        Animation(_affiche=max(0, min(1, self.part)), d=0.45, t="out_cubic").start(self)

    _affiche = NumericProperty(0)

    def on__affiche(self, *_):
        self._maj()

    def _maj(self, *_):
        self._fond.pos, self._fond.size = self.pos, self.size
        haut = self.top - dp(5)
        self._rail.pos, self._rail.size = (self.x, haut), (self.width, dp(5))
        self._plein.pos, self._plein.size = (self.x, haut), (self.width * self._affiche, dp(5))

    def _alerte(self, *_):
        teinter(self._c_fond, ALERTE if self.alerte else FOND, 0.25)
        teinter(self._c_plein, (*TRACE[:3], 0 if self.alerte else 1), 0.25)
        for l in (self.gauche, self.droite):
            l.color = SUR_ALERTE if self.alerte else (ENCRE if l is self.gauche else BRUME)
        if self.alerte:
            pulser(self.gauche, 1.06)


class Feuille(ModalView):
    """Feuille qui monte du bas de l'écran, à portée de pouce, et y redescend quand on la ferme."""

    def __init__(self, titre, hauteur, **kw):
        super().__init__(size_hint=(1, None), height=hauteur, pos_hint={"x": 0, "y": 0},
                         background="", background_color=(0, 0, 0, 0),
                         overlay_color=(0.03, 0.05, 0.09, 0.6), auto_dismiss=False, **kw)
        self.boite = BoxLayout(orientation="vertical", padding=[dp(20), dp(14), dp(20), dp(20)],
                               spacing=dp(12))
        with self.boite.canvas.before:
            Color(*FOND)
            r = RoundedRectangle(radius=[dp(22), dp(22), 0, 0])
            Color(*FOND_2)
            poignee = RoundedRectangle(radius=[dp(2)])

        def suivre(w, *_):
            r.pos, r.size = w.pos, (w.width, w.height + dp(40))  # déborde en bas pendant le rebond
            poignee.pos, poignee.size = (w.center_x - dp(20), w.top - dp(10)), (dp(40), dp(4))
        self.boite.bind(pos=suivre, size=suivre)
        self.boite.add_widget(lab(titre, 22, gras=True, size_hint_y=None, height=dp(40)))
        self.add_widget(self.boite)

    def ajouter(self, w):
        self.boite.add_widget(w)

    def ouvrir(self):
        self.open()
        self.boite.y = -self.height  # elle monte : on voit d'où elle vient
        Animation(y=0, d=0.38, t="out_back").start(self.boite)

    def fermer(self, ensuite=None):
        a = Animation(y=-self.height, d=0.22, t="in_cubic")
        a.bind(on_complete=lambda *_: (self.dismiss(), ensuite and ensuite()))
        a.start(self.boite)


def choix(titre, message, options, hauteur=dp(300)):
    """Feuille à boutons : options = [(texte, action, style)]. Renvoie la feuille."""
    f = Feuille(titre, hauteur)
    f.ajouter(lab(message, 18))
    ligne = BoxLayout(size_hint_y=None, height=dp(68), spacing=dp(10))
    for texte, action, style_ in options:
        ligne.add_widget(Bouton(texte, lambda b, a=action: f.fermer(a), style_, 68))
    f.ajouter(ligne)
    f.ouvrir()
    return f


class Croissance(Widget):
    """Base des graphiques : les barres poussent depuis leur base à l'affichage."""
    pousse = NumericProperty(1)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self.dessiner, size=self.dessiner, pousse=self.dessiner)

    def faire_pousser(self, d=0.7):
        Animation.cancel_all(self, "pousse")
        self.pousse = 0
        Animation(pousse=1, d=d, t="out_cubic").start(self)

    def dessiner(self, *_):
        pass


class Barre(Croissance):
    def __init__(self, part, couleur, **kw):
        super().__init__(**kw)
        self.part, self.couleur = part, couleur

    def dessiner(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*self.couleur)
            RoundedRectangle(pos=(self.x, self.center_y - dp(6)), size=(self.width * self.part * self.pousse, dp(12)),
                             radius=[dp(4)])


class Splits(BoxLayout):
    """Un km par ligne : barre d'autant plus longue que le km est rapide, le meilleur en sauge.
    Les barres s'allongent l'une après l'autre."""

    def __init__(self, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(4), **kw)
        self.bind(minimum_height=self.setter("height"))

    def remplir(self, splits):
        from course import fmt_allure
        self.clear_widgets()
        vit = [1000 / s for s in splits if s > 0]
        if not vit:
            self.add_widget(lab("Pas encore de kilomètre complet", 16, BRUME, size_hint_y=None, height=dp(30)))
            return
        lo, hi = min(vit), max(vit)
        for i, v in enumerate(vit, 1):
            ligne = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(10))
            ligne.add_widget(lab(f"km {i}", 18, BRUME, chiffres=True, size_hint_x=None, width=dp(44)))
            part = 0.3 + 0.7 * ((v - lo) / (hi - lo) if hi > lo else 1)
            barre = Barre(part, TRACE if v == hi and len(vit) > 1 else (*BRUME[:3], 0.45))
            barre.pousse = 0
            ligne.add_widget(barre)
            ligne.add_widget(lab(fmt_allure(v), 22, gras=True, chiffres=True, aligne="right",
                                 size_hint_x=None, width=dp(54)))
            self.add_widget(ligne)
            Clock.schedule_once(lambda dt, b=barre: b.faire_pousser(0.5), 0.15 + 0.06 * i)


# --- navigation, saisie, listes ---
class Nav(BoxLayout):
    """Barre du bas : les cinq destinations de l'app. L'onglet courant porte un filet sauge et passe en gras."""
    ONGLETS = (("accueil", "Accueil"), ("sport", "Créer"), ("historique", "Historique"),
               ("communaute", "Communauté"), ("profil", "Profil"))
    GROUPES = {"distance": "sport", "plan": "sport", "detail": "historique"}

    def __init__(self, aller, **kw):
        super().__init__(size_hint_y=None, height=dp(62), padding=[dp(4), 0], **kw)
        with self.canvas.before:
            Color(*FOND)
            self._fond = Rectangle()
            Color(*FOND_2)
            self._filet = Rectangle()
            self._c_marque = Color(*TRACE)
            self._marque = RoundedRectangle(radius=[0, 0, dp(2), dp(2)])
        self.boutons = {}
        for nom, texte in self.ONGLETS:
            b = Bouton(texte, lambda b, n=nom: aller(n), "discret", 62, 13)
            b.bold = False
            self.boutons[nom] = b
            self.add_widget(b)
        self.bind(pos=self._maj, size=self._maj)
        self.courant = "accueil"

    def _maj(self, *_):
        self._fond.pos, self._fond.size = self.pos, self.size
        self._filet.pos, self._filet.size = (self.x, self.top - dp(1)), (self.width, dp(1))
        b = self.boutons.get(self.courant)
        if b:
            Animation.cancel_all(self._marque)
            Animation(pos=(b.x + dp(14), self.top - dp(3)), size=(b.width - dp(28), dp(3)), d=0.25,
                      t="out_cubic").start(self._marque)

    def montrer(self, ecran):
        self.courant = self.GROUPES.get(ecran, ecran)
        for nom, b in self.boutons.items():
            b.bold = nom == self.courant
            b.color = ENCRE if nom == self.courant else BRUME
        Clock.schedule_once(self._maj)


def champ(indice="", texte="", motdepasse=False, nombre_=False, **kw):
    """Zone de saisie aux couleurs de l'app."""
    from kivy.uix.textinput import TextInput
    reglages = dict(text=texte, hint_text=indice, password=motdepasse, multiline=False, write_tab=False,
                    size_hint_y=None, height=dp(52), font_size="18sp", padding=[dp(14), dp(14)],
                    background_normal="", background_active="", background_color=FOND_2,
                    foreground_color=ENCRE, hint_text_color=(*BRUME[:3], 0.8), cursor_color=TRACE,
                    input_filter="float" if nombre_ else None)
    reglages.update(kw)
    return TextInput(**reglages)


class Repartition(Widget):
    """Barre empilée : parts d'un total (types de voies, revêtement). valeurs = [(part, couleur)]."""

    def __init__(self, **kw):
        super().__init__(size_hint_y=None, height=dp(10), **kw)
        self.valeurs = []
        self.bind(pos=self.dessiner, size=self.dessiner)

    def remplir(self, valeurs):
        self.valeurs = valeurs
        self.dessiner()

    def dessiner(self, *_):
        self.canvas.clear()
        total = sum(v for v, _ in self.valeurs) or 1
        x = self.x
        with self.canvas:
            Color(*FOND_2)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(5)])
            for v, c in self.valeurs:
                w = self.width * v / total
                Color(*c)
                Rectangle(pos=(x, self.y), size=(w, self.height))
                x += w


def liste_defilante(espacement=0):
    """(ScrollView, contenu) : un contenu vertical qui prend la hauteur de ce qu'il contient."""
    from kivy.uix.scrollview import ScrollView
    sv = ScrollView(do_scroll_x=False)
    contenu = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(espacement))
    contenu.bind(minimum_height=contenu.setter("height"))
    sv.add_widget(contenu)
    return sv, contenu


def titre_ecran(texte, retour=None):
    """Barre de titre : retour éventuel à gauche, titre en Barlow."""
    b = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(6), padding=[dp(12), dp(4), dp(20), 0])
    if retour:
        b.add_widget(Bouton("‹ Retour", retour, "discret", 52, 17, size_hint_x=None, width=dp(100)))
    b.titre = lab(texte, 30, gras=True, chiffres=True)
    b.add_widget(b.titre)
    return b
