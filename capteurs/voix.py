"""Voix et vibreur. Sans contexte Android (PC, tests), la voix s'affiche dans la console.
Sans dépendance à Kivy : utilisé aussi par le service GPS."""


class Voix:
    def __init__(self, contexte=None):
        self.contexte, self.tts = contexte, None

    def preparer(self):
        """Android met ~1 s à initialiser la synthèse vocale : à appeler un peu avant de parler."""
        if self.contexte is None or self.tts is not None:
            return
        try:
            from jnius import autoclass
            self.tts = autoclass("android.speech.tts.TextToSpeech")(self.contexte, None)
        except Exception as err:
            print(f"Voix indisponible : {err}")

    def dire(self, texte):
        if self.contexte is None:
            print(f"[voix] {texte}")
            return
        self.preparer()
        try:
            from capteurs.android import chaine
            self.tts.speak(chaine(texte), 1, None, chaine("starva"))  # 1 = QUEUE_ADD
        except Exception as err:
            print(f"Voix : {err}")

    def vibrer(self, ms=600):
        if self.contexte is None:
            return
        try:
            from capteurs.android import systeme
            systeme(self.contexte, "vibrator", "android.os.Vibrator").vibrate(ms)
        except Exception as err:
            print(f"Vibreur : {err}")

    def fermer(self):
        if self.tts is not None:
            self.tts.shutdown()
            self.tts = None
