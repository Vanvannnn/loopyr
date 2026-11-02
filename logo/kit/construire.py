"""Construit le kit du logo Loopy (« la rose des boucles », palette Sauge & Pêche) en contours pleins.

Trois boucles de longueurs différentes partent du même point de départ. Chaque boucle est une goutte
(pointe au départ, cercle au bout) dont le demi-angle vaut 30° : toutes les tangentes tombent sur des
multiples de 15°. Les traits sont convertis en contours avec skia-pathops ; aucun trait, police ni
transformation ne reste dans les fichiers.

Mêmes valeurs que ui/logo.py, qui dessine le symbole animé dans l'app.

Outil de dev, pas une dépendance de l'app :  pip install skia-pathops fonttools cairosvg pillow
    python logo/kit/construire.py
"""
import io
import math
import os

import cairosvg
from fontTools.pens.svgPathPen import SVGPathPen
from pathops import LineCap, LineJoin, Path, PathOp, op
from PIL import Image

ICI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.dirname(ICI)
SVG = os.path.join(ICI, "svg")
ICONES = os.path.join(ICI, "icones")
PNG = os.path.join(ICONES, "png")

SAUGE, PECHE, ENCRE, LIN = "#A8C3B1", "#F4BFA3", "#22322B", "#F4EFE6"
NOIR, BLANC = "#000000", "#FFFFFF"

# (angle de la boucle en degrés, distance pointe → centre du bout, rayon du bout) ; y vers le bas
ROSE = dict(trait=15, boucles=((-105, 84, 42), (15, 64, 32), (150, 48, 24)), ecart=21, point=10.5)
# coupe petites tailles (16 à 24 px) : trait plus gras, petite boucle agrandie, départ plus dégagé
ROSE_PETITE = dict(trait=23, boucles=((-105, 80, 40), (15, 68, 34), (150, 58, 29)), ecart=28, point=14)


# --- primitives ---

def _arc(p, cx, cy, r, a0, a1, move=False):
    """Arc en cubiques (≤ 90° chacune), angles en degrés."""
    n = max(1, math.ceil(abs(a1 - a0) / 90 - 1e-9))
    step = math.radians(a1 - a0) / n
    a = math.radians(a0)
    if move:
        p.moveTo(cx + r * math.cos(a), cy + r * math.sin(a))
    h = 4 / 3 * math.tan(step / 4)
    for _ in range(n):
        b = a + step
        p.cubicTo(cx + r * (math.cos(a) - h * math.sin(a)), cy + r * (math.sin(a) + h * math.cos(a)),
                  cx + r * (math.cos(b) + h * math.sin(b)), cy + r * (math.sin(b) - h * math.cos(b)),
                  cx + r * math.cos(b), cy + r * math.sin(b))
        a = b


def cercle(cx, cy, r):
    p = Path()
    _arc(p, cx, cy, r, 0, 360, move=True)
    p.close()
    return p


def union(*ps):
    out = ps[0]
    for q in ps[1:]:
        out = op(out, q, PathOp.UNION)
    return out


def trait(chemin, w):
    """Chemin ouvert ou fermé → contour plein de graisse w, bouts et jointures ronds."""
    chemin.stroke(w, LineCap.ROUND_CAP, LineJoin.ROUND_JOIN, 4)
    chemin.convertConicsToQuads()
    chemin.simplify()
    return chemin


