"""Read-only Durchreiche auf einen bestehenden Verzeichnisbaum (Quelle-Port).

Nichts wird kopiert oder gehasht; gelesen wird direkt von der Platte. Pfade
werden gegen die Wurzel abgesichert, damit weder '..' noch Symlinks aus der
Quelle ausbrechen koennen. Im Betrieb ein gemounteter Datentraeger, lokal ein
Testordner.
"""

from pathlib import Path

from app.ports import Eintrag


class DateibaumQuelle:
    def __init__(self, wurzel) -> None:
        self.wurzel = Path(wurzel).resolve()

    def _aufloesen(self, relativ: str) -> Path:
        ziel = (self.wurzel / relativ.lstrip("/")).resolve()
        if ziel != self.wurzel and self.wurzel not in ziel.parents:
            raise PermissionError("Pfad ausserhalb der Quelle")
        return ziel

    def auflisten(self, relativ: str = "") -> list[Eintrag]:
        ordner = self._aufloesen(relativ)
        eintraege = []
        for kind in sorted(ordner.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                ist_ordner = kind.is_dir()
                st = kind.stat()
            except OSError:
                continue
            eintraege.append(Eintrag(name=kind.name, ist_ordner=ist_ordner, groesse=0 if ist_ordner else st.st_size,
                                     geaendert=st.st_mtime))
        return eintraege

    def info(self, relativ: str) -> Eintrag:
        ziel = self._aufloesen(relativ)
        ist_ordner = ziel.is_dir()
        st = ziel.stat()
        return Eintrag(name=ziel.name, ist_ordner=ist_ordner, groesse=0 if ist_ordner else st.st_size,
                       geaendert=st.st_mtime)

    def bereich_lesen(self, relativ: str, start: int, laenge: int) -> bytes:
        """Nur den Ausschnitt lesen; Auslieferungen holen sich so Stück für Stück, nie die ganze Datei."""
        ziel = self._aufloesen(relativ)
        if ziel.is_dir():
            raise IsADirectoryError(relativ)
        with open(ziel, "rb") as f:
            f.seek(start)
            return f.read(laenge)
