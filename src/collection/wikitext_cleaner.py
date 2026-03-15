"""
Strip wikitext markup from infobox field values, producing clean plain text
or structured lists of items (for {{unbulleted list|...}} templates).
"""

import re


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_value(raw: str) -> str:
    """
    Return a cleaned plain-text string for a single infobox field value.
    Call this when tokenization strategy is 'single_node'.
    """
    text = raw
    text = _strip_html_comments(text)
    text = _strip_ref_tags(text)
    text = _strip_cite_templates(text)
    text = _strip_efn_templates(text)
    text = _strip_inline_efn_ref_args(text)     # strip bare |efn|text|ref|...|</ref>| in list pipes
    text = _strip_standalone_tree_lists(text)   # remove duplicate outer {{Tree list}}
    text = _expand_unbulleted_list(text)         # handles embedded Tree list items
    text = _unwrap_wiki_links(text)
    text = _strip_html_tags(text)
    text = _strip_remaining_templates(text)
    text = _normalise_whitespace(text)
    return text


def extract_list_items(raw: str) -> list[str]:
    """
    Return a list of cleaned items for multi-value fields.
    If the value is an {{unbulleted list|...}}, each pipe-separated item is
    cleaned and returned separately.
    For plain values, returns a single-element list.
    Call this when tokenization strategy is 'token_nodes'.
    """
    text = raw
    text = _strip_html_comments(text)
    text = _strip_ref_tags(text)
    text = _strip_cite_templates(text)
    text = _strip_efn_templates(text)
    text = _strip_inline_efn_ref_args(text)     # strip bare |efn|text|ref|...|</ref>| in list pipes
    text = _strip_standalone_tree_lists(text)   # remove duplicate outer {{Tree list}} blocks

    items = _extract_unbulleted_items(text)
    if items is not None:
        # Filter and expand items
        result = []
        for item in items:
            if _is_junk_item(item):
                continue
            # Item may be a multi-line bullet block from an embedded Tree list
            if _is_bullet_block(item):
                result.extend(_extract_bullet_lines(item))
            else:
                cleaned = _clean_item(item)
                if cleaned:
                    result.append(cleaned)
        return result

    # Plain value
    single = _clean_item(text)
    return [single] if single else []


# ---------------------------------------------------------------------------
# Ref / comment stripping
# ---------------------------------------------------------------------------

def _strip_html_comments(text: str) -> str:
    return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)


