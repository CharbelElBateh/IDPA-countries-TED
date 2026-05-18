"""Wikitext cleaning utilities.

A pipeline of small, focused functions that turn raw Wikipedia infobox
wikitext into clean plain text. Run order matters; the top-level
``clean()`` orchestrates them.
"""

from __future__ import annotations

import re
from typing import Any

# ----------------------------------------------------------- regex patterns
_RE_REF_BLOCK     = re.compile(r"<ref\b[^>]*?>.*?</ref>", re.IGNORECASE | re.DOTALL)
_RE_REF_SELF      = re.compile(r"<ref\b[^/>]*/>",        re.IGNORECASE)
_RE_COMMENT       = re.compile(r"<!--.*?-->",             re.DOTALL)
_RE_HTML_BR       = re.compile(r"<\s*br\s*/?\s*>",        re.IGNORECASE)
_RE_HTML_TAG      = re.compile(r"</?[a-zA-Z][^>]*>")
_RE_WIKILINK_FULL = re.compile(r"\[\[([^\[\]|]+)\|([^\[\]]*)\]\]")
_RE_WIKILINK_BARE = re.compile(r"\[\[([^\[\]]+)\]\]")
_RE_EXT_LINK      = re.compile(r"\[(https?://[^\]\s]+)(?:\s+([^\]]*))?\]")

_RE_TREND_INC   = re.compile(r"\{\{\s*increase(?:[^}]*)?\}\}",     re.IGNORECASE)
_RE_TREND_DEC   = re.compile(r"\{\{\s*decrease(?:[^}]*)?\}\}",     re.IGNORECASE)
_RE_TREND_STD   = re.compile(r"\{\{\s*(?:steady|nochange|constant|increase\s*neutral|decrease\s*neutral)(?:[^}]*)?\}\}", re.IGNORECASE)

# Templates whose entire content (including args) should be dropped.
_DROP_TEMPLATE_NAMES = {
    "cite", "citation", "efn", "sfn", "sfnp", "rp", "as of", "asof",
    "harvnb", "harvtxt", "harv", "mvar", "math",
}

# Templates that should be unwrapped to their last non-empty argument
# (common pattern: cosmetic wrappers).
_UNWRAP_LAST = {
    "nowrap", "small", "smaller", "big", "huge", "noitalic",
    "nobold", "vunblist", "italic", "em", "lang", "lang-en", "lang-ar",
    "transl", "transliteration",
}

# Templates that should be unwrapped to their first non-empty argument.
_UNWRAP_FIRST = {
    "native name", "nativename", "lang", "transl",
}


# ----------------------------------------------------------- public API
def strip_refs(s: str) -> str:
    """Remove ``<ref…>…</ref>`` and self-closing ``<ref … />`` tags."""
    s = _RE_REF_BLOCK.sub("", s)
    s = _RE_REF_SELF.sub("", s)
    return s


def strip_comments(s: str) -> str:
    """Remove HTML comments ``<!-- … -->``."""
    return _RE_COMMENT.sub("", s)


def strip_html_tags(s: str) -> str:
    """Replace ``<br>`` with newline and drop all other HTML tags."""
    s = _RE_HTML_BR.sub("\n", s)
    return _RE_HTML_TAG.sub("", s)


def resolve_wikilinks(s: str) -> str:
    """``[[X|Y]] → Y``; ``[[X]] → X``."""
    s = _RE_WIKILINK_FULL.sub(lambda m: m.group(2) or m.group(1), s)
    s = _RE_WIKILINK_BARE.sub(lambda m: m.group(1), s)
    return s


def resolve_external_links(s: str) -> str:
    """``[http://… display] → display``; bare URL kept if no display text."""
    return _RE_EXT_LINK.sub(lambda m: m.group(2) or m.group(1), s)


def extract_trend(s: str) -> tuple[str, int | None]:
    """Lift any ``{{increase|decrease|steady}}`` template out of the string.

    Returns ``(cleaned_text, trend ∈ {+1, 0, -1, None})``.
    """
    trend: int | None = None
    if _RE_TREND_INC.search(s):
        trend = +1
        s = _RE_TREND_INC.sub("", s)
    elif _RE_TREND_DEC.search(s):
        trend = -1
        s = _RE_TREND_DEC.sub("", s)
    elif _RE_TREND_STD.search(s):
        trend = 0
        s = _RE_TREND_STD.sub("", s)
    return s, trend


# ----------------------------------------------------------- template parsing
def find_templates(s: str) -> list[tuple[int, int, str, list[str]]]:
    """Find all top-level (non-nested-into) ``{{…}}`` templates.

    Returns a list of ``(start, end, name, args)`` where ``args`` is the
    list of pipe-separated arguments (after the template name).
    Nested templates are kept *inside* the parent's argument string.
    """
    out: list[tuple[int, int, str, list[str]]] = []
    i = 0
    while i < len(s) - 1:
        if s[i] == "{" and s[i + 1] == "{":
            depth = 1
            j = i + 2
            while j < len(s) - 1 and depth > 0:
                if s[j] == "{" and s[j + 1] == "{":
                    depth += 1
                    j += 2
                elif s[j] == "}" and s[j + 1] == "}":
                    depth -= 1
                    j += 2
                else:
                    j += 1
            if depth == 0:
                inner = s[i + 2:j - 2]
                parts = _split_top_level_pipe(inner)
                name = parts[0].strip().lower() if parts else ""
                args = [p.strip() for p in parts[1:]] if len(parts) > 1 else []
                out.append((i, j, name, args))
                i = j
            else:
                break
        else:
            i += 1
    return out


