"""Icône Android et écran de lancement, dessinés depuis les courbes du logo (ui/logo.py).
  python logo/generer_png.py   (Pillow requis)"""
import os, sys

from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))
from ui.logo import DEPART, EPAISSEUR, RAYON, points  # noqa: E402

COBALT, BLANC, SIGNAL, CRAIE, ENCRE = "#2443E6", "#FFFFFF", "#C8F031", "#F4F6F8", "#0D1726"
SUR = 4  # dessin 4 fois plus grand puis réduit : bords lisses


def symbole(d, ox, oy, k, boucle, anneau):
    pts = [(ox + x * k, oy + y * k) for x, y in points(60)]
    e = EPAISSEUR * k
    for p in pts:  # disques le long du tracé : bouts et jointures arrondis
        d.ellipse([p[0] - e / 2, p[1] - e / 2, p[0] + e / 2, p[1] + e / 2], fill=boucle)
    x, y = ox + DEPART[0] * k, oy + DEPART[1] * k
    for r, c in ((RAYON + 0.8, anneau), (RAYON - 0.8, SIGNAL)):
        d.ellipse([x - r * k, y - r * k, x + r * k, y + r * k], fill=c)


def icone(taille=512):
    t = taille * SUR
    im = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, t - 1, t - 1], radius=t * 0.22, fill=COBALT)
    k = t * 0.72 / 48
    symbole(d, (t - 48 * k) / 2, (t - 48 * k) / 2, k, BLANC, COBALT)
    im.resize((taille, taille), Image.LANCZOS).save(os.path.join(ICI, "icone.png"))


def lancement(l=1080, h=1920):
    im = Image.new("RGB", (l * SUR // 2, h * SUR // 2), CRAIE)
    d = ImageDraw.Draw(im)
    k = im.width * 0.2 / 48
    police = ImageFont.truetype(os.path.join(os.path.dirname(ICI), "polices", "BarlowCondensed-ExtraBold.ttf"),
                                int(48 * k * 0.95))
    larg = 46 * k + d.textlength("Loopr", font=police)
    ox, oy = (im.width - larg) / 2, im.height / 2 - 24 * k
    symbole(d, ox, oy, k, COBALT, ENCRE)
    d.text((ox + 50 * k, oy + 41 * k), "Loopr", font=police, fill=ENCRE, anchor="ls")
    im.resize((l // 2, h // 2), Image.LANCZOS).save(os.path.join(ICI, "lancement.png"))


if __name__ == "__main__":
    icone()
    lancement()