def goutte(p, ang, d, r):
    """Boucle en goutte depuis l'origine : pointe au départ, tour d'un cercle de rayon r à distance d."""
    a = math.radians(ang)
    cx, cy = d * math.cos(a), d * math.sin(a)
    beta = math.degrees(math.acos(r / d))
    a0, a1 = ang + 180 + beta, ang + 180 - beta + 360
    p.moveTo(0, 0)
    p.lineTo(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    _arc(p, cx, cy, r, a0, a1)
    p.close()


def d_attr(p):
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    p.draw(pen)
    return pen.getCommands()


def bouge(p, s, dx, dy):
    return p.transform(s, 0, 0, s, dx, dy)


# --- le symbole et le nom ---

def symbole(coupe=ROSE):
    """Les trois boucles, ouvertes autour du départ. Renvoie (forme, (cx, cy, r) du point de départ)."""
    p = Path()
    for b in coupe["boucles"]:
        goutte(p, *b)
    forme = op(trait(p, coupe["trait"]), cercle(0, 0, coupe["ecart"]), PathOp.DIFFERENCE)
    return forme, (0.0, 0.0, coupe["point"])


GRAISSE_NOM = 13


def _ovale(cx, cy, rx, ry):
    q = cercle(0, 0, 1)
    return q.transform(rx, 0, 0, ry, cx, cy)


RX, RY = 21, 23.5  # demi-axes des panses (axe du trait), un peu condensées


def _p(p, x):
    sx = x + GRAISSE_NOM / 2
    p.moveTo(sx, 40); p.lineTo(sx, 128)
    p.addPath(_ovale(sx + RX, 70, RX, RY))
    return x + 2 * RX + GRAISSE_NOM


def _crochet(p, sx, haut):
    """Fût qui finit en crochet vers l'avant, comme une foulée."""
    p.moveTo(sx, haut); p.lineTo(sx, 84); p.cubicTo(sx, 96, sx + 6, 101, sx + 16, 101)
    return sx + 16 + GRAISSE_NOM / 2


def _l(p, x):
    return _crochet(p, x + GRAISSE_NOM / 2, 6)


def _o(p, x):
    p.addPath(_ovale(x + GRAISSE_NOM / 2 + RX, 70, RX, RY))
    return x + 2 * RX + GRAISSE_NOM


def _y(p, x):
    """y en u, dont la queue fait une boucle et repart vers l'avant : le nom finit comme le symbole."""
    xl = x + GRAISSE_NOM / 2
    xr = xl + 2 * RX
    q = Path()
    q.moveTo(-1, -30 / RY); q.lineTo(-1, 0)
    _arc(q, 0, 0, 1, 180, 0)
    p.addPath(q.transform(RX, 0, 0, RY, xl + RX, 70))
    p.moveTo(xr, 40); p.lineTo(xr, 108)
    p.cubicTo(xr, 150, xr - 46, 166, xr - 50, 138)    # descend et tourne à gauche…
    p.cubicTo(xr - 54, 110, xr - 8, 104, xr + 22, 128)  # …remonte en croisant le fût et repart
    return xr + 22 + GRAISSE_NOM / 2


# (lettre, espace avant elle) : l'approche est réglée à l'œil, plus serrée entre deux rondes
NOM = ((_l, 0), (_o, 7), (_o, 10), (_p, 10), (_y, 10))


def lettrage():
    """« loopy » en minuscules monolignes, un peu condensées ; le l finit en crochet, comme une foulée, et la
    queue du y fait une boucle. Hauteur d'x 60 (y 40 → 100), hampe en 6, jambage vers 128."""
    p = Path()
    x = 0
    for glyphe, approche in NOM:
        x = glyphe(p, x + approche)
    return trait(p, GRAISSE_NOM)


# --- couleurs ---

# fond prévu, couleur du symbole, (point, cœur du point ou None), couleur du nom
VARIANTES = {
    "couleur-clair": (LIN, ENCRE, (ENCRE, PECHE), ENCRE),   # fonds clairs : Lin, blanc, Sauge
    "encre": (LIN, ENCRE, (ENCRE, None), ENCRE),            # une couleur sur fond clair ou pastel
    "sombre": (ENCRE, SAUGE, (PECHE, None), SAUGE),         # fond Encre : pastel + point pêche
    "noir": (BLANC, NOIR, (NOIR, None), NOIR),
    "blanc": (NOIR, BLANC, (BLANC, None), BLANC),
}
CŒUR = 0.6  # rayon du cœur pêche dans le point cerclé d'encre


def depart(cx, cy, r, couleurs):
    plein, coeur = couleurs
    s = f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{plein}"/>'
    if coeur:
        s += f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r * CŒUR:.2f}" fill="{coeur}"/>'
    return s


def svg(vb, corps, titre="Loopy"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img"><title>{titre}</title>\n'
            f'{corps}\n</svg>\n')


def ecrire(chemin, contenu):
    with open(chemin, "w") as f:
        f.write(contenu)


def place(forme, pt, s, dx, dy):
    return bouge(forme, s, dx, dy), (pt[0] * s + dx, pt[1] * s + dy, pt[2] * s)


