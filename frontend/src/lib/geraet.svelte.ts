// Telefon oder Rechner: am Telefon zeigt Kellerwolke eine eigene, reduzierte
// Oberfläche (lib/mobil), nicht die zusammengeschobene des Rechners. Entscheidend
// ist die Breite; ein Telefon quer zählt über die geringe Höhe mit.
const abfrage =
  typeof matchMedia === "function" ? matchMedia("(max-width: 760px), (pointer: coarse) and (max-height: 500px)") : null;

export const geraet = $state<{ mobil: boolean }>({ mobil: abfrage?.matches ?? false });

abfrage?.addEventListener("change", (e) => {
  geraet.mobil = e.matches;
});
