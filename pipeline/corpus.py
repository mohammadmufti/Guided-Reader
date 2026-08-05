"""
Corpus configuration, loaded once and shared. Phase 0.

Before this module, `fetch.py` and `segment.py` read `corpora/{id}.yaml` while
`lexicon.py`, `bind.py` and `analyse.py` hardcoded al-Tajrid's inputs and used
`--corpus` only to pick an OUTPUT directory. That meant `bind.py --corpus X`
silently bound X against al-Tajrid's workbook and Sahih al-Bukhari instead of
failing. One loader, used by every stage, is what makes that impossible.

`source_path` is the single answer to "where does this corpus's copy of source
`key` live". Nothing outside this module should build a cache path by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
CORPORA = ROOT / "corpora"


class ConfigError(RuntimeError):
    """A corpus asked for something its configuration does not declare."""


def load_config(corpus: str) -> dict:
    path = CORPORA / f"{corpus}.yaml"
    if not path.exists():
        raise ConfigError(
            f"no such corpus config: {path}. "
            f"Available: {', '.join(sorted(p.stem for p in CORPORA.glob('*.yaml')))}"
        )
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if cfg.get("id") != corpus:
        raise ConfigError(
            f"{path.name} declares id {cfg.get('id')!r} but was loaded as {corpus!r}. "
            "The filename and the `id` field must agree."
        )
    return cfg


def cache_dir(corpus: str) -> Path:
    """Sources live under cache/{corpus}/, never in one flat directory."""
    return CACHE / corpus


def source_path(cfg: dict, key: str, *, required: bool = True) -> Path | None:
    """
    Resolve one declared source to its cached file.

    `required=False` is how an OPTIONAL input is expressed: a corpus with no
    frequency workbook, or no vocalisation reference, is a legitimate corpus
    that simply cannot reach certain binding tiers. Returning None lets the
    caller skip that tier and SAY SO, which is the behaviour the five-tier
    report is built around. Raising here instead -- or worse, falling back to
    another corpus's file -- is what this module exists to prevent.
    """
    spec = (cfg.get("sources") or {}).get(key)
    if not spec:
        if required:
            raise ConfigError(
                f"corpus {cfg['id']!r} declares no `sources.{key}`, which this "
                f"stage requires. Add it to corpora/{cfg['id']}.yaml, or run a "
                f"stage that treats it as optional."
            )
        return None
    path = cache_dir(cfg["id"]) / spec["filename"]
    if not path.exists():
        raise ConfigError(
            f"corpus {cfg['id']!r}: {key} not cached at {path}. "
            f"Run `python pipeline/fetch.py --corpus {cfg['id']}` first."
        )
    return path


def inline_strip_patterns(cfg: dict) -> tuple[re.Pattern[str], ...]:
    """
    Editorial apparatus to remove before tokenising.

    Previously `(بخاري: N)` was a compiled literal inside `tokenise.py` and was
    applied to EVERY corpus before any config was consulted -- the last
    corpus-specific Arabic string in the shared token path. `segment.py` already
    read the same pattern from `segmentation.editorial_reference`; the two are
    now one.
    """
    pat = (cfg.get("segmentation") or {}).get("editorial_reference")
    return (re.compile(pat),) if pat else ()
