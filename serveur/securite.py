"""Mots de passe (scrypt, sel aléatoire), jetons de session (aléatoires, stockés hachés) et limites de débit."""
import collections, hashlib, hmac, secrets, threading, time

N, R, P = 2 ** 14, 8, 1


def hacher_mdp(mdp):
    sel = secrets.token_bytes(16)
    h = hashlib.scrypt(mdp.encode(), salt=sel, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${sel.hex()}${h.hex()}"


def verifier_mdp(mdp, stocke):
    try:
        _, n, r, p, sel, h = stocke.split("$")
        calc = hashlib.scrypt(mdp.encode(), salt=bytes.fromhex(sel), n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc.hex(), h)


def nouveau_jeton():
    """(jeton donné au client, empreinte gardée en base) : une fuite de la base ne donne pas les sessions."""
    j = secrets.token_urlsafe(32)
    return j, empreinte(j)


def empreinte(jeton):
    return hashlib.sha256(jeton.encode()).hexdigest()


class Limiteur:
    """Au plus n appels par fenêtre de s secondes et par clé (adresse IP + action)."""

    def __init__(self):
        self.appels, self.verrou = collections.defaultdict(collections.deque), threading.Lock()

    def autoriser(self, cle, n, s=60):
        now = time.time()
        with self.verrou:
            q = self.appels[cle]
            while q and now - q[0] > s:
                q.popleft()
            if len(q) >= n:
                return False
            q.append(now)
            return True
