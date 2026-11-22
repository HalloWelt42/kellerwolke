-- Papierkorb nach Wurzel (HELF-262): Die Liste zählt je Zeile die mitgenommenen Verweise, das endgültige Löschen sucht,
-- was mit einem Eintrag in den Papierkorb kam. Beides fragt nach geloescht_wurzel; ohne Index lief je Zeile ein Lauf
-- über alle Knoten (4.969 Zeilen: 5,4 s statt Millisekunden), und die Oberfläche zeigte Gelöschtes noch Sekunden lang.

CREATE INDEX IF NOT EXISTS knoten_geloescht_wurzel_idx ON knoten (geloescht_wurzel) WHERE geloescht;
