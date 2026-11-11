"""Serveur Loopy (FastAPI) : comptes, profils, itinéraires, activités, communauté, Strava, génération de
boucles pour le site, et le site lui-même (dossier website/). Lancer : uvicorn serveur.app:app
Un seul système de comptes : l'app (jeton Bearer) et le site (même jeton, en cookie HttpOnly) l'utilisent."""
import contextlib, json, os, re, secrets, smtplib, sys, time, uuid
from email.message import EmailMessage
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # modules partagés (racine)
import boucles  # noqa: E402
from geo import reduire, rogner  # noqa: E402
from gpx import gpx, gpx_itineraire, nom_itineraire  # noqa: E402
from serveur import config, db, securite, strava  # noqa: E402

@contextlib.asynccontextmanager
async def cycle(_app):
    db.initialiser()
    yield
    db.fermer()


app = FastAPI(title="Loopy", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=cycle)
limiteur = securite.Limiteur()
routeur = boucles.BRouter()
COOKIE = "loopy_session"
SESSION = 90 * 86400
NOM_RE = re.compile(r"^[a-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
Visibilite = Literal["public", "abonnes", "prive"]
Sport = Literal["course", "velo"]
Ressenti = Literal["facile", "bien", "dur", "epuisant"]


def base():
    with db.reserve().connection() as con:
        yield con


def ip(req: Request):
    return req.client.host if req.client else "?"


def limiter(req, action, n, s=60):
    if not limiteur.autoriser(f"{ip(req)}:{action}", n, s):
        raise HTTPException(429, "Trop de tentatives : patiente une minute")


def jeton_de(req: Request):
    auth = req.headers.get("authorization", "")
    return auth[7:] if auth.lower().startswith("bearer ") else req.cookies.get(COOKIE)


def utilisateur_optionnel(req: Request, con=Depends(base)):
    j = jeton_de(req)
    if not j:
        return None
    # session par cookie (le site) : une requête qui modifie doit venir de notre propre code (en-tête qu'un
    # formulaire d'un autre site ne peut pas ajouter), en plus du cookie SameSite=Lax
    if not req.headers.get("authorization") and req.method not in ("GET", "HEAD") and \
            req.headers.get("x-loopy") != "1":
        raise HTTPException(403, "Requête refusée")
    return con.execute("SELECT u.* FROM sessions s JOIN utilisateurs u ON u.id=s.utilisateur "
                       "WHERE s.jeton=%s AND s.expire>%s", (securite.empreinte(j), time.time())).fetchone()


def utilisateur(u=Depends(utilisateur_optionnel)):
    if u is None:
        raise HTTPException(401, "Connecte-toi pour continuer")
    return u


# --- comptes ---
class Inscription(BaseModel):
    email: str = Field(max_length=200)
    nom: str
    mot_de_passe: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Adresse e-mail invalide")
        return v

    @field_validator("nom")
    @classmethod
    def _nom(cls, v):
        v = v.strip().lower()
        if not NOM_RE.match(v):
            raise ValueError("Nom d'utilisateur : 3 à 30 caractères parmi a-z, 0-9, _ . -")
        return v


class Connexion(BaseModel):
    email: str
    mot_de_passe: str


def ouvrir_session(con, uid, rep: Response):
    j, h = securite.nouveau_jeton()
    con.execute("INSERT INTO sessions VALUES (%s,%s,%s)", (h, uid, time.time() + SESSION))
    rep.set_cookie(COOKIE, j, max_age=SESSION, httponly=True, samesite="lax", secure=config.COOKIE_SECURE)
    return j


@app.post("/api/comptes", status_code=201)
def inscrire(d: Inscription, req: Request, rep: Response, con=Depends(base)):
    limiter(req, "inscription", 5)
    if con.execute("SELECT 1 FROM utilisateurs WHERE email=%s OR nom=%s", (d.email, d.nom)).fetchone():
        raise HTTPException(409, "Cette adresse ou ce nom d'utilisateur est déjà pris")
    cur = con.execute("INSERT INTO utilisateurs(email, nom, mdp, cree) VALUES (%s,%s,%s,%s) RETURNING id",
                      (d.email, d.nom, securite.hacher_mdp(d.mot_de_passe), time.time()))
    u = con.execute("SELECT * FROM utilisateurs WHERE id=%s", (cur.fetchone()["id"],)).fetchone()
    return {"jeton": ouvrir_session(con, u["id"], rep), "utilisateur": moi_public(u)}


@app.post("/api/sessions")
def connecter(d: Connexion, req: Request, rep: Response, con=Depends(base)):
    limiter(req, "connexion", 10)
    u = con.execute("SELECT * FROM utilisateurs WHERE email=%s", (d.email.strip().lower(),)).fetchone()
    if not u or not securite.verifier_mdp(d.mot_de_passe, u["mdp"]):
        raise HTTPException(401, "E-mail ou mot de passe incorrect")
    return {"jeton": ouvrir_session(con, u["id"], rep), "utilisateur": moi_public(u)}


@app.delete("/api/sessions", status_code=204)
def deconnecter(req: Request, rep: Response, con=Depends(base)):
    j = jeton_de(req)
    if j:
        con.execute("DELETE FROM sessions WHERE jeton=%s", (securite.empreinte(j),))
    rep.delete_cookie(COOKIE)


class Oubli(BaseModel):
    email: str


class Reinit(BaseModel):
    jeton: str
    mot_de_passe: str = Field(min_length=8, max_length=200)


def envoyer_mail(dest, sujet, texte):
    if not config.SMTP["hote"]:  # pas de serveur d'envoi configuré (développement) : le lien va dans le journal
        print(f"[mail non envoyé, SMTP non configuré] À {dest} : {sujet}\n{texte}", flush=True)
        return
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = config.SMTP["expediteur"] or config.SMTP["utilisateur"], dest, sujet
    m.set_content(texte)
    with smtplib.SMTP(config.SMTP["hote"], int(config.SMTP["port"] or 587), timeout=20) as s:
        s.starttls()
        if config.SMTP["utilisateur"]:
            s.login(config.SMTP["utilisateur"], config.SMTP["mot_de_passe"])
        s.send_message(m)


@app.post("/api/mot-de-passe/oubli", status_code=202)
def oubli(d: Oubli, req: Request, con=Depends(base)):
    limiter(req, "oubli", 3)
    u = con.execute("SELECT * FROM utilisateurs WHERE email=%s", (d.email.strip().lower(),)).fetchone()
    if u:  # même réponse que l'adresse existe ou non : on ne révèle pas qui a un compte
        j, h = securite.nouveau_jeton()
        con.execute("INSERT INTO reinits VALUES (%s,%s,%s)", (h, u["id"], time.time() + 3600))
        envoyer_mail(u["email"], "Loopy : nouveau mot de passe",
                     f"Pour choisir un nouveau mot de passe (lien valable 1 heure) :\n"
                     f"{config.URL_PUBLIQUE}/reinitialiser.html#{j}\n\nSi tu n'as rien demandé, ignore ce message.")
    return {"message": "Si un compte existe pour cette adresse, un e-mail vient de partir."}


@app.post("/api/mot-de-passe/reinit")
def reinit(d: Reinit, req: Request, con=Depends(base)):
    limiter(req, "reinit", 10)
    h = securite.empreinte(d.jeton)
    r = con.execute("SELECT * FROM reinits WHERE jeton=%s AND expire>%s", (h, time.time())).fetchone()
    if not r:
        raise HTTPException(400, "Lien expiré ou déjà utilisé")
    con.execute("UPDATE utilisateurs SET mdp=%s WHERE id=%s", (securite.hacher_mdp(d.mot_de_passe), r["utilisateur"]))
    con.execute("DELETE FROM reinits WHERE utilisateur=%s", (r["utilisateur"],))
    con.execute("DELETE FROM sessions WHERE utilisateur=%s", (r["utilisateur"],))  # déconnecte partout
    return {"message": "Mot de passe changé : connecte-toi"}


# --- profil ---
def moi_public(u):
    return {"nom": u["nom"], "email": u["email"], "bio": u["bio"], "sport": u["sport"],
            "preferences": json.loads(u["preferences"] or "{}"),
            "visibilite_profil": u["visibilite_profil"], "visibilite_activites": u["visibilite_activites"],
            "masquer_depart": bool(u["masquer_depart"])}


class Profil(BaseModel):
    bio: Optional[str] = Field(None, max_length=500)
    sport: Optional[Sport] = None
    preferences: Optional[dict] = None
    visibilite_profil: Optional[Visibilite] = None
    visibilite_activites: Optional[Visibilite] = None
    masquer_depart: Optional[bool] = None


@app.get("/api/moi")
def moi(u=Depends(utilisateur), con=Depends(base)):
    return {**moi_public(u), "stats": stats(con, u["id"]), "strava": etat_strava(con, u["id"])}


@app.patch("/api/moi")
def modifier_moi(d: Profil, u=Depends(utilisateur), con=Depends(base)):
    champs = d.model_dump(exclude_none=True)
    if "preferences" in champs:
        if len(json.dumps(champs["preferences"])) > 2000:
            raise HTTPException(422, "Préférences trop longues")
        champs["preferences"] = json.dumps(champs["preferences"])
    if "masquer_depart" in champs:
        champs["masquer_depart"] = int(champs["masquer_depart"])
    for k, v in champs.items():  # noms de colonnes : uniquement ceux du modèle Profil
        con.execute(f"UPDATE utilisateurs SET {k}=%s WHERE id=%s", (v, u["id"]))
    return moi_public(con.execute("SELECT * FROM utilisateurs WHERE id=%s", (u["id"],)).fetchone())


@app.delete("/api/moi", status_code=204)
def supprimer_compte(rep: Response, u=Depends(utilisateur), con=Depends(base)):
    """Suppression du compte et de toutes ses données (droit à l'effacement)."""
    uid = u["id"]
    ligne = con.execute("SELECT acces FROM strava WHERE utilisateur=%s", (uid,)).fetchone()
    if ligne:
        strava.revoquer(ligne["acces"])
    with con.transaction():  # tout ou rien
        _effacer_compte(con, uid)
    rep.delete_cookie(COOKIE)


def _effacer_compte(con, uid):
    ids = [r["id"] for r in con.execute("SELECT id FROM activites WHERE utilisateur=%s", (uid,))]
    for a in ids:
        con.execute("DELETE FROM jaimes WHERE activite=%s", (a,))
        con.execute("DELETE FROM commentaires WHERE activite=%s", (a,))
    for t, c in (("activites", "utilisateur"), ("itineraires", "utilisateur"), ("sessions", "utilisateur"),
                 ("reinits", "utilisateur"), ("strava", "utilisateur"), ("etats_oauth", "utilisateur"),
                 ("jaimes", "utilisateur"), ("commentaires", "utilisateur"), ("abonnements", "suiveur"),
                 ("abonnements", "suivi"), ("utilisateurs", "id")):
        con.execute(f"DELETE FROM {t} WHERE {c}=%s", (uid,))


def stats(con, uid, visibles=None):
    """Totaux par sport et km des 12 dernières semaines. visibles : clause SQL limitant les activités."""
    filtre = f" AND {visibles}" if visibles else ""
    par_sport = {r["sport"]: {"nombre": r["n"], "distance": r["d"] or 0, "duree": r["t"] or 0, "denivele": r["z"] or 0}
                 for r in con.execute(f"SELECT sport, COUNT(*) n, SUM(distance) d, SUM(duree) t, SUM(denivele) z "
                                      f"FROM activites WHERE utilisateur=%s{filtre} GROUP BY sport", (uid,))}
    debut = time.time() - 84 * 86400
    semaines = [0.0] * 12
    for r in con.execute(f"SELECT debut, distance FROM activites WHERE utilisateur=%s AND debut>%s{filtre}", (uid, debut)):
        semaines[min(11, int((r["debut"] - debut) // (7 * 86400)))] += r["distance"] / 1000
    return {"par_sport": par_sport, "km_par_semaine": [round(k, 1) for k in semaines],
            "itineraires": con.execute("SELECT COUNT(*) AS n FROM itineraires WHERE utilisateur=%s", (uid,)).fetchone()["n"]}


# --- visibilité ---
def suit(con, suiveur, suivi):
    return suiveur is not None and con.execute("SELECT 1 FROM abonnements WHERE suiveur=%s AND suivi=%s",
                                               (suiveur, suivi)).fetchone() is not None


def peut_voir(con, lecteur, proprietaire, visibilite):
    lid = lecteur["id"] if lecteur else None
    if lid == proprietaire:
        return True
    return visibilite == "public" or (visibilite == "abonnes" and suit(con, lid, proprietaire))


def clause_visible(con, lecteur, proprietaire):
    """Clause SQL des activités de proprietaire que lecteur peut voir (valeurs fixes, pas d'entrée utilisateur)."""
    lid = lecteur["id"] if lecteur else None
    if lid == proprietaire:
        return None
    return "visibilite IN ('public','abonnes')" if suit(con, lid, proprietaire) else "visibilite='public'"


def trace_publique(coords, proprietaire, lecteur):
    """Le tracé tel que les autres le voient : sans les 300 premiers et derniers mètres si demandé."""
    if lecteur and lecteur["id"] == proprietaire["id"]:
        return reduire(coords)
    return reduire(rogner(coords) if proprietaire["masquer_depart"] else coords)


# --- utilisateurs et abonnements ---
@app.get("/api/utilisateurs")
def chercher_utilisateurs(q: str = "", lecteur=Depends(utilisateur_optionnel), con=Depends(base)):
    q = q.strip().lower()[:30]
    if len(q) < 2:
        return []
    lignes = con.execute("SELECT * FROM utilisateurs WHERE nom ILIKE %s AND visibilite_profil!='prive' LIMIT 20",
                         (q.replace("%", "").replace("_", r"\_") + "%",))
    return [carte_utilisateur(con, u, lecteur) for u in lignes]


def carte_utilisateur(con, u, lecteur):
    return {"nom": u["nom"], "sport": u["sport"],
            "suivi": suit(con, lecteur["id"] if lecteur else None, u["id"])}


@app.get("/api/utilisateurs/{nom}")
def profil_public(nom: str, lecteur=Depends(utilisateur_optionnel), con=Depends(base)):
    u = con.execute("SELECT * FROM utilisateurs WHERE nom=%s", (nom.lower(),)).fetchone()
    if not u or not peut_voir(con, lecteur, u["id"], u["visibilite_profil"]):
        raise HTTPException(404, "Profil introuvable ou privé")
    visibles = clause_visible(con, lecteur, u["id"])
    acts = con.execute(f"SELECT * FROM activites WHERE utilisateur=%s{' AND ' + visibles if visibles else ''} "
                       "ORDER BY debut DESC LIMIT 30", (u["id"],)).fetchall()
    n = lambda sql: con.execute(sql, (u["id"],)).fetchone()["n"]  # noqa: E731
    return {**carte_utilisateur(con, u, lecteur), "bio": u["bio"], "stats": stats(con, u["id"], visibles),
            "abonnes": n("SELECT COUNT(*) AS n FROM abonnements WHERE suivi=%s"),
            "abonnements": n("SELECT COUNT(*) AS n FROM abonnements WHERE suiveur=%s"),
            "activites": [resume_activite(con, a, u, lecteur) for a in acts]}


@app.post("/api/utilisateurs/{nom}/abonnement", status_code=204)
def suivre(nom: str, u=Depends(utilisateur), con=Depends(base)):
    cible = con.execute("SELECT id FROM utilisateurs WHERE nom=%s", (nom.lower(),)).fetchone()
    if not cible or cible["id"] == u["id"]:
        raise HTTPException(404, "Utilisateur introuvable")
    con.execute("INSERT INTO abonnements VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (u["id"], cible["id"], time.time()))


@app.delete("/api/utilisateurs/{nom}/abonnement", status_code=204)
def ne_plus_suivre(nom: str, u=Depends(utilisateur), con=Depends(base)):
    con.execute("DELETE FROM abonnements WHERE suiveur=%s AND suivi=(SELECT id FROM utilisateurs WHERE nom=%s)",
                (u["id"], nom.lower()))


@app.get("/api/moi/abonnements")
def mes_abonnements(u=Depends(utilisateur), con=Depends(base)):
    suivis = con.execute("SELECT u.* FROM abonnements a JOIN utilisateurs u ON u.id=a.suivi WHERE a.suiveur=%s", (u["id"],))
    abonnes = con.execute("SELECT u.* FROM abonnements a JOIN utilisateurs u ON u.id=a.suiveur WHERE a.suivi=%s", (u["id"],))
    return {"abonnements": [carte_utilisateur(con, x, u) for x in suivis],
            "abonnes": [carte_utilisateur(con, x, u) for x in abonnes]}


# --- itinéraires (boucles prévues) ---
Coord = tuple[float, float]


class NouvelItineraire(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    sport: Sport
    distance: float = Field(gt=0, lt=1_000_000)
    montee: Optional[float] = None
    coords: list[Coord] = Field(min_length=2, max_length=50_000)
    ele: Optional[list[Optional[float]]] = None
    resume_voies: Optional[dict] = None
    favori: bool = False
    partage: bool = False


class ModifItineraire(BaseModel):
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    favori: Optional[bool] = None
    partage: Optional[bool] = None


def itin_json(r, proprietaire, lecteur, complet=True):
    coords = json.loads(r["coords"])
    d = {"id": r["id"], "nom": r["nom"], "sport": r["sport"], "distance": r["distance"], "montee": r["montee"],
         "favori": bool(r["favori"]), "partage": bool(r["partage"]), "cree": r["cree"], "auteur": proprietaire["nom"],
         "resume_voies": json.loads(r["resume"] or "null"), "trace": trace_publique(coords, proprietaire, lecteur)}
    if complet and lecteur and lecteur["id"] == proprietaire["id"]:
        d["coords"], d["ele"] = coords, json.loads(r["ele"] or "null")
    return d


@app.get("/api/itineraires")
def mes_itineraires(favoris: bool = False, u=Depends(utilisateur), con=Depends(base)):
    sql = "SELECT * FROM itineraires WHERE utilisateur=%s" + (" AND favori=1" if favoris else "") + " ORDER BY cree DESC"
    return [itin_json(r, u, u, complet=False) for r in con.execute(sql, (u["id"],))]


@app.post("/api/itineraires", status_code=201)
def creer_itineraire(d: NouvelItineraire, u=Depends(utilisateur), con=Depends(base)):
    i = uuid.uuid4().hex[:16]
    ele = d.ele if d.ele and len(d.ele) == len(d.coords) else None
    con.execute("INSERT INTO itineraires VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (i, u["id"], d.nom, d.sport, d.distance, d.montee, json.dumps(d.coords), json.dumps(ele),
                 json.dumps(d.resume_voies) if d.resume_voies else None, int(d.favori), int(d.partage), time.time()))
    return itin_json(con.execute("SELECT * FROM itineraires WHERE id=%s", (i,)).fetchone(), u, u)


def itin_de(con, i, u):
    r = con.execute("SELECT * FROM itineraires WHERE id=%s AND utilisateur=%s", (i, u["id"])).fetchone()
    if not r:
        raise HTTPException(404, "Itinéraire introuvable")
    return r


@app.get("/api/itineraires/{i}")
def lire_itineraire(i: str, lecteur=Depends(utilisateur_optionnel), con=Depends(base)):
    r = con.execute("SELECT * FROM itineraires WHERE id=%s", (i,)).fetchone()
    if not r or not (r["partage"] or (lecteur and lecteur["id"] == r["utilisateur"])):
        raise HTTPException(404, "Itinéraire introuvable")
    return itin_json(r, con.execute("SELECT * FROM utilisateurs WHERE id=%s", (r["utilisateur"],)).fetchone(), lecteur)


@app.patch("/api/itineraires/{i}")
def modifier_itineraire(i: str, d: ModifItineraire, u=Depends(utilisateur), con=Depends(base)):
    itin_de(con, i, u)
    for k, v in d.model_dump(exclude_none=True).items():  # colonnes du modèle uniquement
        con.execute(f"UPDATE itineraires SET {k}=%s WHERE id=%s", (int(v) if isinstance(v, bool) else v, i))
    return itin_json(itin_de(con, i, u), u, u)


@app.delete("/api/itineraires/{i}", status_code=204)
def supprimer_itineraire(i: str, u=Depends(utilisateur), con=Depends(base)):
    itin_de(con, i, u)
    con.execute("DELETE FROM itineraires WHERE id=%s", (i,))


@app.get("/api/itineraires/{i}/gpx")
def gpx_d_itineraire(i: str, u=Depends(utilisateur), con=Depends(base)):
    r = itin_de(con, i, u)
    texte = gpx_itineraire(json.loads(r["coords"]), r["sport"], r["distance"], r["montee"],
                           json.loads(r["ele"] or "null"), r["nom"])
    return Response(texte, media_type="application/gpx+xml", headers={
        "Content-Disposition": f'attachment; filename="{nom_itineraire(r["distance"], r["sport"])}"'})


@app.get("/api/communaute/itineraires")
def itineraires_partages(sport: Optional[Sport] = None, lecteur=Depends(utilisateur_optionnel), con=Depends(base)):
    sql = ("SELECT i.*, u.nom un, u.masquer_depart um FROM itineraires i JOIN utilisateurs u ON u.id=i.utilisateur "
           "WHERE i.partage=1 AND u.visibilite_profil!='prive'" + (" AND i.sport=%s" if sport else "") +
           " ORDER BY i.cree DESC LIMIT 50")
    out = []
    for r in con.execute(sql, (sport,) if sport else ()):
        prop = {"id": r["utilisateur"], "nom": r["un"], "masquer_depart": r["um"]}
        out.append(itin_json(r, prop, lecteur, complet=False))
    return out


# --- activités (réellement faites) ---
class Activite(BaseModel):
    nom: Optional[str] = Field(None, max_length=100)
    sport: Sport = "course"
    debut: float
    duree: Optional[float] = None
    duree_totale: Optional[float] = None
    distance: float = Field(ge=0, lt=2_000_000)
    denivele: Optional[float] = None
    splits: list[float] = Field(default_factory=list, max_length=2000)
    segments: list[list[tuple[float, float, float, Optional[float]]]] = Field(min_length=1)
    itineraire: Optional[str] = None
    visibilite: Optional[Visibilite] = None
    description: Optional[str] = Field(None, max_length=2000)
    ressenti: Optional[Ressenti] = None

    @field_validator("segments")
    @classmethod
    def _taille(cls, v):
        if sum(len(s) for s in v) > 200_000:
            raise ValueError("Trop de points")
        if not any(v):
            raise ValueError("Activité sans point GPS")
        return v


class ModifActivite(BaseModel):
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    visibilite: Optional[Visibilite] = None
    description: Optional[str] = Field(None, max_length=2000)
    ressenti: Optional[Ressenti] = None


def resume_activite(con, a, proprietaire, lecteur):
    pts = [(p[1], p[2]) for s in json.loads(a["segments"]) for p in s]
    lid = lecteur["id"] if lecteur else None
    return {"id": a["id"], "id_client": a["id_client"] if lid == proprietaire["id"] else None, "nom": a["nom"],
            "sport": a["sport"], "debut": a["debut"], "duree": a["duree"], "distance": a["distance"],
            "denivele": a["denivele"], "visibilite": a["visibilite"], "auteur": proprietaire["nom"],
            "description": a["description"] or "",
            "ressenti": a["ressenti"] if lid == proprietaire["id"] else None,  # personnel : l'auteur seulement
            "trace": trace_publique(pts, proprietaire, lecteur),
            "jaimes": con.execute("SELECT COUNT(*) AS n FROM jaimes WHERE activite=%s", (a["id"],)).fetchone()["n"],
            "aime": lid is not None and con.execute("SELECT 1 FROM jaimes WHERE activite=%s AND utilisateur=%s",
                                                    (a["id"], lid)).fetchone() is not None,
            "commentaires": con.execute("SELECT COUNT(*) AS n FROM commentaires WHERE activite=%s", (a["id"],)).fetchone()["n"],
            "strava": {"statut": a["strava_statut"], "erreur": a["strava_erreur"],
                       "activite": a["strava_activite"]} if lid == proprietaire["id"] else None}


@app.put("/api/moi/activites/{id_client}")
def enregistrer_activite(id_client: str, d: Activite, u=Depends(utilisateur), con=Depends(base)):
    """Envoi (ou renvoi) d'une activité terminée depuis l'app. Idempotent : même id_client, même activité."""
    if not re.match(r"^[\w.-]{1,40}$", id_client):
        raise HTTPException(422, "Identifiant invalide")
    nom = d.nom or f"{'Sortie vélo' if d.sport == 'velo' else 'Course'} du {time.strftime('%d/%m/%Y', time.localtime(d.debut))}"
    existante = con.execute("SELECT * FROM activites WHERE utilisateur=%s AND id_client=%s", (u["id"], id_client)).fetchone()
    vals = (nom, d.sport, d.debut, d.duree, d.duree_totale, d.distance, d.denivele, json.dumps(d.splits),
            json.dumps(d.segments), d.itineraire)
    if existante:
        con.execute("UPDATE activites SET nom=%s, sport=%s, debut=%s, duree=%s, duree_totale=%s, distance=%s, denivele=%s, "
                    "splits=%s, segments=%s, itineraire=%s WHERE id=%s", (*vals, existante["id"]))
        i = existante["id"]
    else:
        i = uuid.uuid4().hex[:16]
        con.execute("INSERT INTO activites(id, utilisateur, id_client, nom, sport, debut, duree, duree_totale, distance, "
                    "denivele, splits, segments, itineraire, visibilite, cree) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (i, u["id"], id_client, *vals, d.visibilite or u["visibilite_activites"], time.time()))
    if d.visibilite:
        con.execute("UPDATE activites SET visibilite=%s WHERE id=%s", (d.visibilite, i))
    if d.description is not None or d.ressenti is not None:
        con.execute("UPDATE activites SET description=COALESCE(%s, description), ressenti=%s WHERE id=%s",
                    (d.description, d.ressenti, i))
    return resume_activite(con, con.execute("SELECT * FROM activites WHERE id=%s", (i,)).fetchone(), u, u)


@app.get("/api/moi/activites")
def mes_activites(u=Depends(utilisateur), con=Depends(base)):
    return [resume_activite(con, a, u, u)
            for a in con.execute("SELECT * FROM activites WHERE utilisateur=%s ORDER BY debut DESC", (u["id"],))]


def activite_visible(con, i, lecteur):
    a = con.execute("SELECT * FROM activites WHERE id=%s", (i,)).fetchone()
    if not a:
        raise HTTPException(404, "Activité introuvable")
    prop = con.execute("SELECT * FROM utilisateurs WHERE id=%s", (a["utilisateur"],)).fetchone()
    if not peut_voir(con, lecteur, prop["id"], a["visibilite"]):
        raise HTTPException(404, "Activité introuvable")
    return a, prop


@app.get("/api/activites/{i}")
def lire_activite(i: str, lecteur=Depends(utilisateur_optionnel), con=Depends(base)):
    a, prop = activite_visible(con, i, lecteur)
    return {**resume_activite(con, a, prop, lecteur), "splits": json.loads(a["splits"] or "[]")}


def mon_activite(con, i, u):
    a = con.execute("SELECT * FROM activites WHERE id=%s AND utilisateur=%s", (i, u["id"])).fetchone()
    if not a:
        raise HTTPException(404, "Activité introuvable")
    return a


@app.patch("/api/activites/{i}")
def modifier_activite(i: str, d: ModifActivite, u=Depends(utilisateur), con=Depends(base)):
    mon_activite(con, i, u)
    for k, v in d.model_dump(exclude_none=True).items():  # colonnes du modèle uniquement
        con.execute(f"UPDATE activites SET {k}=%s WHERE id=%s", (v, i))
    return resume_activite(con, mon_activite(con, i, u), u, u)


@app.delete("/api/activites/{i}", status_code=204)
def supprimer_activite(i: str, u=Depends(utilisateur), con=Depends(base)):
    mon_activite(con, i, u)
    for t, c in (("jaimes", "activite"), ("commentaires", "activite"), ("activites", "id")):
        con.execute(f"DELETE FROM {t} WHERE {c}=%s", (i,))


def act_dict(a):
    return {"sport": a["sport"], "nom": a["nom"], "debut": a["debut"],
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(a["debut"])), "segments": json.loads(a["segments"])}


@app.get("/api/activites/{i}/gpx")
def gpx_d_activite(i: str, u=Depends(utilisateur), con=Depends(base)):
    a = mon_activite(con, i, u)
    return Response(gpx(act_dict(a)), media_type="application/gpx+xml",
                    headers={"Content-Disposition": f'attachment; filename="loopy-{a["id_client"]}.gpx"'})


@app.get("/api/fil")
def fil(u=Depends(utilisateur), con=Depends(base)):
    """Activités des personnes suivies (et les miennes), visibles par moi, les plus récentes d'abord."""
    lignes = con.execute(
        "SELECT a.* FROM activites a WHERE a.utilisateur=%s OR (a.visibilite IN ('public','abonnes') AND a.utilisateur IN "
        "(SELECT suivi FROM abonnements WHERE suiveur=%s)) ORDER BY a.debut DESC LIMIT 50", (u["id"], u["id"])).fetchall()
    return [resume_activite(con, a, con.execute("SELECT * FROM utilisateurs WHERE id=%s", (a["utilisateur"],)).fetchone(), u)
            for a in lignes]


@app.get("/api/communaute/activites")
def decouvrir(lecteur=Depends(utilisateur_optionnel), con=Depends(base)):
    lignes = con.execute("SELECT a.* FROM activites a JOIN utilisateurs u ON u.id=a.utilisateur WHERE a.visibilite='public' "
                         "AND u.visibilite_profil='public' ORDER BY a.debut DESC LIMIT 30").fetchall()
    return [resume_activite(con, a, con.execute("SELECT * FROM utilisateurs WHERE id=%s", (a["utilisateur"],)).fetchone(),
                            lecteur) for a in lignes]


@app.post("/api/activites/{i}/jaime", status_code=204)
def aimer(i: str, u=Depends(utilisateur), con=Depends(base)):
    activite_visible(con, i, u)
    con.execute("INSERT INTO jaimes VALUES (%s,%s) ON CONFLICT DO NOTHING", (u["id"], i))


@app.delete("/api/activites/{i}/jaime", status_code=204)
def ne_plus_aimer(i: str, u=Depends(utilisateur), con=Depends(base)):
    con.execute("DELETE FROM jaimes WHERE utilisateur=%s AND activite=%s", (u["id"], i))


class Commentaire(BaseModel):
    texte: str = Field(min_length=1, max_length=1000)


@app.get("/api/activites/{i}/commentaires")
def commentaires(i: str, lecteur=Depends(utilisateur_optionnel), con=Depends(base)):
    activite_visible(con, i, lecteur)
    return [{"id": r["id"], "auteur": r["nom"], "texte": r["texte"], "cree": r["cree"]} for r in con.execute(
        "SELECT c.*, u.nom FROM commentaires c JOIN utilisateurs u ON u.id=c.utilisateur WHERE activite=%s ORDER BY cree", (i,))]


@app.post("/api/activites/{i}/commentaires", status_code=201)
def commenter(i: str, d: Commentaire, req: Request, u=Depends(utilisateur), con=Depends(base)):
    limiter(req, "commentaire", 20)
    activite_visible(con, i, u)
    con.execute("INSERT INTO commentaires(utilisateur, activite, texte, cree) VALUES (%s,%s,%s,%s)",
                (u["id"], i, d.texte.strip(), time.time()))
    return commentaires(i, u, con)


# --- génération de boucles (pour le site ; l'app appelle le moteur directement) ---
class Demande(BaseModel):
    sport: Sport
    distance_km: float = Field(gt=0, le=300)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    relief: Optional[Literal["plat", "vallonne"]] = None


@app.post("/api/boucles")
def generer_boucles(d: Demande, req: Request):
    limiter(req, "boucles", 6)
    try:
        out = boucles.generer((d.lat, d.lon), d.distance_km * 1000, d.sport, routeur, relief=d.relief)
    except ValueError as e:
        raise HTTPException(422, str(e))
    out["propositions"] = [boucles.alleger(p) for p in out["propositions"]]
    return out


# --- Strava ---
def etat_strava(con, uid):
    ligne = con.execute("SELECT nom, portee FROM strava WHERE utilisateur=%s", (uid,)).fetchone()
    return {"configure": config.strava_configure(), "connecte": bool(ligne),
            "athlete": ligne["nom"] if ligne else None}


def exiger_strava():
    if not config.strava_configure():
        raise HTTPException(503, "Strava n'est pas encore configuré sur ce serveur (voir docs/CONFIGURATION.md)")


@app.get("/api/strava")
def strava_etat(u=Depends(utilisateur), con=Depends(base)):
    return etat_strava(con, u["id"])


@app.post("/api/strava/connexion")
def strava_connexion(retour: str = "/espace.html#profil", u=Depends(utilisateur), con=Depends(base)):
    """Adresse d'autorisation Strava, liée à ce compte par un état à usage unique (10 minutes)."""
    exiger_strava()
    if not retour.startswith("/") or retour.startswith("//"):
        retour = "/espace.html#profil"  # pas de redirection vers un autre site
    etat = secrets.token_urlsafe(24)
    con.execute("INSERT INTO etats_oauth VALUES (%s,%s,%s,%s)", (etat, u["id"], retour, time.time() + 600))
    return {"url": strava.url_autorisation(etat)}


@app.get("/api/strava/retour")
def strava_retour(state: str = "", code: str = "", scope: str = "", error: str = "", con=Depends(base)):
    exiger_strava()
    e = con.execute("SELECT * FROM etats_oauth WHERE etat=%s AND expire>%s", (state, time.time())).fetchone()
    con.execute("DELETE FROM etats_oauth WHERE etat=%s", (state,))
    if not e:
        return HTMLResponse(page_retour("Lien expiré : relance la connexion à Strava depuis Loopy."), 400)
    if error or not code:
        return RedirectResponse(avec_statut(e["retour"], "refus"), 303)
    if "activity:write" not in scope.split(","):
        return RedirectResponse(avec_statut(e["retour"], "permission"), 303)
    try:
        j = strava.echanger(code)
    except strava.ErreurStrava:
        return RedirectResponse(avec_statut(e["retour"], "erreur"), 303)
    ath = j.get("athlete") or {}
    con.execute("INSERT INTO strava VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (utilisateur) DO UPDATE SET "
                "athlete=EXCLUDED.athlete, nom=EXCLUDED.nom, acces=EXCLUDED.acces, "
                "rafraichissement=EXCLUDED.rafraichissement, expire=EXCLUDED.expire, portee=EXCLUDED.portee",
                (e["utilisateur"], str(ath.get("id", "")), f"{ath.get('firstname', '')} {ath.get('lastname', '')}".strip(),
                 j["access_token"], j["refresh_token"], j["expires_at"], scope))
    return RedirectResponse(avec_statut(e["retour"], "ok"), 303)


def avec_statut(retour, valeur):
    """/espace.html#profil -> /espace.html?strava=ok#profil"""
    base_, _, ancre = retour.partition("#")
    return f"{base_}?strava={valeur}" + (f"#{ancre}" if ancre else "")


def page_retour(texte):
    return f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>Loopy</title>" \
           f"<body style='font-family:sans-serif;padding:2rem;background:#F4EFE6;color:#22322B'><p>{texte}</p>"


@app.delete("/api/strava", status_code=204)
def strava_deconnexion(u=Depends(utilisateur), con=Depends(base)):
    ligne = con.execute("SELECT acces FROM strava WHERE utilisateur=%s", (u["id"],)).fetchone()
    if ligne:
        strava.revoquer(ligne["acces"])
        con.execute("DELETE FROM strava WHERE utilisateur=%s", (u["id"],))


def statut_envoi(a):
    return {"statut": a["strava_statut"], "erreur": a["strava_erreur"], "activite": a["strava_activite"],
            "url": f"https://www.strava.com/activities/{a['strava_activite']}" if a["strava_activite"] else None}


@app.post("/api/activites/{i}/strava")
def envoyer_strava(i: str, req: Request, u=Depends(utilisateur), con=Depends(base)):
    """Envoie l'activité terminée (GPX horodaté) à Strava. Le traitement est asynchrone : suivre avec GET."""
    exiger_strava()
    limiter(req, "strava", 10)
    a = mon_activite(con, i, u)
    if a["strava_statut"] in ("en_cours", "pret"):
        return statut_envoi(a)
    try:
        acces = strava.jeton_valide(con, u["id"])
        rep = strava.envoyer(acces, gpx(act_dict(a)), a["nom"], boucles.SPORTS[a["sport"]]["strava"], f"loopy-{a['id']}")
    except strava.ErreurStrava as e:
        raise HTTPException(502, str(e))
    st, act, err = strava.interpreter(rep)
    con.execute("UPDATE activites SET strava_upload=%s, strava_statut=%s, strava_erreur=%s, strava_activite=%s WHERE id=%s",
                (rep.get("id_str") or str(rep.get("id", "")), st, err, act, i))
    return statut_envoi(mon_activite(con, i, u))


@app.get("/api/activites/{i}/strava")
def suivre_strava(i: str, u=Depends(utilisateur), con=Depends(base)):
    a = mon_activite(con, i, u)
    if a["strava_statut"] == "en_cours" and a["strava_upload"]:
        exiger_strava()
        try:
            st, act, err = strava.interpreter(strava.statut(strava.jeton_valide(con, u["id"]), a["strava_upload"]))
        except strava.ErreurStrava as e:
            raise HTTPException(502, str(e))
        con.execute("UPDATE activites SET strava_statut=%s, strava_erreur=%s, strava_activite=%s WHERE id=%s", (st, err, act, i))
        a = mon_activite(con, i, u)
    return statut_envoi(a)


# --- le site ---
@app.middleware("http")
async def entetes(req: Request, appel):
    rep = await appel(req)
    rep.headers.setdefault("X-Content-Type-Options", "nosniff")
    rep.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    rep.headers.setdefault("X-Frame-Options", "DENY")
    if req.url.path.startswith("/api/"):
        rep.headers.setdefault("Cache-Control", "no-store")
    return rep


if os.path.isdir(config.SITE):
    app.mount("/", StaticFiles(directory=config.SITE, html=True), name="site")
