"""Tests fuer den SQL-bewussten Schema-Loader _anweisungen: Semikolon und '--'
in String-Literalen, Dollar-Quoting, Escape-Quotes - alles darf nicht falsch
zerlegt werden."""

from app.db import _anweisungen


def test_semikolon_im_string():
    sql = "INSERT INTO t VALUES ('a;b'); SELECT 1;"
    assert _anweisungen(sql) == ["INSERT INTO t VALUES ('a;b')", "SELECT 1"]


def test_kommentar_mit_semikolon():
    sql = "-- kommentar; mit semikolon\nSELECT 1;"
    assert _anweisungen(sql) == ["SELECT 1"]


def test_doppelstrich_im_string_ist_kein_kommentar():
    sql = "SELECT '--kein kommentar'; SELECT 2;"
    assert _anweisungen(sql) == ["SELECT '--kein kommentar'", "SELECT 2"]


def test_escapetes_anfuehrungszeichen():
    sql = "SELECT 'it''s; ok'; SELECT 4;"
    assert _anweisungen(sql) == ["SELECT 'it''s; ok'", "SELECT 4"]


def test_dollar_quoting():
    sql = (
        "CREATE FUNCTION f() RETURNS int AS $$ BEGIN; RETURN 1; END; $$ "
        "LANGUAGE plpgsql; SELECT 3;"
    )
    teile = _anweisungen(sql)
    assert len(teile) == 2
    assert teile[1] == "SELECT 3"
    assert "BEGIN; RETURN 1; END;" in teile[0]


def test_blockkommentar():
    sql = "/* weg; weg */ SELECT 5; SELECT 6;"
    assert _anweisungen(sql) == ["SELECT 5", "SELECT 6"]