def cadre(coupe, taille, zone):
    """Symbole centré dans un carré, relevé de 1 % (centre optique). zone : part du côté occupée."""
    forme, pt = symbole(coupe)
    x0, y0, x1, y1 = forme.bounds
    s = taille * zone / max(x1 - x0, y1 - y0)
    return place(forme, pt, s, taille / 2 - s * (x0 + x1) / 2, taille / 2 - s * (y0 + y1) / 2 - taille * 0.01)


def dessin(forme, pt, coul, coul_pt):
    return f'<path fill="{coul}" d="{d_attr(forme)}"/>\n' + depart(*pt, coul_pt)


# --- mise en page ---

S_SYM = 0.95     # échelle du symbole face au nom : traits optiquement égaux (15 × 0,95 ≈ 13 × 1,1)
ESPACE = 44      # entre symbole et nom, en unités du nom
HAUTEUR_X = 60   # zone de protection = une hauteur d'x du nom


def lockups():
    nom = lettrage()
    forme, pt = symbole()
    sx0, sy0, sx1, sy1 = forme.bounds
    nx0, ny0, nx1, ny1 = nom.bounds
    m = HAUTEUR_X

    # horizontal : symbole centré sur la hauteur hampe → ligne de base du nom (y 6 → 100)
    hs = (sy1 - sy0) * S_SYM
    f_h, p_h = place(forme, pt, S_SYM, m - sx0 * S_SYM, 53 - hs / 2 - sy0 * S_SYM)
    n_dx = m + (sx1 - sx0) * S_SYM + ESPACE - nx0
    hy0 = min(f_h.bounds[1], ny0) - m
    hy1 = max(f_h.bounds[3], ny1) + m
    n_h = bouge(nom, 1, n_dx, 0)
    vb_h = f"0 {hy0:.1f} {n_dx + nx1 + m:.1f} {hy1 - hy0:.1f}"

    # empilé : symbole au-dessus, nom centré dessous
    ln = nx1 - nx0
    ls = (sx1 - sx0) * S_SYM * 1.6
    larg = max(ln, ls) + 2 * m
    f_e, p_e = place(forme, pt, S_SYM * 1.6, larg / 2 - (sx0 + sx1) / 2 * S_SYM * 1.6, m - sy0 * S_SYM * 1.6)
    y_nom = f_e.bounds[3] + 34 - ny0
    n_e = bouge(nom, 1, larg / 2 - (nx0 + nx1) / 2, y_nom)
    vb_e = f"0 0 {larg:.1f} {n_e.bounds[3] + m:.1f}"

    vb_l = f"{nx0 - m:.1f} {ny0 - m:.1f} {ln + 2 * m:.1f} {ny1 - ny0 + 2 * m:.1f}"
    return (f_h, p_h, n_h, vb_h), (f_e, p_e, n_e, vb_e), (nom, vb_l)


