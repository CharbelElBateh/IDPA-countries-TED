"""Tests for wikitext cleaning + typed-value parsing."""

from __future__ import annotations

from datetime import date

import pytest

from src.parsing.typed import (
    detect_type, parse_coordinates, parse_currency, parse_date,
    parse_number, parse_percent, parse_value, parse_year,
)
from src.parsing.wikitext import (
    clean, expand_lists, extract_trend, handle_templates,
    resolve_wikilinks, strip_comments, strip_refs,
)


class TestWikitext:
    def test_strip_refs(self):
        assert strip_refs("hello<ref>cite</ref> world") == "hello world"
        assert strip_refs('hello<ref name="x"/>!') == "hello!"

    def test_strip_comments(self):
        assert strip_comments("foo<!-- comment -->bar") == "foobar"

    def test_resolve_wikilinks(self):
        assert resolve_wikilinks("[[Beirut]]") == "Beirut"
        assert resolve_wikilinks("[[Lebanese people|Lebanese]]") == "Lebanese"
        assert resolve_wikilinks("[[a]] and [[b|B]]") == "a and B"

    def test_extract_trend(self):
        text, trend = extract_trend("{{increase}} $78 billion")
        assert trend == +1 and "78 billion" in text
        text, trend = extract_trend("{{decrease}} 0.7")
        assert trend == -1
        text, trend = extract_trend("plain")
        assert trend is None

    def test_handle_templates_drops_cites(self):
        assert handle_templates("a {{cite news|x=1}} b") == "a  b"
        assert handle_templates("{{efn|foo}}bar") == "bar"

    def test_handle_templates_unwraps_lang(self):
        assert "Lebanon" in handle_templates("{{lang|en|Lebanon}}")

    def test_handle_templates_expands_ubl(self):
        result = handle_templates("{{ubl|Sunni|Shia|Druze}}")
        assert "Sunni" in result and "Shia" in result and "Druze" in result

    def test_expand_lists(self):
        items = expand_lists("* Sunni\n* Shia\n* Druze")
        assert items == ["Sunni", "Shia", "Druze"]
        # Single item returns None.
        assert expand_lists("just one") is None

    def test_clean_full(self):
        raw = "[[Beirut]]<ref name='a'>cite</ref> {{cite news|x=1}}"
        text, trend = clean(raw)
        assert text == "Beirut"
        assert trend is None


class TestNumber:
    @pytest.mark.parametrize("s,expected", [
        ("10452",         10452.0),
        ("28,748",        28748.0),
        ("3.14",          3.14),
        ("78.233 billion", 78.233e9),
        ("11,793",        11793.0),
        ("2.5 million",   2.5e6),
        ("",              None),
        ("not a number",  None),
    ])
    def test_parse_number(self, s, expected):
        assert parse_number(s) == expected


class TestPercent:
    def test_simple(self):
        assert parse_percent("19.4%") == 19.4
        assert parse_percent("2%") == 2.0
        assert parse_percent("not percent") is None


class TestYear:
    def test_ce(self):
        assert parse_year("1516") == 1516
        assert parse_year("2024") == 2024

    def test_bce(self):
        assert parse_year("202 BC") == -202
        assert parse_year("753 BCE") == -753

    def test_out_of_range(self):
        assert parse_year("99999") is None


class TestDate:
    def test_iso(self):
        assert parse_date("2024-03-15") == date(2024, 3, 15)

    def test_dmy(self):
        assert parse_date("15 March 2024") == date(2024, 3, 15)

    def test_mdy(self):
        assert parse_date("March 15, 2024") == date(2024, 3, 15)

    def test_year_only(self):
        assert parse_date("1516") == date(1516, 1, 1)


class TestCurrency:
    def test_usd_billion(self):
        result = parse_currency("$78.233 billion")
        assert result is not None
        amount, code = result
        assert amount == pytest.approx(78.233e9)
        assert code == "USD"

    def test_usd_capita(self):
        amount, code = parse_currency("$11,793")
        assert amount == 11793.0
        assert code == "USD"

    def test_eur_with_rates(self):
        result = parse_currency("€100", rates={"EUR": 1.08})
        amount, code = result
        assert amount == pytest.approx(108.0)
        assert code == "USD"

    def test_no_currency_returns_none(self):
        assert parse_currency("100") is None


class TestCoordinates:
    def test_decimal(self):
        result = parse_coordinates("{{coord|33.886|35.513}}")
        assert result == (33.886, 35.513)

    def test_dms(self):
        result = parse_coordinates("{{coord|33|54|N|35|31|E}}")
        assert result is not None
        lat, lon = result
        assert 33 < lat < 34
        assert 35 < lon < 36

    def test_comma_pair(self):
        assert parse_coordinates("33.886, 35.513") == (33.886, 35.513)


class TestDetectType:
    @pytest.mark.parametrize("s,expected", [
        ("19.4%",          "percent"),
        ("2024",           "year"),
        ("$78 billion",    "currency"),
        ("{{coord|1|2}}",  "coordinates"),
        ("10452",          "number"),
        ("",               "empty"),
        ("Beirut",         "text"),
    ])
    def test(self, s, expected):
        assert detect_type(s) == expected


class TestParseValue:
    def test_currency_with_trend(self):
        v, t, trend, unit = parse_value("{{increase}} $78.233 billion",
                                        type_hint="currency",
                                        rates={"USD": 1.0})
        assert t == "currency"
        assert v == pytest.approx(78.233e9)
        assert unit == "USD"
        assert trend == +1

    def test_wikilink_resolves(self):
        v, t, _, _ = parse_value("[[Lebanese people|Lebanese]]",
                                 type_hint="wikilink")
        assert t == "wikilink"
        assert v == "Lebanese"

    def test_empty(self):
        v, t, _, _ = parse_value("", type_hint="text")
        assert t == "empty"
