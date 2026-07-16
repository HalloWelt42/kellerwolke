"""Read-only Durchreiche auf einen bestehenden Verzeichnisbaum (Quelle-Port).

Nichts wird kopiert oder gehasht; gelesen wird direkt von der Platte. Pfade
werden gegen die Wurzel abgesichert, damit weder '..' noch Symlinks aus der
Quelle ausbrechen koennen. Im Betrieb ein gemounteter Datentraeger, lokal ein
Testordner.
"""

from pathlib import Path

from app.ports import DateiZuGross, Eintrag


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
                groesse = 0 if ist_ordner else kind.stat().st_size
            except OSError:
                continue
            eintraege.append(Eintrag(name=kind.name, ist_ordner=ist_ordner, groesse=groesse))
        return eintraege

    def lesen(self, relativ: str) -> bytes:
        ziel = self._aufloesen(relativ)
        if ziel.is_dir():
            raise IsADirectoryError(relativ)
        return ziel.read_bytes()

    def info(self, relativ: str) -> Eintrag:
        ziel = self._aufloesen(relativ)
        ist_ordner = ziel.is_dir()
        return Eintrag(
            name=ziel.name,
            ist_ordner=ist_ordner,
            groesse=0 if ist_ordner else ziel.stat().st_size,
        )

    def schreiben(self, relativ: str, daten: bytes) -> None:
        """Legt eine Datei an oder ueberschreibt sie. Pfad bleibt durch
        _aufloesen in der Quelle eingegrenzt (kein '..', kein Symlink-Ausbruch)."""
        ziel = self._aufloesen(relativ)
        if ziel == self.wurzel or ziel.is_dir():
            raise IsADirectoryError(relativ)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(daten)

    def schreiben_strom(self, relativ: str, quelle, max_bytes: int = 0,
                        stueck: int = 1024 * 1024) -> int:
        """Wie schreiben, aber stueckweise aus einem Datei-Objekt - der Inhalt
        landet nie vollstaendig im Speicher. Liefert die geschriebene Groesse.
        Ueberschreitet der Strom max_bytes, wird abgebrochen und die angefangene
        Datei wieder entfernt (keine halbe Datei in der fremden Quelle)."""
        ziel = self._aufloesen(relativ)
        if ziel == self.wurzel or ziel.is_dir():
            raise IsADirectoryError(relativ)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        groesse = 0
        try:
            with open(ziel, "wb") as f:
                while True:
                    brocken = quelle.read(stueck)
                    if not brocken:
                        break
                    groesse += len(brocken)
                    if max_bytes and groesse > max_bytes:
                        raise DateiZuGross(f"Datei groesser als {max_bytes} Bytes")
                    f.write(brocken)
            return groesse
        except BaseException:
            try:
                ziel.unlink()
            except OSError:
                pass
            raise

    def ordner_anlegen(self, relativ: str) -> None:
        ziel = self._aufloesen(relativ)
        if ziel == self.wurzel:
            raise PermissionError("Wurzel kann nicht angelegt werden")
        ziel.mkdir(parents=True, exist_ok=True)
