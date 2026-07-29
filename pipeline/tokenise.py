"""
Tokenisation for the reading pane. Phase 3.

A token is a maximal run of Arabic letters and diacritics. Everything between
two tokens — spaces, guillemets, the dashes around honorifics, punctuation — is
carried on the preceding token as `punctuationAfter`, and anything before the
first token is carried on the record. Concatenating
`token.surface + token.punctuationAfter` across a record reproduces its text
exactly, which is what lets the reading pane wrap every word in its own element
without disturbing Arabic shaping.

The editorial `(بخاري: N)` cross-reference is removed first: it is apparatus,
not text, and the workbook did not count it either.
"""

from __future__ import annotations

import re

# Arabic letters, harakat, tanwin, shadda, sukun, superscript alef, tatweel.
RE_WORD = re.compile(r"[\u0621-\u064a\u064b-\u0652\u0670\u0640]+")
RE_BUKHARI_REF = re.compile(r"\(\s*بخاري\s*:\s*[\d\s،,و\u2013-]+?\s*\)")


def tokenise(text: str) -> tuple[str, list[dict]]:
    """Return (leading punctuation, tokens). Lossless with respect to `text`."""
    clean = RE_BUKHARI_REF.sub(" ", text)
    matches = list(RE_WORD.finditer(clean))
    if not matches:
        return clean, []

    leading = clean[: matches[0].start()]
    tokens: list[dict] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(clean)
        tokens.append(
            {
                "i": i,
                "raw": m.group(0),
                "punctuationAfter": clean[m.end() : end],
            }
        )
    # Trailing whitespace on the last token is noise, not layout.
    tokens[-1]["punctuationAfter"] = tokens[-1]["punctuationAfter"].rstrip()
    return leading, tokens


def reconstruct(leading: str, tokens: list[dict], key: str = "raw") -> str:
    """Inverse of tokenise(), used to assert losslessness."""
    return leading + "".join(t[key] + t["punctuationAfter"] for t in tokens)
