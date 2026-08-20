#!/usr/bin/env python3
"""
A digest of the configs a stage actually depends on, for CI cache keys.

WHY THIS EXISTS. The morphology cache — the most expensive one in the build —
was keyed on `hashFiles('pipeline/corpora/*.yaml')`. That glob is correct in
spirit and too wide in fact: it includes the three LEXICAL SOURCE configs
(lane, lisan, nihaya), which `analyse.py` never reads. It walks
`build/*/records.json` and a dictionary never produces one.

So editing a comment in `lisan.yaml` invalidated the morphology cache and
forced a full re-analysis of every corpus — minutes of CAMeL for a change that
could not possibly affect its output. Adding a fourth dictionary would do the
same, every time its config was touched.

Listing the reading corpora explicitly in the workflow would fix it and rot:
the next corpus gets forgotten, and a forgotten corpus means a stale analysis
silently reused — exactly the failure the `corpora/*.yaml` glob was widened to
prevent in the first place. So the set is DERIVED, from the same `role` field
that already distinguishes a book from a dictionary.

    python pipeline/corpus_digest.py            # reading corpora (default)
    python pipeline/corpus_digest.py --lexical  # dictionaries only

Prints one hex digest. Stable across machines and orderings: configs are sorted
by id and hashed by content, so a digest changes when and only when a config a
stage reads changes.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from corpus import is_lexical_source  # noqa: E402


def digest(lexical: bool) -> str:
    h = hashlib.sha256()
    for path in sorted((ROOT / "corpora").glob("*.yaml")):
        raw = path.read_bytes()
        cfg = yaml.safe_load(raw.decode("utf-8"))
        if is_lexical_source(cfg) != lexical:
            continue
        # The id as well as the bytes: renaming a config to an id already in
        # use would otherwise leave the digest unchanged.
        h.update(cfg.get("id", path.stem).encode("utf-8"))
        h.update(b"\0")
        h.update(raw)
        # AND THE CONTENT OF ANY `kind: local` SOURCE. A config names such a
        # file by path, so replacing the file without touching the config
        # would leave the digest unchanged and serve an analysis derived from
        # the old bytes. Riyad's records are built from a Shamela .bok, so
        # that is not hypothetical.
        for spec in (cfg.get("sources") or {}).values():
            if isinstance(spec, dict) and spec.get("kind") == "local":
                local = ROOT.parent / str(spec.get("path", ""))
                if local.is_file():
                    h.update(hashlib.sha256(local.read_bytes()).digest())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--lexical",
        action="store_true",
        help="digest the dictionary configs instead of the reading corpora",
    )
    args = ap.parse_args()
    print(digest(args.lexical))
    return 0


if __name__ == "__main__":
    sys.exit(main())
