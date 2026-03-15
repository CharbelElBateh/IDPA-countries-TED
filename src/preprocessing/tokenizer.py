"""Text tokenizer for infobox field values."""

import re


def tokenize(text: str) -> list[str]:
    """
    Split text into word/number tokens, ignoring punctuation.
    Returns a list of non-empty alphanumeric tokens.

    Examples:
        tokenize("I like data processing") -> ['I', 'like', 'data', 'processing']
        tokenize("$11,793") -> ['11', '793']
        tokenize("+2") -> ['2']
    """
    return re.findall(r'[A-Za-z0-9]+', text)