def _strip_ref_tags(text: str) -> str:
    text = re.sub(r'<ref[^>]*/>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'</ref>', '', text, flags=re.IGNORECASE)
    return text


def _strip_html_tags(text: str) -> str:
    """Strip any remaining HTML/XML tags like <br />, <span>, etc."""
    return re.sub(r'<[^>]+/?>', '', text)


# ---------------------------------------------------------------------------
# Template stripping
# ---------------------------------------------------------------------------

def _strip_cite_templates(text: str) -> str:
    return _strip_templates_named(text, r'[Cc]ite[_ ]?\w*')


def _strip_efn_templates(text: str) -> str:
    return _strip_templates_named(text, r'efn')


def _strip_templates_named(text: str, name_pattern: str) -> str:
    pattern = re.compile(r'\{\{' + name_pattern + r'(?:\s*\||\s*\}\})', re.IGNORECASE)
    for _ in range(20):  # max iterations guard
        m = pattern.search(text)
        if not m:
            break
        start = text.rfind('{{', 0, m.start() + 2)
        if start == -1:
            start = m.start()
        new_text = _remove_template_at(text, start)
        if new_text == text:
            break
        text = new_text
    return text


def _remove_template_at(text: str, start: int) -> str:
    """Remove the {{ ... }} template starting at position start."""
    depth = 0
    i = start
    while i < len(text) - 1:
        if text[i:i+2] == '{{':
            depth += 1
            i += 2
        elif text[i:i+2] == '}}':
            depth -= 1
            i += 2
            if depth == 0:
                return text[:start] + text[i:]
        else:
            i += 1
    return text


def _strip_inline_efn_ref_args(text: str) -> str:
    """
    Strip bare |efn|footnote_text|ref|ref_attrs|</ref>| sequences that appear
    inside unbulleted list pipes when {{efn|...}} is embedded in a list item.
    Pattern: everything from |efn| up to the next newline+| (next real list item).
    """
    # Match |efn| followed by any content up to the next \n| (next list item line)
    text = re.sub(r'\|efn\|.*?(?=\n\s*\|)', '', text, flags=re.DOTALL)
    return text


def _strip_remaining_templates(text: str) -> str:
    """Remove any leftover {{ ... }} templates (handling nesting)."""
    for _ in range(20):
        if '{{' not in text:
            break
        new_text = _remove_all_outermost_templates(text)
        if new_text == text:
            break
        text = new_text
    return text


def _remove_all_outermost_templates(text: str) -> str:
    result = []
    depth = 0
    i = 0
    while i < len(text):
        if text[i:i+2] == '{{':
            depth += 1
            i += 2
        elif text[i:i+2] == '}}':
            depth -= 1
            i += 2
        else:
            if depth == 0:
                result.append(text[i])
            i += 1
    return ''.join(result)


# ---------------------------------------------------------------------------
# Tree list handling
# ---------------------------------------------------------------------------

def _strip_standalone_tree_lists(text: str) -> str:
    """
    Remove standalone {{Tree list}} ... {{Tree list/end}} blocks.
    These appear as duplicates after the {{unbulleted list|...}} closes.
    The content is already included inside the unbulleted list pipes.
    """
    pattern = re.compile(
        r'\{\{[Tt]ree list\}\}.*?\{\{[Tt]ree list/end\}\}',
        flags=re.DOTALL,
    )
    return pattern.sub('', text)


def _is_bullet_block(item: str) -> bool:
    """Return True if the item is a multi-line block of * bullet lines."""
    return bool(re.search(r'^\s*\*', item, re.MULTILINE))


def _extract_bullet_lines(item: str) -> list[str]:
    """Extract non-empty lines from a * bullet block, stripping leading * chars."""
    lines = []
    for line in item.splitlines():
        line = re.sub(r'^\s*\*+\s*', '', line).strip()
        if line:
            cleaned = _clean_item(line)
            if cleaned:
                lines.append(cleaned)
    return lines


# ---------------------------------------------------------------------------
# Unbulleted list handling
# ---------------------------------------------------------------------------

def _extract_unbulleted_items(text: str) -> list[str] | None:
    """
    If text starts with {{unbulleted list|...}}, return the pipe-separated items.
    Otherwise return None.
    """
    stripped = text.strip()
    m = re.match(
        r'\{\{(?:unbulleted list|plainlist|ubl|hlist)\s*\|',
        stripped,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    content = _extract_template_body(stripped, 0)
    if content is None:
        return None
    return _split_template_args(content)


def _expand_unbulleted_list(text: str) -> str:
    """
    Replace {{unbulleted list|a|b|c}} with joined text.
    Handles embedded Tree list pipes and bullet blocks.
    """
    result = []
    last = 0
    pattern = re.compile(r'\{\{(?:unbulleted list|plainlist|ubl|hlist)\b', re.IGNORECASE)
    for m in pattern.finditer(text):
        result.append(text[last:m.start()])
        end = _find_template_end(text, m.start())
        if end == -1:
            result.append(text[m.start():])
            last = len(text)
            break
        template_text = text[m.start():end]
        content = _extract_template_body(template_text, 0)
        if content is None:
            result.append(template_text)
        else:
            args = _split_template_args(content)
            parts = []
            for arg in args:
                if _is_junk_item(arg):
                    continue
                if _is_bullet_block(arg):
                    parts.extend(_extract_bullet_lines(arg))
                else:
                    cleaned = _clean_item(arg)
                    if cleaned:
                        parts.append(cleaned)
            result.append(', '.join(parts))
        last = end
    result.append(text[last:])
    return ''.join(result)


def _extract_template_body(text: str, start: int) -> str | None:
    """
    Given text and position of '{{', return the content after the first '|'
    up to the matching '}}', or None if unbalanced.
    """
    depth = 0
    i = start
    while i < len(text) - 1:
        if text[i:i+2] == '{{':
            depth += 1
            i += 2
        elif text[i:i+2] == '}}':
            depth -= 1
            if depth == 0:
                body = text[start+2:i]
                pipe = body.find('|')
                if pipe == -1:
                    return ''
                return body[pipe+1:]
            i += 2
        else:
            i += 1
    return None


def _find_template_end(text: str, start: int) -> int:
    """Return the index just after the matching '}}' for '{{' at start."""
    depth = 0
    i = start
    while i < len(text) - 1:
        if text[i:i+2] == '{{':
            depth += 1
            i += 2
        elif text[i:i+2] == '}}':
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return -1


def _split_template_args(args_str: str) -> list[str]:
    """
    Split on top-level '|' characters (ignoring pipes inside {{ }} or [[ ]]).
    """
    parts = []
    depth_brace = 0
    depth_bracket = 0
    current: list[str] = []
    i = 0
    while i < len(args_str):
        if args_str[i:i+2] == '{{':
            depth_brace += 1
            current.append('{{')
            i += 2
        elif args_str[i:i+2] == '}}':
            depth_brace -= 1
            current.append('}}')
            i += 2
        elif args_str[i:i+2] == '[[':
            depth_bracket += 1
            current.append('[[')
            i += 2
        elif args_str[i:i+2] == ']]':
            depth_bracket -= 1
            current.append(']]')
            i += 2
        elif args_str[i] == '|' and depth_brace == 0 and depth_bracket == 0:
            parts.append(''.join(current))
            current = []
            i += 1
        else:
            current.append(args_str[i])
            i += 1
    parts.append(''.join(current))
    return parts


# ---------------------------------------------------------------------------
# Junk item detection
# ---------------------------------------------------------------------------

def _is_junk_item(item: str) -> bool:
    """Return True if an unbulleted list item is template noise, not data."""
    s = item.strip()
    if not s:
        return True
    junk_exact = {'efn', 'ref', 'tree list', 'tree list/end', '/ref'}
    if s.lower() in junk_exact:
        return True
    junk_patterns = [
        r'^</?\s*ref\b',
        r'^\s*name\s*=',
        r'^\s*group\s*=',
        r'^\s*url',
        r'^\s*doi\s*=',
        r'^\s*jstor\s*=',
    ]
    for p in junk_patterns:
        if re.match(p, s, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# Wiki link unwrapping
# ---------------------------------------------------------------------------

def _unwrap_wiki_links(text: str) -> str:
    text = re.sub(r'\[\[(?:[^|\]]+)\|([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    return text


# ---------------------------------------------------------------------------
# Item-level cleaning
# ---------------------------------------------------------------------------

def _clean_item(text: str) -> str:
    """Full clean pipeline for a single item string."""
    text = _strip_html_comments(text)
    text = _strip_ref_tags(text)
    text = _strip_cite_templates(text)
    text = _strip_efn_templates(text)
    text = _unwrap_wiki_links(text)
    text = _strip_html_tags(text)
    text = _strip_remaining_templates(text)
    # Strip leading * bullets (for items from bullet blocks)
    text = re.sub(r'^\s*\*+\s*', '', text)
    text = _normalise_whitespace(text)
    return text


def _normalise_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()
