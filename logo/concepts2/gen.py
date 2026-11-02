"""Concepts Loop R, deuxième tour (de zéro) : symboles en noir + lockups, en contours pleins.

Outil de dev :  pip install skia-pathops fonttools
    python logo/concepts2/gen.py [suffixe]
"""
import math
import os
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from pathops import Path, PathOp, op, LineCap, LineJoin

ICI = os.path.dirname(os.path.abspath(__file__))
V = sys.argv[1] if len(sys.argv) > 1 else "v1"


# --- primitives ---

def _arc(p, cx, cy, r, a0, a1, move=False):
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


def moins(a, b):
    return op(a, b, PathOp.DIFFERENCE)


def trait(build, w, cap="round", join="round"):
    """Construit un chemin ouvert avec build(p), puis le convertit en contour plein de graisse w."""
    p = Path()
    build(p)
    p.stroke(w, LineCap.ROUND_CAP if cap == "round" else LineCap.BUTT_CAP,
             LineJoin.ROUND_JOIN if join == "round" else LineJoin.MITER_JOIN, 4)
    p.convertConicsToQuads()
    p.simplify()
    return p


def goutte(p, tx, ty, ang, d, r):
    """Boucle en goutte : part de la pointe (tx, ty), fait le tour d'un cercle de rayon r à distance d, revient."""
    a = math.radians(ang)
    cx, cy = tx + d * math.cos(a), ty + d * math.sin(a)
    beta = math.degrees(math.acos(r / d))
    back = ang + 180  # direction centre -> pointe
    a0, a1 = back + beta, back - beta + 360
    p.moveTo(tx, ty)
    p.lineTo(cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    _arc(p, cx, cy, r, a0, a1)
    p.close()


def d_attr(p):
    pen = SVGPathPen(None, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    p.draw(pen)
    return pen.getCommands()


def cadre(p, taille=256, marge=28, haut=None):
    """Met p à l'échelle et le centre (léger relèvement optique) dans un carré."""
    x0, y0, x1, y1 = p.bounds
    s = (taille - 2 * marge) / max(x1 - x0, y1 - y0)
    dx = taille / 2 - s * (x0 + x1) / 2
    dy = taille / 2 - s * (y0 + y1) / 2 - taille * 0.01
    return p.transform(s, 0, 0, s, dx, dy)


def svg(vb, corps):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img"><title>Loop R</title>\n{corps}\n</svg>\n'


# --- A : la rose des boucles — trois boucles de longueurs différentes autour d'un même départ ---

def sym_a():
    w = 15
    def b(p):
        # demi-angle de 30° : toutes les tangentes tombent sur des multiples de 15°
        goutte(p, 0, 0, -105, 84, 42)
        goutte(p, 0, 0, 15, 64, 32)
        goutte(p, 0, 0, 150, 48, 24)
    f = trait(b, w)
    f = moins(f, cercle(0, 0, 21))
    return union(f, cercle(0, 0, 10.5))


# --- B : le ℓ de loop — la lettre l en écriture liée, qui forme une boucle et repart ---

def sym_b():
    w = 20
    def b(p):
        p.moveTo(40, 176)
        p.cubicTo(92, 150, 156, 92, 152, 48)
        p.cubicTo(149, 18, 116, 16, 106, 44)
        p.cubicTo(96, 74, 88, 136, 92, 168)
        p.cubicTo(96, 200, 136, 204, 172, 172)
    f = trait(b, w)
    return union(f, cercle(20, 188, 11))


# --- C : le lacet — un nœud de lacet dont les deux boucles sont deux parcours ---

def sym_c():
    w = 16
    def b(p):
        goutte(p, 0, 0, 200, 76, 30)
        goutte(p, 0, 0, -20, 76, 30)
        p.moveTo(-6, 4)
        p.cubicTo(-14, 40, -30, 70, -40, 104)
        p.moveTo(6, 4)
        p.cubicTo(16, 34, 30, 52, 34, 78)
    f = trait(b, w)
    f = moins(f, cercle(0, 2, 26))
    knot = Path()
    _arc(knot, 0, 2, 18, 0, 360, move=True)
    knot.close()
    return union(f, knot, cercle(36, 104, 10))


# --- D : le pas de côté — une boucle dont l'aller et le retour ne prennent pas la même voie ---

def sym_d():
    w = 22
    r, dec = 66, 30
    def b(p):
        _arc(p, 0, 0, r, 180, 360, move=True)       # aller, par le haut
        p.lineTo(r + dec, 0)
        _arc(p, dec, 0, r, 0, 180)                  # retour, décalé d'une voie
    f = trait(b, w)
    return union(f, cercle(-r + dec + 2, -34, 13))


# --- E : le r qui revient — le bras du r s'enroule en boucle avant de repartir ---

def sym_e():
    w = 20
    def b(p):
        p.moveTo(0, 150)
        p.lineTo(0, 60)
        p.cubicTo(0, 20, 40, 0, 78, 8)        # épaule
        p.cubicTo(118, 16, 124, 66, 92, 74)   # la boucle descend…
        p.cubicTo(62, 82, 52, 46, 80, 34)     # …remonte
        p.cubicTo(98, 26, 120, 34, 134, 52)   # et repart vers l'avant
    f = trait(b, w)
    return union(f, cercle(0, 186, 12))


# --- F : le galet — une boucle organique comme une vraie trace GPS, coupée au départ ---

def _catmull(p, pts):
    n = len(pts)
    p.moveTo(*pts[0])
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        p.cubicTo(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                  p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, *p2)
    p.close()


def sym_f():
    w = 20
    pts = [(40, 170), (10, 120), (30, 50), (100, 18), (170, 40), (150, 92), (186, 140), (130, 186)]
    f = trait(lambda p: _catmull(p, pts), w)
    f = moins(f, cercle(40, 170, 24))
    return union(f, cercle(40, 170, 12))


# --- G : les courbes de niveau — trois boucles emboîtées (5, 10, 15 km) depuis le même départ ---

def _contour(forme, w):
    """Trait de graisse w posé sur le bord d'une forme pleine."""
    p = Path()
    p.addPath(forme)
    p.stroke(w, LineCap.ROUND_CAP, LineJoin.ROUND_JOIN, 4)
    p.convertConicsToQuads()
    p.simplify()
    return p


def sym_g():
    w, pas = 13, 27
    base = Path()
    goutte(base, 0, 0, -45, 70, 26)
    lignes = []
    for i in range(3):
        forme = base if i == 0 else union(base, _contour(base, 2 * pas * i))
        lignes.append(_contour(forme, w))
    a = math.radians(135)
    coin = Path()
    coin.moveTo(0, 0)
    for da in (-38, 38):
        coin.lineTo(300 * math.cos(a + math.radians(da)), 300 * math.sin(a + math.radians(da)))
    coin.close()
    f = moins(union(*lignes), union(coin, cercle(0, 0, 24)))
    return union(f, cercle(0, 0, 12))


# --- lettrage commun « loop r » : monoline arrondi minuscule ---

def _ovale(p, cx, cy, rx, ry):
    """Ovale fermé (cercle étiré), départ à droite."""
    q = Path()
    _arc(q, 0, 0, 1, 0, 360, move=True)
    q.close()
    p.addPath(q.transform(rx, 0, 0, ry, cx, cy))


def lettrage():
    """Minuscules monolignes un peu condensées ; le l finit en crochet, comme un départ de foulée."""
    w = 13
    rx, ry = 21, 23.5  # o légèrement condensés (axe du trait)
    def b(p):
        x = w / 2
        p.moveTo(x, 6); p.lineTo(x, 84)                       # l, fût + crochet
        p.cubicTo(x, 96, x + 6, 101, x + 16, 101)
        o1 = x + 16 + 12 + rx + w / 2                         # o o
        o2 = o1 + 2 * rx + w + 10
        q = Path()
        _ovale(q, o1, 70, rx, ry)
        _ovale(q, o2, 70, rx, ry)
        p.addPath(q)
        sx = o2 + rx + w + 10                                 # p
        p.moveTo(sx, 40); p.lineTo(sx, 128)
        q = Path()
        _ovale(q, sx + rx, 70, rx, ry)
        p.addPath(q)
        rxx = sx + 2 * rx + w / 2 + 34                        # r
        p.moveTo(rxx, 100); p.lineTo(rxx, 66)
        p.cubicTo(rxx, 50, rxx + 10, 40, rxx + 26, 42)
    return trait(b, w)


def ecrire():
    lt = lettrage()
    lx0, ly0, lx1, ly1 = lt.bounds
    for k, f in {"a": sym_a, "b": sym_b, "c": sym_c, "d": sym_d, "e": sym_e, "f": sym_f, "g": sym_g}.items():
        s = cadre(f())
        with open(os.path.join(ICI, f"{k}-symbole-{V}.svg"), "w") as fh:
            fh.write(svg("0 0 256 256", f'<path fill="#000" d="{d_attr(s)}"/>'))
        sc = 1.25
        t = lt.transform(sc, 0, 0, sc, 268 - lx0 * sc, 128 - 70 * sc)
        largeur = 268 + (lx1 - lx0) * sc + 28
        with open(os.path.join(ICI, f"{k}-lockup-{V}.svg"), "w") as fh:
            fh.write(svg(f"0 0 {largeur:.0f} 256",
                         f'<path fill="#000" d="{d_attr(s)}"/>\n<path fill="#000" d="{d_attr(t)}"/>'))
    print("ok", V)


if __name__ == "__main__":
    ecrire()
