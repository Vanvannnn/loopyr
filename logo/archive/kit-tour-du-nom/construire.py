"""Construit le kit du logo Loop R (option B, « le tour du nom ») en contours pleins.

Tout est dessiné droit, en unités de lettre (hauteur de capitale 100, graisse 18, y vers le bas),
fusionné en contours avec skia-pathops, puis incliné de 15° autour de la ligne de base.
Le point de départ est ajouté après l'inclinaison pour rester rond.

Outil de dev, pas une dépendance de l'app :  pip install skia-pathops fonttools
    python logo/kit/construire.py
"""
import math
import os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from pathops import Path, PathOp, op

ICI = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(ICI, "svg")
ICONES = os.path.join(ICI, "icones")

K = math.tan(math.radians(15))  # inclinaison commune au symbole et au lettrage
W = 18                          # graisse
KAPPA = 0.5522847498

BLEU, CITRON, ENCRE, NUIT, BLANC, NOIR = "#2443E6", "#C8F031", "#0D1726", "#0E131B", "#FFFFFF", "#000000"


# --- primitives (repère droit, y vers le bas) ---

def poly(*pts):
    p = Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def rect(x0, y0, x1, y1):
    return poly((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _arc(p, cx, cy, r, a0, a1, move=False):
    """Arc de cercle en cubiques (≤ 90° chacune), angles en degrés, sens des angles croissants."""
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


def anneau(cx, cy, ro, ri, a0, a1):
    """Secteur d'anneau entre les angles a0 et a1."""
    p = Path()
    _arc(p, cx, cy, ro, a0, a1, move=True)
    p.lineTo(cx + ri * math.cos(math.radians(a1)), cy + ri * math.sin(math.radians(a1)))
    _arc(p, cx, cy, ri, a1, a0)
    p.close()
    return p


def stade(x0, y0, x1, y1):
    """Rectangle aux bouts entièrement arrondis (la piste des o)."""
    r = min(x1 - x0, y1 - y0) / 2
    p = Path()
    p.moveTo(x0 + r, y0)
    p.lineTo(x1 - r, y0)
    _arc(p, x1 - r, y0 + r, r, -90, 0)
    p.lineTo(x1, y1 - r)
    _arc(p, x1 - r, y1 - r, r, 0, 90)
    p.lineTo(x0 + r, y1)
    _arc(p, x0 + r, y1 - r, r, 90, 180)
    p.lineTo(x0, y0 + r)
    _arc(p, x0 + r, y0 + r, r, 180, 270)
    p.close()
    return p


def union(*ps):
    out = ps[0]
    for p in ps[1:]:
        out = op(out, p, PathOp.UNION)
    return out


def moins(a, b):
    return op(a, b, PathOp.DIFFERENCE)


def bouge(p, dx, dy=0):
    out = Path()
    p.draw(TransformPen(out.getPen(), (1, 0, 0, 1, dx, dy)))
    return out


# --- le R, commun au symbole et au lettrage ---

def jambe(w, y_haut, fin):
    """La jambe du R : un trait de graisse w, de y_haut jusqu'au point fin, coupe perpendiculaire."""
    p0 = (32, 55)
    ux, uy = fin[0] - p0[0], fin[1] - p0[1]
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    nx, ny = uy * w / 2, -ux * w / 2
    t = (y_haut - p0[1]) / uy
    a = (p0[0] + ux * t, y_haut)
    return poly((a[0] + nx, a[1] + ny), (fin[0] + nx, fin[1] + ny), (fin[0] - nx, fin[1] - ny), (a[0] - nx, a[1] - ny))


DIRECTION = (36 * (1 / math.sqrt(3) + K), 36)  # pente de la jambe, la même partout : 60° une fois inclinée


def r_lettre(w=W, bas_fut=100, base=None):
    """base=None : R du lettrage, jambe coupée à l'horizontale sur la ligne de base.
    base=(x_debut, gap) : R du symbole, la jambe tourne dans la ligne de base qui revient vers le point."""
    h = w / 2
    cy = (h + 46 + h) / 2  # centre de la panse, entre la barre du haut et celle du bas
    ro = cy                # rayon extérieur : touche le haut de capitale
    ri = ro - w
    forme = union(rect(0, 0, w, bas_fut), rect(0, 0, 29, w), rect(0, 46, 29, 46 + w),
                  anneau(29, cy, ro, ri, -90, 90))
    if base is None:
        y = 100
        fin = (32 + DIRECTION[0] * (y - 55) / DIRECTION[1], y)
        ux, uy = DIRECTION
        dx = w / 2 * math.hypot(ux, uy) / uy  # demi-largeur horizontale de la jambe
        t = (46 - 55) / uy
        xh = 32 + ux * t
        leg = poly((xh - dx, 46), (xh + dx, 46), (fin[0] + dx, y), (fin[0] - dx, y))
        return union(forme, leg)
    x0 = base
    coin = (32 + DIRECTION[0] * (100 - h - 55) / DIRECTION[1], 100 - h)
    leg = op(jambe(w, 40, coin), rect(-50, 46, 300, 200), PathOp.INTERSECTION)  # coupée net sous la panse
    return union(forme, leg, cercle(*coin, h), rect(x0, 100 - w, coin[0], 100))


# --- le lettrage « Loop R » ---

def lettrage():
    h = W / 2
    L = union(rect(0, 0, W, 100), rect(0, 100 - W, 50, 100))

    def o(x):
        return moins(stade(x, 32, x + 54, 100), stade(x + W, 32 + W, x + 54 - W, 100 - W))
    panse = moins(stade(175, 32, 229, 100), stade(175 + W, 32 + W, 229 - W, 100 - W))
    p_ = union(rect(178, 32, 178 + W, 134), moins(panse, rect(170, 30, 178 + W, 102)))
    return union(L, o(54), o(116), p_, bouge(r_lettre(), 266))  # espace de mot ≈ 2 graisses


# --- le symbole : L + R en un seul tour, le point de départ dans le coin ---

def symbole(w=W, gap=None, rayon=None):
    """gap et rayon du point en unités de lettre ; la coupe pour petites tailles les élargit."""
    rayon = rayon or w * 0.533
    gap = gap or rayon
    cx, cy = w / 2, 100 - w / 2
    bas_fut = cy - rayon - gap
    x_base = cx + rayon + gap
    return r_lettre(w, bas_fut, base=x_base), (cx, cy, rayon)


# --- mise en page ---

def incline(p, s=1, dx=0, dy=0):
    """Incline autour de la ligne de base (y = 100), met à l'échelle s, puis décale."""
    out = Path()
    p.draw(TransformPen(out.getPen(), (s, 0, -K * s, s, dx + K * 100 * s, dy)))
    return out


def point_incline(cx, cy, s=1, dx=0, dy=0):
    return (s * (cx - K * (cy - 100)) + dx, s * cy + dy)


def d(p):
    pen = SVGPathPen(None, ntos=lambda v: ("%.2f" % v).rstrip("0").rstrip("."))
    p.draw(pen)
    return pen.getCommands()


def depart(cx, cy, r, couleurs):
    """Le point de départ : plein, ou disque citron cerclé (fonds clairs, où le citron seul disparaît)."""
    plein, coeur = couleurs
    out = f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{plein}"/>'
    if coeur:
        out += f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r * 0.6:.2f}" fill="{coeur}"/>'
    return out


# fond prévu, couleur du symbole, du point (plein, cœur), du lettrage
BRUME = "#F4F6F8"
VARIANTES = {
    "couleur-clair": (BRUME, BLEU, (BLEU, CITRON), ENCRE),
    "couleur-sombre": (ENCRE, BLANC, (CITRON, None), BLANC),
    "sur-bleu": (BLEU, BLANC, (CITRON, None), BLANC),
    "noir": (BLANC, NOIR, (NOIR, None), NOIR),
    "blanc": (NOIR, BLANC, (BLANC, None), BLANC),
}


def svg(vb, corps, titre="Loop R"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img">'
            f'<title>{titre}</title>\n{corps}\n</svg>\n')


def ecrire(dossier, nom, contenu):
    os.makedirs(dossier, exist_ok=True)
    with open(os.path.join(dossier, nom), "w") as f:
        f.write(contenu)


def bornes(p):
    return p.bounds  # (xmin, ymin, xmax, ymax)


def place_symbole(forme, pt, s, dx, dy, var):
    _, c_sym, c_pt, _ = VARIANTES[var]
    px, py = point_incline(pt[0], pt[1], s, dx, dy)
    return (f'<path fill="{c_sym}" d="{d(incline(forme, s, dx, dy))}"/>\n'
            + depart(px, py, pt[2] * s, c_pt))


def construire():
    forme, pt = symbole()
    petite, pt_petit = symbole(w=20, gap=16, rayon=12)
    mots = lettrage()

    # symbole seul : centré dans 256, marge 24, centre optique légèrement au-dessus
    def cadre(f, p, cote=256, marge=24):
        x0, y0, x1, y1 = bornes(incline(f))
        x0 = min(x0, point_incline(p[0], p[1])[0] - p[2])
        s = (cote - 2 * marge) / max(x1 - x0, y1 - y0)
        dx = (cote - s * (x1 + x0)) / 2
        dy = (cote - s * (y1 + y0)) / 2 - cote * 0.01
        return s, dx, dy

    s, dx, dy = cadre(forme, pt)
    sp, dxp, dyp = cadre(petite, pt_petit, marge=12)

    # horizontal : le symbole fait 1,6 capitale ; capitale du lettrage centrée sur le symbole
    S_H, ECART = 1.6, 34
    lx0, _, lx1, _ = bornes(incline(mots))
    sx0, sy0, sx1, sy1 = bornes(incline(forme, S_H))
    sx0 = min(sx0, point_incline(pt[0], pt[1], S_H)[0] - pt[2] * S_H)
    m = 2 * pt[2] * S_H  # zone de protection = un diamètre du point de départ
    h_dx = m - sx0
    h_dy = m - sy0
    cap_y = h_dy + (sy0 + sy1) / 2 - 50
    w_dx = h_dx + sx1 + ECART - lx0
    largeur_h = w_dx + lx1 + m
    hauteur_h = h_dy + sy1 + m

    # empilé : symbole de 1,6 capitale au-dessus, lettrage centré dessous
    e_sy = m - sy0
    e_cap = e_sy + sy1 + 30
    largeur_e = lx1 - lx0 + 2 * m
    e_wx = m - lx0
    e_sx = (largeur_e - (sx1 - sx0)) / 2 - sx0
    hauteur_e = e_cap + 134 + m

    for var, (_, c_sym, c_pt, c_mot) in VARIANTES.items():
        ecrire(SVG, f"loopr-symbole-{var}.svg", svg("0 0 256 256", place_symbole(forme, pt, s, dx, dy, var)))
        ecrire(SVG, f"loopr-symbole-petit-{var}.svg",
               svg("0 0 256 256", place_symbole(petite, pt_petit, sp, dxp, dyp, var)))
        ecrire(SVG, f"loopr-lettrage-{var}.svg",
               svg(f"0 0 {lx1 - lx0 + 2 * m:.0f} {134 + 2 * m:.0f}",
                   f'<path fill="{c_mot}" d="{d(incline(mots, 1, m - lx0, m))}"/>'))
        ecrire(SVG, f"loopr-horizontal-{var}.svg",
               svg(f"0 0 {largeur_h:.0f} {max(hauteur_h, cap_y + 134 + m):.0f}",
                   place_symbole(forme, pt, S_H, h_dx, h_dy, var) + "\n"
                   + f'<path fill="{c_mot}" d="{d(incline(mots, 1, w_dx, cap_y))}"/>'))
        ecrire(SVG, f"loopr-empile-{var}.svg",
               svg(f"0 0 {largeur_e:.0f} {hauteur_e:.0f}",
                   place_symbole(forme, pt, S_H, e_sx, e_sy, var) + "\n"
                   + f'<path fill="{c_mot}" d="{d(incline(mots, 1, e_wx, e_cap))}"/>'))

    # icônes : pleine page bleue (le système arrondit lui-même), symbole dans la zone sûre (66 %)
    def icone(f, p, cote, zone, arrondi=0):
        x0, y0, x1, y1 = bornes(incline(f))
        x0 = min(x0, point_incline(p[0], p[1])[0] - p[2])
        s_ = cote * zone / max(x1 - x0, y1 - y0)
        dx_ = (cote - s_ * (x1 + x0)) / 2
        dy_ = (cote - s_ * (y1 + y0)) / 2 - cote * 0.01
        fond = f'<rect width="{cote}" height="{cote}" rx="{arrondi}" fill="{BLEU}"/>'
        return svg(f"0 0 {cote} {cote}", fond + "\n" + place_symbole(f, p, s_, dx_, dy_, "sur-bleu"))

    ecrire(ICONES, "app-icon.svg", icone(forme, pt, 1024, 0.56))
    ecrire(ICONES, "app-icon-arrondie.svg", icone(forme, pt, 1024, 0.56, arrondi=230))
    ecrire(ICONES, "favicon.svg", icone(petite, pt_petit, 64, 0.74, arrondi=14))


# --- planche de présentation : chaque déclinaison sur son fond ---

def _inclure(chemin, x, y, w, h):
    """Insère un SVG du kit dans un cadre, centré."""
    with open(chemin) as f:
        src = f.read()
    vb = src.split('viewBox="')[1].split('"')[0]
    corps = src.split("</title>", 1)[1].rsplit("</svg>", 1)[0]
    return f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{vb}">{corps}</svg>'


def planche():
    L, marge, pas = 1600, 40, 24
    out, y = [], 40
    txt = 'font-family="Atkinson Hyperlegible, DejaVu Sans, sans-serif"'
    out.append(f'<text x="{marge}" y="{y + 30}" {txt} font-size="30" font-weight="700" fill="{ENCRE}">'
               'Loop R — kit d\'identité</text>')
    out.append(f'<text x="{marge}" y="{y + 62}" {txt} font-size="17" fill="#535E70">'
               'Le tour du nom : on part du point, on trace le R, la ligne de base ramène au départ.</text>')
    y += 100

    def panneau(x, y, w, h, var, fichier, legende, pad=40):
        fond = VARIANTES[var][0]
        bord = ' stroke="#E1E6ED"' if fond in (BLANC, BRUME) else ""
        c = "#8E9AAB" if fond in (ENCRE, NOIR) else ("#DCE3FF" if fond == BLEU else "#535E70")
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fond}"{bord}/>')
        out.append(_inclure(os.path.join(SVG, fichier), x + pad, y + pad, w - 2 * pad, h - 2 * pad - 20))
        out.append(f'<text x="{x + 18}" y="{y + h - 16}" {txt} font-size="14" fill="{c}">{legende}</text>')

    lw = (L - 2 * marge - pas) / 2
    panneau(marge, y, lw, 300, "couleur-clair", "loopr-horizontal-couleur-clair.svg", "Horizontal · couleur, fond clair")
    panneau(marge + lw + pas, y, lw, 300, "couleur-sombre", "loopr-horizontal-couleur-sombre.svg",
            "Horizontal · couleur, fond sombre")
    y += 300 + pas
    tw = (L - 2 * marge - 2 * pas) / 3
    for i, (var, leg) in enumerate((("sur-bleu", "Empilé · sur bleu"), ("noir", "Empilé · une couleur, noir"),
                                     ("blanc", "Empilé · une couleur, blanc"))):
        panneau(marge + i * (tw + pas), y, tw, 380, var, f"loopr-empile-{var}.svg", leg, pad=50)
    y += 380 + pas
    qw = (L - 2 * marge - 3 * pas) / 4
    panneau(marge, y, qw, 300, "couleur-clair", "loopr-symbole-couleur-clair.svg", "Symbole · fond clair")
    panneau(marge + qw + pas, y, qw, 300, "couleur-sombre", "loopr-symbole-couleur-sombre.svg", "Symbole · fond sombre")
    x = marge + 2 * (qw + pas)
    out.append(f'<rect x="{x}" y="{y}" width="{qw}" height="300" rx="14" fill="{BRUME}"/>')
    out.append(_inclure(os.path.join(ICONES, "app-icon-arrondie.svg"), x + qw / 2 - 100, y + 30, 200, 200))
    out.append(f'<text x="{x + 18}" y="{y + 284}" {txt} font-size="14" fill="#535E70">Icône d\'application</text>')
    x += qw + pas
    out.append(f'<rect x="{x}" y="{y}" width="{qw}" height="300" rx="14" fill="{BRUME}"/>')
    cx = x + 40
    for t in (64, 32, 16):
        out.append(_inclure(os.path.join(ICONES, "favicon.svg"), cx, y + 130 - t / 2, t, t))
        out.append(f'<text x="{cx}" y="{y + 190}" {txt} font-size="13" fill="#535E70">{t} px</text>')
        cx += t + 44
    out.append(f'<text x="{x + 18}" y="{y + 284}" {txt} font-size="14" fill="#535E70">Favicon · coupe petites tailles</text>')
    y += 300 + pas

    nuancier = (("Bleu tracé", BLEU, "RVB 36 67 230", BLANC), ("Citron signal", CITRON, "RVB 200 240 49", ENCRE),
                ("Encre", ENCRE, "RVB 13 23 38", BLANC), ("Brume", BRUME, "RVB 244 246 248", ENCRE))
    for i, (nom, hexa, rvb, sur) in enumerate(nuancier):
        x = marge + i * (qw + pas)
        bord = ' stroke="#E1E6ED"' if hexa == BRUME else ""
        out.append(f'<rect x="{x}" y="{y}" width="{qw}" height="130" rx="14" fill="{hexa}"{bord}/>')
        out.append(f'<text x="{x + 20}" y="{y + 42}" {txt} font-size="20" font-weight="700" fill="{sur}">{nom}</text>')
        out.append(f'<text x="{x + 20}" y="{y + 80}" {txt} font-size="16" fill="{sur}">{hexa}</text>')
        out.append(f'<text x="{x + 20}" y="{y + 106}" {txt} font-size="16" fill="{sur}">{rvb}</text>')
    y += 130 + 40
    ecrire(ICI, "planche.svg", svg(f"0 0 {L} {y}", f'<rect width="{L}" height="{y}" fill="{BLANC}"/>\n'
                                   + "\n".join(out), "Loop R — planche"))


if __name__ == "__main__":
    construire()
    planche()
    print("kit écrit dans", ICI)
