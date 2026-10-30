"""Couleurs et petits widgets communs aux écrans."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup

MINT, FOND, ENCRE = (0.20, 0.78, 0.55, 1), (0.07, 0.08, 0.09, 1), (0.05, 0.10, 0.08, 1)
CORAIL, GRIS, BLANC = (1, 0.35, 0.25, 1), (0.55, 0.58, 0.60, 1), (1, 1, 1, 1)
ARDOISE, JAUNE = (0.18, 0.20, 0.22, 1), (0.95, 0.75, 0.20, 1)


def bouton(texte, action, couleur=MINT, texte_couleur=ENCRE, hauteur=64, **kw):
    return Button(text=texte, font_size="20sp", bold=True, size_hint_y=None, height=dp(hauteur),
                  background_normal="", background_disabled_normal="", background_color=couleur,
                  color=texte_couleur, on_release=action, **kw)


def lab(texte, taille, couleur=BLANC, gras=False, **kw):
    l = Label(text=texte, font_size=f"{taille}sp", color=couleur, bold=gras, markup=True,
              halign="center", valign="middle", **kw)
    l.bind(size=lambda i, s: setattr(i, "text_size", s))
    return l


def confirmer(bouton_, texte, action):
    """Un premier appui arme le bouton (« texte »), le second lance l'action."""
    if getattr(bouton_, "arme", False):
        action()
    else:
        bouton_.arme, bouton_.text = True, texte


def choix(titre, message, options, hauteur=0.45):
    """Popup à boutons : options = [(texte, action, couleur, couleur_texte)]. Renvoie le popup."""
    boite = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
    boite.add_widget(lab(message, 20))
    ligne = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
    pop = Popup(title=titre, content=boite, size_hint=(0.92, hauteur), auto_dismiss=False,
                title_size="20sp")
    for texte, action, couleur, tc in options:
        ligne.add_widget(bouton(texte, lambda b, a=action: (pop.dismiss(), a()), couleur, tc))
    boite.add_widget(ligne)
    pop.open()
    return pop
