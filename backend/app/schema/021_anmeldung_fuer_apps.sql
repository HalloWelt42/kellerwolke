-- Anmeldung an einer App (Entscheidung 17.10.2026, "Rechte je Auftrag"): Sitzungen und Geräteschlüssel, die eine App
-- für ihre Anmeldung erhält, tragen den Namen der App. Sie taugen nur zur Erkennung (Status, Abmelden) und, zusammen
-- mit dem App-Schlüssel derselben App, für die Dateiwahl; an Dateien kommt eine App nur über ihren App-Schlüssel und
-- offene Anfragen. Leer heißt: Anmeldung an der Kellerwolke selbst.

ALTER TABLE sitzung ADD COLUMN IF NOT EXISTS app text;
ALTER TABLE geraet ADD COLUMN IF NOT EXISTS app text;
