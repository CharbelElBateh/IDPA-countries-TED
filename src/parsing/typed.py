"""Typed-value parsers: number, percent, year, date, currency, coordinates.

Each parser is permissive — returns ``None`` if it cannot make sense of the
input. Use ``detect_type`` to pick a parser when no explicit type is given.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from src.parsing.wikitext import clean as clean_wikitext

# ----------------------------------------------------------- number parsing
_MAGNITUDES = {
    "thousand": 1e3, "k": 1e3,
    "million": 1e6, "m": 1e6, "mn": 1e6,
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "trillion": 1e12, "tn": 1e12, "t": 1e12,
    "lakh": 1e5, "crore": 1e7,
}

_RE_LEADING_NUMBER = re.compile(
    r"^\s*(-?\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*"
)

_RE_TRAIL_MAGNITUDE = re.compile(
    r"^\s*(thousand|million|billion|trillion|lakh|crore|bn|mn|tn|k|m|b|t)\b",
    re.IGNORECASE,
)

_RE_PERCENT = re.compile(r"^\s*(-?[\d,]*\.?\d+)\s*%\s*$")
_RE_YEAR    = re.compile(r"^\s*(-?\d{1,4})(?:\s*(BC|BCE|AD|CE))?\s*$",
                         re.IGNORECASE)

_RE_DATE_ISO = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$")
_RE_DATE_DMY = re.compile(
    r"^\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s*(BC|BCE|AD|CE))?\s*$"
)
_RE_DATE_MDY = re.compile(
    r"^\s*([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})(?:\s*(BC|BCE|AD|CE))?\s*$"
)
_RE_DATE_YEAR_ONLY = re.compile(r"^\s*(\d{3,4})(?:\s*(BC|BCE|AD|CE))?\s*$",
                                re.IGNORECASE)

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June",
     "July","August","September","October","November","December"], start=1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})

# ----------------------------------------------------------- currency
_CURRENCY_SYMBOLS = {
    "$": "USD", "US$": "USD", "USD": "USD",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
    "¥": "JPY", "JPY": "JPY", "CNY": "CNY",
    "₹": "INR", "Rs": "INR", "INR": "INR",
    "C$": "CAD", "A$": "AUD", "NZ$": "NZD", "HK$": "HKD", "S$": "SGD",
    "CHF": "CHF", "BRL": "BRL", "R$": "BRL",
}

_RE_CURRENCY_PREFIX = re.compile(
    r"^\s*(US\$|C\$|A\$|NZ\$|HK\$|S\$|R\$|USD|EUR|GBP|JPY|CNY|INR|CHF|BRL|"
    r"[\$€£¥₹])\s*"
)


# ============================================================ parsers
def parse_number(s: str) -> float | None:
    """Parse ``"28,748"``, ``"3.14"``, ``"78.233 billion"`` → float. Returns ``None`` if not a number."""
    if not s:
        return None
    s = s.strip()
    m = _RE_LEADING_NUMBER.match(s)
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", "").replace(" ", ""))
    except ValueError:
        return None
    rest = s[m.end():].strip()
    mag = _RE_TRAIL_MAGNITUDE.match(rest)
    if mag:
        n *= _MAGNITUDES[mag.group(1).lower()]
    return n


def parse_percent(s: str) -> float | None:
    """Parse ``"19.4%"`` → ``19.4``. Returns ``None`` if no trailing ``%``."""
    if not s:
        return None
    m = _RE_PERCENT.match(s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_year(s: str) -> int | None:
    """Parse ``"1516"`` / ``"202 BC"`` → int (BCE = negative)."""
    if not s:
        return None
    m = _RE_YEAR.match(s)
    if not m:
        return None
    try:
        y = int(m.group(1))
    except ValueError:
        return None
    era = (m.group(2) or "").upper()
    if era in {"BC", "BCE"}:
        y = -y
    if -10000 <= y <= 2100:
        return y
    return None


def parse_date(s: str) -> date | None:
    """Parse ``"2024-03-15"``, ``"15 March 2024"``, ``"March 15, 2024"``,
    or just a bare year ``"1516"`` (returned as ``date(year, 1, 1)``).

    BCE years cannot be represented by ``datetime.date`` — those return
    ``None`` from this parser (use ``parse_year`` instead)."""
    if not s:
        return None
    s = s.strip()

    m = _RE_DATE_ISO.match(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = _RE_DATE_DMY.match(s)
    if m:
        d, mon, y, era = m.group(1), m.group(2).lower(), m.group(3), (m.group(4) or "").upper()
        if era in {"BC", "BCE"}:
            return None
        if mon not in _MONTHS:
            return None
        try:
            return date(int(y), _MONTHS[mon], int(d))
        except ValueError:
            return None

    m = _RE_DATE_MDY.match(s)
    if m:
        mon, d, y, era = m.group(1).lower(), m.group(2), m.group(3), (m.group(4) or "").upper()
        if era in {"BC", "BCE"}:
            return None
        if mon not in _MONTHS:
            return None
        try:
            return date(int(y), _MONTHS[mon], int(d))
        except ValueError:
            return None

    m = _RE_DATE_YEAR_ONLY.match(s)
    if m:
        try:
            y = int(m.group(1))
            era = (m.group(2) or "").upper()
            if era in {"BC", "BCE"}:
                return None
            if 1 <= y <= 2100:
                return date(y, 1, 1)
        except ValueError:
            return None
    return None


def parse_currency(s: str, *, rates: dict[str, float] | None = None
                   ) -> tuple[float, str] | None:
    """Parse ``"$78.233 billion"`` → ``(78.233e9, "USD")``.

    If ``rates`` is provided, the returned amount is converted to USD;
    otherwise the local amount + ISO code are returned.
    Returns ``None`` if no currency symbol/code is found."""
    if not s:
        return None
    s = s.strip()
    m = _RE_CURRENCY_PREFIX.match(s)
    code: str | None = None
    if m:
        code = _CURRENCY_SYMBOLS.get(m.group(1).upper()) or _CURRENCY_SYMBOLS.get(m.group(1))
        s = s[m.end():]
    if not code:
        # Maybe trailing code: "100 USD"
        toks = s.split()
        if toks and toks[-1].upper() in _CURRENCY_SYMBOLS.values():
            code = toks[-1].upper()
            s = " ".join(toks[:-1])
    if not code:
        return None
    amount = parse_number(s)
    if amount is None:
        return None
    if rates and code in rates:
        amount *= rates[code]
        code = "USD"
    return amount, code


def parse_coordinates(s: str) -> tuple[float, float] | None:
    """Parse a ``{{coord|...}}`` template OR a ``"lat,lon"`` pair → ``(lat, lon)``."""
    if not s:
        return None
    s = s.strip()
    if s.lower().startswith("{{coord"):
        body = s[2:-2] if s.endswith("}}") else s[2:]
        parts = [p.strip() for p in body.split("|")][1:]
        # Drop named args.
        nums: list[float] = []
        ns_ew: list[str] = []
        for p in parts:
            if "=" in p:
                continue
            try:
                nums.append(float(p))
            except ValueError:
                if p.upper() in {"N", "S", "E", "W"}:
                    ns_ew.append(p.upper())
        if len(nums) == 2:
            return nums[0], nums[1]
        if len(nums) >= 6 and len(ns_ew) >= 2:
            lat = nums[0] + nums[1] / 60 + nums[2] / 3600
            lon = nums[3] + nums[4] / 60 + nums[5] / 3600
            if ns_ew[0] == "S": lat = -lat
            if ns_ew[1] == "W": lon = -lon
            return lat, lon
        if len(nums) >= 4 and len(ns_ew) >= 2:
            lat = nums[0] + nums[1] / 60
            lon = nums[2] + nums[3] / 60
            if ns_ew[0] == "S": lat = -lat
            if ns_ew[1] == "W": lon = -lon
            return lat, lon
        return None
    # "lat,lon"
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                return None
    return None


# ============================================================ type detection
def detect_type(raw: str) -> str:
    """Heuristic type label for a wikitext string."""
    if raw is None:
        return "empty"
    s = str(raw).strip()
    if not s:
        return "empty"
    if "{{coord" in s.lower():
        return "coordinates"
    if _RE_PERCENT.match(s):
        return "percent"
    if _RE_YEAR.match(s) and parse_year(s) is not None:
        return "year"
    if _RE_CURRENCY_PREFIX.match(s):
        return "currency"
    if parse_date(s) is not None and "-" in s or _RE_DATE_DMY.match(s) or _RE_DATE_MDY.match(s):
        return "date"
    if parse_number(s) is not None:
        return "number"
    return "text"


# ============================================================ unified parse
def parse_value(raw: Any, type_hint: str | None = None,
                rates: dict[str, float] | None = None
                ) -> tuple[Any, str, int | None, str | None]:
    """Parse one raw infobox value into ``(value, type, trend, unit)``.

    ``type_hint`` may be one of: ``"number"``, ``"percent"``, ``"year"``,
    ``"date"``, ``"currency"``, ``"coordinates"``, ``"wikilink"``,
    ``"text"``. If absent, the type is detected heuristically.
    """
    text, trend = clean_wikitext(raw)
    if not text:
        return None, "empty", trend, None

    t = type_hint or detect_type(text)

    if t == "number":
        v = parse_number(text)
        return (v, "number", trend, None) if v is not None else (text, "text", trend, None)
    if t == "percent":
        v = parse_percent(text)
        if v is None:
            # Allow a bare number when the field is hinted as percent
            # (e.g. ``percent_water = "1.6"``).
            v = parse_number(text)
        return (v, "percent", trend, None) if v is not None else (text, "text", trend, None)
    if t == "year":
        v = parse_year(text)
        return (v, "year", trend, None) if v is not None else (text, "text", trend, None)
    if t == "date":
        v = parse_date(text)
        return (v, "date", trend, None) if v is not None else (text, "text", trend, None)
    if t == "currency":
        v = parse_currency(text, rates=rates)
        if v is not None:
            amount, code = v
            return amount, "currency", trend, code
        # fall through to number
        n = parse_number(text)
        return (n, "number", trend, None) if n is not None else (text, "text", trend, None)
    if t == "coordinates":
        v = parse_coordinates(text)
        return (v, "coordinates", trend, None) if v is not None else (text, "text", trend, None)
    if t == "wikilink":
        return text, "wikilink", trend, None
    return text, "text", trend, None
