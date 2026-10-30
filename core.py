"""Génération de boucles 100 % hors-ligne, Python pur (heapq + sqlite3)."""
import heapq, json, math, random, sqlite3, time


class Carte:
    def __init__(self, chemin_db):
        db = sqlite3.connect(chemin_db)
        self.nodes = {i: (lat, lon, ele) for i, lat, lon, ele in db.execute("SELECT * FROM nodes")}
        self.adj = {}
        for u, v, l, t, g in db.execute("SELECT * FROM edges"):
            self.adj.setdefault(u, []).append((v, l, t, json.loads(g)))
        self.centre = db.execute("SELECT lat, lon, rayon FROM meta").fetchone()
        db.close()
        self.depart = self.plus_proche(*self.centre[:2])

    def _dist_m(self, lat1, lon1, lat2, lon2):
        k = math.cos(math.radians(lat1))
        return math.hypot((lat2 - lat1) * 111000, (lon2 - lon1) * 111000 * k)

    def plus_proche(self, lat, lon):
        return min(self.nodes, key=lambda n: self._dist_m(lat, lon, *self.nodes[n][:2]))

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
        cost, prev, lg = {src: 0}, {}, {src: 0}
        pq = [(0, src)]
        while pq:
            c, u = heapq.heappop(pq)
            if c > cost[u]:
                continue
            if u == cible:
                break
            for v, l, t, _ in self.adj.get(u, ()):
                nc = c + cout(u, v, l, t)
                if nc < cost.get(v, 1e18):
                    cost[v], prev[v], lg[v] = nc, u, lg[u] + l
                    heapq.heappush(pq, (nc, v))
        return cost, prev, lg

    @staticmethod
    def chemin(prev, n):
        p = [n]
        while n in prev:
            n = prev[n]
            p.append(n)
        return p[::-1]

    def d_plus(self, chemin):
        e = [self.nodes[n][2] for n in chemin]
        return sum(max(0, b - a) for a, b in zip(e, e[1:]))

    def coords(self, chemin):
        pts = []
        for u, v in zip(chemin, chemin[1:]):
            g = next((g for w, _, _, g in self.adj[u] if w == v), None)
            pts += g or [self.nodes[u][:2], self.nodes[v][:2]]
        return pts

    def generer(self, distance, denivele, preference="hybride", depart=None, max_s=20):
        debut, dep, bruit = time.time(), depart or self.depart, {}

        def facteur(t):
            if preference == "trail":
                return 0.8 if t else 5
            if preference == "route":
                return 5 if t else 1
            return 1

        def cout(u, v, l, t, deja=()):
            b = bruit.setdefault((u, v), random.uniform(0.6, 1.4))
            return l * facteur(t) * b * (100 if (u, v) in deja or (v, u) in deja else 1)

        _, prev_a, lg_a = self.dijkstra(dep, cout)
        demi = distance / 2
        cands = [n for n, l in lg_a.items() if 0.7 * demi <= l <= 1.3 * demi]
        random.shuffle(cands)

        resultats = []
        for n in cands[:30]:
            if time.time() - debut > max_s:
                break
            aller = self.chemin(prev_a, n)
            deja = set(zip(aller, aller[1:]))
            _, prev_r, lg_r = self.dijkstra(n, lambda u, v, l, t: cout(u, v, l, t, deja), cible=dep)
            if dep not in lg_r:
                continue
            total = lg_a[n] + lg_r[dep]
            if not 0.8 * distance <= total <= 1.2 * distance:
                continue
            boucle = aller + self.chemin(prev_r, dep)[1:]
            dp = self.d_plus(boucle)
            score = abs(total - distance) + 3 * abs(dp - denivele)
            resultats.append((score, boucle, total, dp))

        if not resultats:
            return None
        _, boucle, total, dp = min(resultats, key=lambda r: r[0])
        return {"coords": self.coords(boucle), "distance": total, "denivele": dp}