def _split_top_level_pipe(s: str) -> list[str]:
    """Split on ``|`` ignoring those inside nested ``{{…}}`` / ``[[…]]``."""
    parts: list[str] = []
    cur: list[str] = []
    depth_t = 0
    depth_l = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "{" and i + 1 < len(s) and s[i + 1] == "{":
            depth_t += 1
            cur.append("{{"); i += 2; continue
        if ch == "}" and i + 1 < len(s) and s[i + 1] == "}":
            depth_t -= 1
            cur.append("}}"); i += 2; continue
        if ch == "[" and i + 1 < len(s) and s[i + 1] == "[":
            depth_l += 1
            cur.append("[["); i += 2; continue
        if ch == "]" and i + 1 < len(s) and s[i + 1] == "]":
            depth_l -= 1
            cur.append("]]"); i += 2; continue
        if ch == "|" and depth_t == 0 and depth_l == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def handle_templates(s: str) -> str:
    """Process templates: drop citation-like, unwrap cosmetic, leave others."""
    # We rebuild the string left-to-right, replacing each template.
    out: list[str] = []
    last = 0
    for start, end, name, args in find_templates(s):
        out.append(s[last:start])
        out.append(_handle_one_template(name, args))
        last = end
    out.append(s[last:])
    return "".join(out)


def _handle_one_template(name: str, args: list[str]) -> str:
    """Return the replacement string for a single template."""
    # Heuristic: starts-with match for citations (e.g. "cite news").
    base = name.split()[0] if name else ""
    if base in _DROP_TEMPLATE_NAMES or name.startswith("cite "):
        return ""
    if name in {"nbsp", "ndash", "mdash"}:
        return {"nbsp": " ", "ndash": "–", "mdash": "—"}[name]
    if name == "spaces" or name == "spaced ndash":
        return " "
    if name == "nbhyph":
        return "-"
    if name in {"hlist", "ubl", "unbulleted list", "plainlist", "flatlist", "ublist"}:
        # Join items with newlines so downstream list expansion sees them.
        items = [a for a in args if a and "=" not in a]
        return "\n".join(items)
    if name in {"convert", "cvt"}:
        # {{convert|X|unit|...}} -> "X unit"
        nums = [a for a in args[:2] if a and "=" not in a]
        return " ".join(nums)
    if name == "formatnum":
        return args[0] if args else ""
    if name in _UNWRAP_LAST:
        non_empty = [a for a in args if a and "=" not in a]
        return non_empty[-1] if non_empty else ""
    if name in _UNWRAP_FIRST:
        non_empty = [a for a in args if a and "=" not in a]
        return non_empty[0] if non_empty else ""
    if name == "coord":
        # Preserve as a sentinel string parse-able later by typed.parse_coordinates.
        return "{{coord|" + "|".join(args) + "}}"
    # Default: drop the template entirely.
    return ""


# ----------------------------------------------------------- list expansion
def expand_lists(raw: str) -> list[str] | None:
    """If ``raw`` looks like a list (ubl/plainlist/bullets/newlines), return items.

    Otherwise return ``None`` to indicate "treat as a single scalar".
    """
    s = raw.strip()
    if not s:
        return None
    # Strip wrapping list templates entirely first via handle_templates.
    s = handle_templates(s)
    # Bulleted lines.
    if "\n" in s or s.startswith("*"):
        items = []
        for line in s.splitlines():
            line = line.strip().lstrip("*").lstrip("#").strip()
            if line:
                items.append(line)
        if len(items) >= 2:
            return items
    # Comma- or semicolon-separated short list (3+ items).
    if ";" in s and s.count(";") >= 2:
        items = [p.strip() for p in s.split(";") if p.strip()]
        if len(items) >= 2:
            return items
    return None


# ----------------------------------------------------------- top-level
def clean(raw: Any) -> tuple[str, int | None]:
    """Full cleaning pipeline.

    Returns ``(plain_text, trend)`` where ``trend`` is ``±1`` / ``0`` if a
    trend template was lifted, else ``None``.
    """
    if raw is None:
        return "", None
    if not isinstance(raw, str):
        raw = str(raw)
    s = raw
    s = strip_refs(s)
    s = strip_comments(s)
    s, trend = extract_trend(s)
    s = handle_templates(s)         # cite/cosmetic/list templates
    s = resolve_wikilinks(s)
    s = resolve_external_links(s)
    s = strip_html_tags(s)
    # Whitespace normalization.
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip(), trend
