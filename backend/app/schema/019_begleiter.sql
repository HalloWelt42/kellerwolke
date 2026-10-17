-- Begleitdateien: Ergebnisse, die zu einer Hauptdatei gehören und neben ihr liegen (Transkript zu einem Ton,
-- Sprachausgabe zu einem Text). Ein Begleiter gehört genau einer Hauptdatei, je Hauptdatei und Rolle gibt es höchstens
-- einen. Die Gruppe zieht gemeinsam um; Regeln und Namen in module/speicher/begleiter.py.

CREATE TABLE IF NOT EXISTS begleiter (
    begleiter_id uuid PRIMARY KEY REFERENCES knoten(id) ON DELETE CASCADE,
    haupt_id     uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    rolle        text NOT NULL CHECK (rolle ~ '^[a-z][a-z_]{0,39}$'),
    app          text,
    erstellt_am  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (haupt_id, rolle),
    CHECK (haupt_id <> begleiter_id)
);

CREATE INDEX IF NOT EXISTS begleiter_haupt_idx ON begleiter (haupt_id);
