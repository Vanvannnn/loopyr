"""Position du téléphone côté app (aperçu sur l'écran de préparation) et pilotage du service GPS.
Pendant une course, c'est le service (service/suivi.py) qui enregistre : il continue écran éteint."""
import time

from kivy.clock import Clock


class Gps:
    """Permissions + écoute plyer + plan B (dernière position connue d'Android).
    sur_position(lat, lon, precision, age_s) et sur_etat(texte) sont appelés dans le fil de Kivy."""

    def __init__(self, sur_position, sur_etat):
        self.sur_position, self.sur_etat = sur_position, sur_etat
        self.demarre, self.precis, self.dernier_t, self.t_cb = False, False, 0, 0
        self.a_une_position = False

    def etat(self, texte):
        Clock.schedule_once(lambda dt: self.sur_etat(texte))

    def demander(self):
        from android.permissions import Permission, check_permission, request_permissions
        self.perms = [Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION]
        self.sur_etat("GPS : autorisation en cours…")
        demande = list(self.perms)
        from capteurs.android import version_sdk
        if version_sdk() >= 33:  # Android 13+ : la notification du service de course
            demande.append(Permission.POST_NOTIFICATIONS)
        if check_permission(self.perms[0]):  # déjà accordée : Android n'appellerait pas le callback
            self.precis = True
            Clock.schedule_once(self._demarrer, 0.5)
            if len(demande) > 2 and not check_permission(demande[2]):
                request_permissions(demande[2:])
        else:
            request_permissions(demande, self._reponse)
            Clock.schedule_interval(self._attendre, 1)

    def _reponse(self, perms, results):  # réponse à la fenêtre d'autorisation
        if not any(results[:2]):
            self.etat("GPS : localisation refusée (Réglages > Applis > Starva > Autorisations)")

    def _attendre(self, dt):
        if self.demarre:
            return False
        try:
            from android.permissions import check_permission
            fin, gros = check_permission(self.perms[0]), check_permission(self.perms[1])
        except Exception as err:
            self.sur_etat(f"GPS : erreur d'autorisation ({err})")
            return False
        if fin or gros:
            self.precis = fin
            self._demarrer(dt)
            return False

    def _demarrer(self, dt):
        if self.demarre:
            return
        self.demarre = True
        try:
            from plyer import gps
            gps.configure(on_location=self._on_loc, on_status=self._on_status)
            gps.start(minTime=1000, minDistance=0)
            self.sur_etat("GPS : recherche du signal…" if self.precis
                          else "GPS : position approximative seulement, autorise la position précise")
        except Exception as err:
            self.sur_etat(f"GPS (plyer) indisponible : {err}")
        Clock.schedule_interval(self._sonder, 1)  # plan B : on interroge Android directement

    def _sonder(self, dt):
        """Si l'écoute de plyer ne reçoit rien, on lit la dernière position connue d'Android."""
        try:
            from capteurs.android import activite, systeme
            lm = systeme(activite(), "location", "android.location.LocationManager")
            gps_on, res_on = bool(lm.isProviderEnabled("gps")), bool(lm.isProviderEnabled("network"))
            best = None
            for p in ("gps", "network", "passive"):
                loc = lm.getLastKnownLocation(p)
                if loc is not None and (best is None or loc.getTime() > best.getTime()):
                    best = loc
        except Exception as err:
            self.sur_etat(f"GPS : sondage impossible ({err})")
            return
        if not gps_on:
            self.sur_etat("La localisation du téléphone est désactivée : active-la dans les réglages")
        elif best is None and not self.a_une_position:
            self.sur_etat(f"GPS : recherche du signal… (réseau {'oui' if res_on else 'non'})")
        if best is not None and best.getTime() != self.dernier_t and time.time() - self.t_cb > 3:
            self.dernier_t = best.getTime()
            age = time.time() - best.getTime() / 1000
            self.a_une_position = True
            self.sur_position(best.getLatitude(), best.getLongitude(), best.getAccuracy(), age)

    def _on_status(self, stype, status):
        self.etat(f"GPS : {stype} {status}")

    def _on_loc(self, **kw):
        self.t_cb = time.time()
        try:
            lat, lon, prec = kw["lat"], kw["lon"], kw.get("accuracy")
        except KeyError:
            self.etat(f"GPS : réponse inattendue {list(kw)}")
            return
        self.a_une_position = True
        Clock.schedule_once(lambda dt: self.sur_position(lat, lon, prec, 0))


def demarrer_service(chemin_journal):
    """Lance le service de course en premier plan (notification « Course en cours »)."""
    from jnius import autoclass
    from capteurs.android import PAQUET, activite
    autoclass(f"{PAQUET}.ServiceSuivi").start(activite(), "", "Starva", "Course en cours", chemin_journal)


def arreter_service():
    from jnius import autoclass
    from capteurs.android import PAQUET, activite
    autoclass(f"{PAQUET}.ServiceSuivi").stop(activite())
