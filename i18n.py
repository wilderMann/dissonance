"""Server-side messages in English and German. Messages are written in German in the code ({placeholders} allowed);
EN maps them to English. The language of a request: X-Lang header (sent by the app), cookie "lang", Accept-Language;
English when nothing says German."""

LANGS = ("en", "de")

EN = {
    # requests / songs / songbooks
    "Ungültiger Dateiname.": "Invalid file name.",
    "Bitte zuerst anmelden.": "Please sign in first.",
    "Lied nicht gefunden.": "Song not found.",
    "Liederbuch nicht gefunden.": "Songbook not found.",
    "Das darf nur, wer es angelegt hat (oder ein Admin).": "Only the person who created it (or an admin) may do that.",
    "Das darf nur, wer es angelegt hat, wer mitarbeitet (oder ein Admin).":
        "Only the person who created it, collaborators (or an admin) may do that.",
    "Lied zu groß.": "Song too large.",
    "Bitte einen Titel angeben: {{title: …}}": "Please add a title: {{title: …}}",
    "Das Lied wurde inzwischen gelöscht.": "The song has been deleted in the meantime.",
    "Das Lied wurde inzwischen woanders geändert.": "The song has been changed elsewhere in the meantime.",
    "„{name}“ gibt es schon.": "“{name}” already exists.",
    "Ungültiges Tempo.": "Invalid tempo.",
    "Version nicht gefunden.": "Version not found.",
    "Bitte einen Namen angeben.": "Please enter a name.",
    "Das Liederbuch wurde inzwischen woanders geändert.": "The songbook has been changed elsewhere in the meantime.",
    "Nur für Admins.": "Admins only.",
    "Du kannst dich nicht selbst löschen.": "You can't delete yourself.",
    "Bitte angeben, was mit den Liedern passieren soll.": "Please say what should happen to the songs.",
    "Benutzer nicht gefunden.": "User not found.",
    "Anfrage zu groß.": "Request too large.",
    "Ungültige Anfrage.": "Invalid request.",
    "Nicht gefunden.": "Not found.",
    "Fremde Herkunft.": "Request from a foreign site refused.",
    "Speicherfehler: {err}": "Storage error: {err}",
    # converter
    "Keine Eingabe.": "Nothing to convert.",
    "Unbekannte Quelle.": "Unknown source.",
    "Laden fehlgeschlagen: {err}": "Loading failed: {err}",
    "Keine Ultimate-Guitar-Songdaten in der Seite gefunden (js-store fehlt).":
        "No Ultimate Guitar song data found in the page (js-store missing).",
    "Dieser Tab ({kind}) enthält keinen Text – Pro-/Official-Tabs werden nicht unterstützt.":
        "This tab ({kind}) contains no text – Pro/Official tabs are not supported.",
    "Das ist eine Album-Seite von Ukulele-Tabs.com, kein Lied.": "This is an album page on Ukulele-Tabs.com, not a song.",
    "Das ist eine Album-Seite von Ukulele-Tabs.com, kein Lied. Das Lied ist hier: {url}":
        "This is an album page on Ukulele-Tabs.com, not a song. The song is here: {url}",
    "Keine Songdaten gefunden – unterstützt werden Seiten von Ultimate Guitar (js-store) und Ukulele-Tabs.com.":
        "No song data found – supported are pages from Ultimate Guitar (js-store) and Ukulele-Tabs.com.",
    "Nur https-Links von ultimate-guitar.com und ukulele-tabs.com werden geladen.":
        "Only https links from ultimate-guitar.com and ukulele-tabs.com are loaded.",
    "Seite zu groß.": "Page too large.",
    # login
    "Ungültiges ID-Token.": "Invalid ID token.",
    "Der Anmeldedienst ist nicht erreichbar ({err}).": "The sign-in service is not reachable ({err}).",
    "Der Anmeldedienst meldet einen anderen Issuer als konfiguriert (OIDC_ISSUER).":
        "The sign-in service reports a different issuer than configured (OIDC_ISSUER).",
    "Der Anmeldedienst hat die Anmeldung abgelehnt (HTTP {code}).": "The sign-in service rejected the sign-in (HTTP {code}).",
    "Anmeldung abgebrochen: {why}": "Sign-in cancelled: {why}",
    "Die Anmeldung ist abgelaufen – bitte nochmal versuchen.": "The sign-in has expired – please try again.",
    "ID-Token ist nicht für diese App ausgestellt.": "The ID token was not issued for this app.",
    "ID-Token ist abgelaufen oder ungültig.": "The ID token is expired or invalid.",
    "Dein Konto ist für diese App nicht freigeschaltet (Gruppe fehlt).": "Your account is not allowed to use this app (group missing).",
    "Dein Konto ist für diese App nicht freigeschaltet (E-Mail-Domain).": "Your account is not allowed to use this app (e-mail domain).",
    "Dein Konto ist für diese App nicht freigeschaltet.": "Your account is not allowed to use this app.",
    "Anmeldung fehlgeschlagen": "Sign-in failed",
    "Zurück zu Dissonance": "Back to Dissonance",
    "Mit einem anderen Konto anmelden": "Sign in with another account",
    "Dieser Link gilt nicht (mehr) – die Freigabe wurde vielleicht beendet.":
        "This link is not valid (any more) – sharing may have been switched off.",
    "Dieser Link ist abgelaufen.": "This link has expired.",
    "Ungültige Gültigkeitsdauer.": "Invalid duration.",
    "Ungültige Tonart.": "Invalid key.",
}


def tr(lang, text, **args):
    s = EN.get(text, text) if lang == "en" else text
    try:
        return s.format(**args)
    except (KeyError, IndexError, ValueError):
        return s


class Message(Exception):
    """An error whose text is translated when it is shown: Message("„{name}“ gibt es schon.", name=…)."""

    def __init__(self, text, **args):
        super().__init__(tr("de", text, **args))
        self.text, self.args_ = text, args

    def localized(self, lang):
        return tr(lang, self.text, **self.args_)


def pick(header=None, cookie=None, accept=None):
    """Language for a request: explicit choice of the app, then the browser's Accept-Language; default English."""
    for v in (header, cookie):
        if v in LANGS:
            return v
    for part in (accept or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LANGS:
            return code
    return "en"