def construire():
    for dossier in (SVG, ICONES, PNG):
        os.makedirs(dossier, exist_ok=True)
    sym = cadre(ROSE, 256, 0.78)
    petit = cadre(ROSE_PETITE, 256, 0.86)
    (f_h, p_h, n_h, vb_h), (f_e, p_e, n_e, vb_e), (nom, vb_l) = lockups()

    for v, (_, c_sym, c_pt, c_nom) in VARIANTES.items():
        ecrire(os.path.join(SVG, f"loopy-symbole-{v}.svg"), svg("0 0 256 256", dessin(*sym, c_sym, c_pt)))
        # en petit, le cœur pêche ferait moins d'un pixel : point plein
        ecrire(os.path.join(SVG, f"loopy-symbole-petit-{v}.svg"),
               svg("0 0 256 256", dessin(*petit, c_sym, (c_pt[0], None))))
        ecrire(os.path.join(SVG, f"loopy-lettrage-{v}.svg"), svg(vb_l, f'<path fill="{c_nom}" d="{d_attr(nom)}"/>'))
        ecrire(os.path.join(SVG, f"loopy-horizontal-{v}.svg"),
               svg(vb_h, dessin(f_h, p_h, c_sym, c_pt) + f'\n<path fill="{c_nom}" d="{d_attr(n_h)}"/>'))
        ecrire(os.path.join(SVG, f"loopy-empile-{v}.svg"),
               svg(vb_e, dessin(f_e, p_e, c_sym, c_pt) + f'\n<path fill="{c_nom}" d="{d_attr(n_e)}"/>'))

    # icônes : encre sur tuile Sauge (principale), Sauge et pêche sur tuile Encre (sombre)
    def icone(taille, coupe, zone, fond, c_sym, c_pt, rx=0):
        f, p = cadre(coupe, taille, zone)
        return svg(f"0 0 {taille} {taille}",
                   f'<rect width="{taille}" height="{taille}"{f" rx={chr(34)}{rx}{chr(34)}" if rx else ""} fill="{fond}"/>\n'
                   + dessin(f, p, c_sym, c_pt))

    fichiers = {
        "app-icon.svg": icone(1024, ROSE, 0.6, SAUGE, ENCRE, (ENCRE, PECHE)),
        "app-icon-arrondie.svg": icone(1024, ROSE, 0.6, SAUGE, ENCRE, (ENCRE, PECHE), rx=225),
        "app-icon-sombre.svg": icone(1024, ROSE, 0.6, ENCRE, SAUGE, (PECHE, None)),
        "app-icon-sombre-arrondie.svg": icone(1024, ROSE, 0.6, ENCRE, SAUGE, (PECHE, None), rx=225),
        "favicon.svg": icone(64, ROSE_PETITE, 0.84, SAUGE, ENCRE, (ENCRE, None), rx=14),
    }
    for nom_f, contenu in fichiers.items():
        ecrire(os.path.join(ICONES, nom_f), contenu)

    def png(nom_svg, taille, sortie):
        cairosvg.svg2png(url=os.path.join(ICONES, nom_svg), write_to=sortie, output_width=taille, output_height=taille)

    for t in (1024, 512, 192, 180):
        png("app-icon.svg", t, os.path.join(PNG, f"app-icon-{t}.png"))
    png("app-icon-arrondie.svg", 512, os.path.join(PNG, "app-icon-arrondie-512.png"))
    png("app-icon-sombre.svg", 512, os.path.join(PNG, "app-icon-sombre-512.png"))
    for t in (16, 32, 48):
        png("favicon.svg", t, os.path.join(PNG, f"favicon-{t}.png"))
    Image.open(os.path.join(PNG, "favicon-48.png")).save(os.path.join(ICONES, "favicon.ico"),
                                                         sizes=[(16, 16), (32, 32), (48, 48)])

    # l'app : icône Android (coins déjà arrondis) et écran de lancement sur fond Lin
    png("app-icon-arrondie.svg", 512, os.path.join(LOGO, "icone.png"))
    l, h = 540, 960
    emp = open(os.path.join(SVG, "loopy-empile-couleur-clair.svg")).read()
    marque = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=emp.encode(), output_width=int(l * 0.46))))
    ecran = Image.new("RGB", (l, h), LIN)
    ecran.paste(marque, ((l - marque.width) // 2, (h - marque.height) // 2 - 30), marque)
    ecran.save(os.path.join(LOGO, "lancement.png"))


# --- planche de présentation ---

def _inclure(fichier, x, y, larg, haut):
    contenu = open(fichier).read()
    vb = contenu.split('viewBox="')[1].split('"')[0]
    corps = contenu.split("</title>", 1)[1].rsplit("</svg>", 1)[0]
    return (f'<svg x="{x}" y="{y}" width="{larg}" height="{haut}" viewBox="{vb}" '
            f'preserveAspectRatio="xMidYMid meet">{corps}</svg>')


def _texte(x, y, t, taille=18, couleur=ENCRE, poids=400, ancre="start"):
    t = t.replace("&", "&amp;")
    return (f'<text x="{x}" y="{y}" font-family="Atkinson Hyperlegible, sans-serif" font-size="{taille}" '
            f'font-weight="{poids}" fill="{couleur}" text-anchor="{ancre}">{t}</text>')


def planche():
    L, H = 1600, 1500
    s = lambda f: os.path.join(SVG, f)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {H}">',
         f'<rect width="{L}" height="{H}" fill="#FBFAF7"/>',
         _texte(64, 86, "Loopy", 44, ENCRE, 700),
         _texte(64, 122, "La rose des boucles · Sauge & Pêche — trois boucles, un seul départ", 20, "#56655D")]
    # 1. horizontal clair et sombre
    o += [f'<rect x="64" y="160" width="728" height="300" rx="24" fill="{LIN}"/>',
          _inclure(s("loopy-horizontal-couleur-clair.svg"), 104, 190, 648, 240),
          f'<rect x="808" y="160" width="728" height="300" rx="24" fill="{ENCRE}"/>',
          _inclure(s("loopy-horizontal-sombre.svg"), 848, 190, 648, 240)]
    # 2. empilé sur Sauge, sur Encre ; une couleur noir / blanc
    y = 484
    for i, (fond, f) in enumerate(((SAUGE, "loopy-empile-encre.svg"), (ENCRE, "loopy-empile-sombre.svg"),
                                   ("#FFFFFF", "loopy-empile-noir.svg"), ("#111111", "loopy-empile-blanc.svg"))):
        x = 64 + i * 372
        o += [f'<rect x="{x}" y="{y}" width="356" height="356" rx="24" fill="{fond}"'
              f'{" stroke=" + chr(34) + "#E5DDCF" + chr(34) if fond == "#FFFFFF" else ""}/>',
              _inclure(s(f), x + 38, y + 38, 280, 280)]
    # 3. icônes et petites tailles
    y = 864
    o += [_inclure(os.path.join(ICONES, "app-icon-arrondie.svg"), 64, y, 220, 220),
          _inclure(os.path.join(ICONES, "app-icon-sombre-arrondie.svg"), 300, y, 220, 220),
          _texte(174, y + 250, "icône · principale", 15, "#56655D", 400, "middle"),
          _texte(410, y + 250, "icône · sombre", 15, "#56655D", 400, "middle")]
    x = 560
    for t in (64, 32, 16):
        o += [_inclure(os.path.join(ICONES, "favicon.svg"), x, y + (64 - t), t, t),
              _texte(x + t / 2, y + 96, f"{t} px", 14, "#56655D", 400, "middle")]
        x += t + 36
    o += [_inclure(s("loopy-symbole-couleur-clair.svg"), 560, y + 120, 100, 100),
          _texte(610, y + 240, "symbole", 14, "#56655D", 400, "middle"),
          _inclure(s("loopy-symbole-petit-encre.svg"), 690, y + 140, 60, 60),
          _texte(720, y + 240, "coupe petite", 14, "#56655D", 400, "middle")]
    # 4. nuancier
    x0 = 820
    for i, (c, n, role) in enumerate(((SAUGE, "Sauge", "principal · tuiles, symbole sur Encre"),
                                      (PECHE, "Pêche", "accent · le point de départ"),
                                      (ENCRE, "Encre", "symbole et nom sur fond clair"),
                                      (LIN, "Lin", "fond clair"))):
        yy = y + i * 62
        o += [f'<rect x="{x0}" y="{yy}" width="48" height="48" rx="12" fill="{c}" stroke="#0000001A"/>',
              _texte(x0 + 64, yy + 21, f"{n}  {c}", 18, ENCRE, 700),
              _texte(x0 + 64, yy + 42, role, 15, "#56655D")]
    # 5. règle de contraste
    y = 1180
    o += [f'<rect x="64" y="{y}" width="1472" height="250" rx="24" fill="{LIN}"/>',
          _texte(100, y + 52, "Règle de contraste", 22, ENCRE, 700),
          _texte(100, y + 92, "Encre sur Lin 11,8:1 · Encre sur Sauge 7,1:1 · Sauge sur Encre 7,1:1 · Pêche sur Encre 8,2:1", 18),
          _texte(100, y + 130, "Jamais de Sauge ni de Pêche seuls sur fond clair (1,4 à 1,9:1) : sur fond clair, le point pêche", 18),
          _texte(100, y + 158, "est toujours cerclé d'Encre. Jamais Pêche sur Sauge (1,2:1).", 18),
          _texte(100, y + 206, "Zone de protection : une hauteur d'x du nom tout autour (déjà incluse dans les fichiers).", 18, "#56655D")]
    o.append("</svg>")
    chemin = os.path.join(ICI, "planche.svg")
    ecrire(chemin, "\n".join(o))
    cairosvg.svg2png(url=chemin, write_to=os.path.join(ICI, "planche.png"), output_width=L)


if __name__ == "__main__":
    construire()
    planche()
