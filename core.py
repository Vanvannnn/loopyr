"""Génération de boucles 100 % hors-ligne, Python pur (heapq + sqlite3)."""
import heapq, json, math, random, sqlite3, time

CASE = 0.002  # degrés : taille des cases de l'index (~220 m x 160 m)


class Carte:
    def __init__(self, chemin_db):
        db = sqlite3.connect(chemin_db)
        self.nodes = {i: (lat, lon, ele) for i, lat, lon, ele in db.execute("SELECT * FROM nodes")}
        self.adj = {}
        for u, v, l, t, g in db.execute("SELECT * FROM edges"):
            self.adj.setdefault(u, []).append((v, l, t, json.loads(g)))
        self.centre = db.execute("SELECT lat, lon, rayon FROM meta").fetchone()
        db.close()
        self.grille = {}
        for n, (lat, lon, _) in self.nodes.items():
            self.grille.setdefault(self._case(lat, lon), []).append(n)
        self.depart = self.plus_proche(*self.centre[:2])

    @property
    def distance_max(self):
        return 4 * self.centre[2]  # au-delà, la boucle sortirait de la zone embarquée

    @staticmethod
    def _case(lat, lon):
        return int(lat // CASE), int(lon // CASE)

    def _dist_m(self, lat1, lon1, lat2, lon2):
        k = math.cos(math.radians(lat1))
        return math.hypot((lat2 - lat1) * 111000, (lon2 - lon1) * 111000 * k)

    def plus_proche(self, lat, lon, max_m=None):
        """Nœud le plus proche (None si aucun à moins de max_m). Cherche case par case autour du point."""
        ci, cj = self._case(lat, lon)
        pas = CASE * 111000 * math.cos(math.radians(lat))  # côté le plus court d'une case, en m
        best = None
        for r in range(60):
            for i in range(ci - r, ci + r + 1):
                for j in range(cj - r, cj + r + 1):
                    if max(abs(i - ci), abs(j - cj)) != r:
                        continue
                    for n in self.grille.get((i, j), ()):
                        d = self._dist_m(lat, lon, *self.nodes[n][:2])
                        if best is None or d < best[0]:
                            best = (d, n)
            if best and best[0] <= r * pas:
                break
        if best is None:  # très loin de la zone : on parcourt tout
            best = min((self._dist_m(lat, lon, *v[:2]), n) for n, v in self.nodes.items())
        return None if max_m is not None and best[0] > max_m else best[1]

    def altitude(self, lat, lon):
        """Altitude (m) du nœud le plus proche, ou None hors de la zone."""
        n = self.plus_proche(lat, lon, max_m=300)
        return None if n is None else self.nodes[n][2]

    def dans_zone(self, lat, lon):
        return self._dist_m(lat, lon, *self.centre[:2]) < self.centre[2] * 0.8

    def segments(self):
        """Toutes les rues/chemins (sans doublons aller/retour) : liste de (trail, points)."""
        vus, segs = set(), []
        for u, voisins in self.adj.items():
            for v, l, t, g in voisins:
                cle = (min(u, v), max(u, v), round(l))
                if cle not in vus:
                    vus.add(cle)
                    segs.append((t, g or [self.nodes[u][:2], self.nodes[v][:2]]))
        return segs

    def dijkstra(self, src, cout, cible=None):
        """prev[v] = (u, k) : on arrive en v par l'arête adj[u][k] (il peut y en avoir plusieurs u -> v)."""
        cost, prev, lg = {src: 0}, {}, {src: 0}
        pq = [(0, src)]
        while pq:
            c, u = heapq.heappop(pq)
            if c > cost[u]:
                continue
            if u == cible:
                break
            for k, (v, l, t, _) in enumerate(self.adj.get(u, ())):
                nc = c + cout(u, v, l, t)
                if nc < cost.get(v, 1e18):
                    cost[v], prev[v], lg[v] = nc, (u, k), lg[u] + l
                    heapq.heappush(pq, (nc, v))
        return cost, prev, lg

    @staticmethod
    def chemin(prev, n):
        """Liste des arêtes (u, k) pour aller de la source à n."""
        aretes = []
        while n in prev:
            u, k = prev[n]
            aretes.append((u, k))
            n = u
        return aretes[::-1]

    def d_plus(self, aretes):
        return sum(max(0, self.nodes[self.adj[u][k][0]][2] - self.nodes[u][2]) for u, k in aretes)

    def coords(self, aretes):
        pts = []
        for u, k in aretes:
            v, _, _, g = self.adj[u][k]
            seg = g or [self.nodes[u][:2], self.nodes[v][:2]]
            pts += seg if not pts else seg[1:]  # le premier point = le dernier du tronçon précédent
        return pts

    def recouvrement(self, aretes):
        """Part de la distance parcourue deux fois (dans un sens ou dans l'autre)."""
        vus, double, total = set(), 0.0, 0.0
        for u, k in aretes:
            v, l, _, _ = self.adj[u][k]
            total += l
            if (min(u, v), max(u, v)) in vus:
                double += l
            vus.add((min(u, v), max(u, v)))
        return double / total if total else 0.0

    def generer(self, distance, denivele, preference="hybride", depart=None, max_s=6):
        """Plusieurs tours de recherche. À chaque tour, le poids donné aux pentes est ajusté
        selon le D+ obtenu : plus de pentes si on manque de D+, moins si on en a trop."""
        debut, dep = time.time(), depart or self.depart
        terrain = {"trail": (5, 0.8), "route": (1, 5)}.get(preference, (1, 1))  # (route, chemin)
        resultats, poids = [], 0.0  # poids > 0 : on cherche les pentes ; < 0 : on les évite

        while time.time() - debut < max_s:
            bruit = {}

            def cout(u, v, l, t, deja=()):
                b = bruit.setdefault((u, v), random.uniform(0.6, 1.4))
                pente = abs(self.nodes[v][2] - self.nodes[u][2]) / max(l, 1)
                relief = 1 / (1 + 25 * poids * pente) if poids >= 0 else 1 - 25 * poids * pente
                return l * terrain[t] * b * relief * (100 if (u, v) in deja or (v, u) in deja else 1)

            _, prev_a, lg_a = self.dijkstra(dep, cout)
            demi = distance / 2
            cands = [n for n, l in lg_a.items() if 0.7 * demi <= l <= 1.3 * demi]
            random.shuffle(cands)
            tour = []
            for n in cands[:10]:
                aller = self.chemin(prev_a, n)
                deja = {(u, self.adj[u][k][0]) for u, k in aller}
                _, prev_r, lg_r = self.dijkstra(n, lambda u, v, l, t: cout(u, v, l, t, deja), cible=dep)
                if dep not in lg_r:
                    continue
                total = lg_a[n] + lg_r[dep]
                if not 0.8 * distance <= total <= 1.2 * distance:
                    continue
                boucle = aller + self.chemin(prev_r, dep)
                dp, rec = self.d_plus(boucle), self.recouvrement(boucle)
                score = (3 * abs(total - distance) / distance + abs(dp - denivele) / max(denivele, 30)
                         + 2 * rec)
                tour.append((score, boucle, total, dp))
            if not tour:
                if not cands:
                    break
                continue
            resultats += tour
            best = min(resultats, key=lambda r: r[0])
            if best[0] < 0.15:  # assez bien : distance et D+ à quelques % près, peu de recouvrement
                break
            dp_tour = sorted(r[3] for r in tour)[len(tour) // 2]
            poids += 0.5 if dp_tour < denivele else -0.5
            poids = max(-2.0, min(4.0, poids))

        if not resultats:
            return None
        _, boucle, total, dp = min(resultats, key=lambda r: r[0])
        return {"coords": self.coords(boucle), "distance": total, "denivele": dp,
                "recouvrement": self.recouvrement(boucle)}
