"""Planche couleur : trois palettes pastel appliquées aux trois concepts retenus."""
import os

import gen

ICI = os.path.dirname(os.path.abspath(__file__))

# nom, pastel principal, pastel d'accent (le point de départ), encre, fond clair
PALETTES = [
    ("Sauge & Pêche", "#A8C3B1", "#F4BFA3", "#22322B", "#F4EFE6"),
    ("Ciel & Argile", "#B5CFE6", "#E9A48E", "#1E2A3A", "#F6F4EF"),
    ("Poudre & Menthe", "#EFC3BE", "#B9DCC8", "#2B2D3A", "#F7F1EC"),
]
CONCEPTS = [("A", gen.sym_a, (0, 0, 10.5)), ("B", gen.sym_b, (20, 188, 11)), ("C", gen.sym_g, (0, 0, 12))]


def cadre(p, dot, taille=256, marge=28):
    x0, y0, x1, y1 = p.bounds
    s = (taille - 2 * marge) / max(x1 - x0, y1 - y0)
    dx = taille / 2 - s * (x0 + x1) / 2
    dy = taille / 2 - s * (y0 + y1) / 2 - taille * 0.01
    return p.transform(s, 0, 0, s, dx, dy), (dot[0] * s + dx, dot[1] * s + dy, dot[2] * s)


def symbole(fn, dot, x, y, taille, encre, accent, zone=0.62):
    p, (cx, cy, r) = cadre(fn(), dot)
    k = taille * zone / 256
    o = (taille - 256 * k) / 2
    return (f'<g transform="translate({x + o:.1f} {y + o:.1f}) scale({k:.4f})">'
            f'<path fill="{encre}" d="{gen.d_attr(p)}"/>'
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r * 1.08:.2f}" fill="{accent}"/></g>')


def texte(x, y, t, taille=22, couleur="#2B2D3A", poids=600):
    return (f'<text x="{x}" y="{y}" font-family="Atkinson Hyperlegible, sans-serif" font-size="{taille}" '
            f'font-weight="{poids}" fill="{couleur}">{t.replace("&", "&amp;")}</text>')


def planche():
    lt = gen.lettrage()
    lx0, ly0, lx1, ly1 = lt.bounds
    T, G, L = 150, 24, 1700
    rangee = 2 * T + 3 * G + 60
    h = 110 + len(PALETTES) * rangee
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {h}">',
           f'<rect width="{L}" height="{h}" fill="#FBFAF7"/>',
           texte(60, 70, "Loop R — trois palettes pastel", 34, "#22252E", 700)]
    for i, (nom, pastel, accent, encre, fond) in enumerate(PALETTES):
        y = 110 + i * rangee
        out.append(texte(60, y + 26, nom, 24, encre, 700))
        y += 50
        x = 60
        for lettre, fn, dot in CONCEPTS:
            # icône claire : tuile pastel, symbole encre, point d'accent
            out.append(f'<rect x="{x}" y="{y}" width="{T}" height="{T}" rx="34" fill="{pastel}"/>')
            out.append(symbole(fn, dot, x, y, T, encre, encre))
            out.append(f'<rect x="{x}" y="{y + T + G}" width="{T}" height="{T}" rx="34" fill="{encre}"/>')
            out.append(symbole(fn, dot, x, y + T + G, T, pastel, accent))
            out.append(texte(x + T / 2 - 6, y + 2 * T + G + 34, lettre, 18, encre, 700))
            x += T + G
        # lockup du concept C sur fond clair et sur fond encre
        lx = x + 30
        lw = L - lx - 220
        for j, (bg, fg, ac) in enumerate(((fond, encre, encre), (encre, pastel, accent))):
            yy = y + j * (T + G)
            out.append(f'<rect x="{lx}" y="{yy}" width="{lw}" height="{T}" rx="18" fill="{bg}"/>')
            out.append(symbole(gen.sym_g, (0, 0, 12), lx + 20, yy, T, fg, ac, zone=0.7))
            sc = 0.66
            out.append(f'<g transform="translate({lx + T + 20 - lx0 * sc:.1f} {yy + T / 2 - 70 * sc:.1f}) scale({sc})">'
                       f'<path fill="{fg}" d="{gen.d_attr(lt)}"/></g>')
        # nuancier
        sx = L - 190
        for j, (c, n) in enumerate(((pastel, "principal"), (accent, "accent"), (encre, "encre"), (fond, "fond"))):
            yy = y + j * 70
            out.append(f'<rect x="{sx}" y="{yy}" width="54" height="54" rx="12" fill="{c}" stroke="#0001"/>')
            out.append(texte(sx + 66, yy + 24, c, 16, "#22252E", 700))
            out.append(texte(sx + 66, yy + 46, n, 15, "#6B6F78", 400))
    out.append("</svg>")
    with open(os.path.join(ICI, "palettes.svg"), "w") as fh:
        fh.write("\n".join(out))


if __name__ == "__main__":
    planche()
