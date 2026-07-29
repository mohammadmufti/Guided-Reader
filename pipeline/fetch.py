#!/usr/bin/env python3
"""
Acquire and checksum every source this corpus needs. Phase 0.

    python pipeline/fetch.py                 # fetch what is missing or changed
    python pipeline/fetch.py --verify        # checksum only, download nothing
    python pipeline/fetch.py --force         # re-download regardless

Idempotence contract: a second run downloads nothing. Each file's sha256 is
recorded in `cache/manifest.json`; if the file on disk still hashes to the
recorded value, it is left alone. If it hashes to something else the run fails
loudly rather than silently proceeding on changed input — a corpus that shifts
under the pipeline invalidates every downstream measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
def manifest_path(corpus: str) -> Path:
    """
    One manifest per corpus.

    Phase 0 wrote a single `manifest.json` and refused to mix corpora in it,
    which was safe but made a second corpus impossible without deleting the
    first. Found by actually running a second text through — the guard fired on
    the very first command.
    """
    return CACHE / f"manifest-{corpus}.json"
USER_AGENT = "tajrid-reader-pipeline/0.1 (+research; contact via repo)"
TIMEOUT = 180

# Where a `kind: local` source is looked for, in order: an explicit override,
# then the repository root, then the cache. A user-supplied workbook has no URI
# for CI to fetch, so the convention is that it sits at the repository root and
# is committed alongside the code.
LOCAL_SEARCH_PATHS = [
    Path(p) for p in os.environ.get("TAJRID_SOURCE_DIR", "").split(os.pathsep) if p
] + [ROOT.parent, CACHE]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n} B"


def load_manifest(corpus: str) -> dict:
    path = manifest_path(corpus)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"corpus": corpus, "sources": {}}


def save_manifest(corpus: str, m: dict) -> None:
    manifest_path(corpus).write_text(
        json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def download(uri: str, dest: Path) -> None:
    req = urllib.request.Request(uri, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, tmp.open("wb") as out:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            shutil.copyfileobj(resp, out)
    except urllib.error.HTTPError as e:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"HTTP {e.code} fetching {uri}") from e
    except urllib.error.URLError as e:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"network error fetching {uri}: {e.reason}") from e
    tmp.replace(dest)


def find_local(spec: dict) -> Path:
    name = spec["path"]
    for base in LOCAL_SEARCH_PATHS:
        candidate = base / name
        if candidate.exists():
            return candidate
    searched = ", ".join(str(p) for p in LOCAL_SEARCH_PATHS)
    raise RuntimeError(f"local source {name!r} not found. Searched: {searched}")


def acquire(key: str, spec: dict, manifest: dict, *, force: bool, verify_only: bool) -> dict:
    dest = CACHE / spec["filename"]
    recorded = manifest["sources"].get(key)

    if dest.exists() and not force:
        digest = sha256(dest)
        if recorded and recorded["sha256"] == digest:
            print(f"  [cached] {key:<24} {spec['filename']:<34} {human(dest.stat().st_size):>10}")
            return recorded
        if recorded:
            raise RuntimeError(
                f"{key}: {dest.name} on disk hashes {digest[:12]}… but the manifest "
                f"records {recorded['sha256'][:12]}…. The input changed. Delete the file "
                f"and re-fetch deliberately, or run --force."
            )
        # Present but never recorded — adopt it.
        print(f"  [adopt ] {key:<24} {spec['filename']:<34} {human(dest.stat().st_size):>10}")
        return {
            "kind": spec["kind"],
            "origin": spec.get("uri") or spec.get("path"),
            "sha256": digest,
            "bytes": dest.stat().st_size,
            "retrieved": date.today().isoformat(),
        }

    if verify_only:
        raise RuntimeError(f"{key}: {dest.name} absent and --verify forbids fetching")

    if spec["kind"] == "http":
        print(f"  [fetch ] {key:<24} {spec['filename']:<34} …", flush=True)
        download(spec["uri"], dest)
        origin = spec["uri"]
    elif spec["kind"] == "local":
        src = find_local(spec)
        print(f"  [copy  ] {key:<24} {spec['filename']:<34} from {src.parent}", flush=True)
        shutil.copy2(src, dest)
        origin = str(src)
    else:
        raise RuntimeError(f"{key}: unknown source kind {spec['kind']!r}")

    return {
        "kind": spec["kind"],
        "origin": origin,
        "sha256": sha256(dest),
        "bytes": dest.stat().st_size,
        "retrieved": date.today().isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="tajrid", help="corpus id under pipeline/corpora/")
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    ap.add_argument("--verify", action="store_true", help="checksum existing files, fetch nothing")
    args = ap.parse_args()

    cfg_path = ROOT / "corpora" / f"{args.corpus}.yaml"
    if not cfg_path.exists():
        print(f"no such corpus config: {cfg_path}", file=sys.stderr)
        return 1
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    CACHE.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(args.corpus)
    manifest["corpus"] = args.corpus

    print(f"corpus: {args.corpus}  ({cfg['display']['titleEn']})")
    failures: list[str] = []
    for key, spec in cfg["sources"].items():
        try:
            manifest["sources"][key] = acquire(
                key, spec, manifest, force=args.force, verify_only=args.verify
            )
        except RuntimeError as e:
            print(f"  [FAIL  ] {key:<24} {e}", file=sys.stderr)
            failures.append(key)

    save_manifest(args.corpus, manifest)

    print()
    print(f"{'source':<24} {'bytes':>12}  sha256")
    for key, rec in manifest["sources"].items():
        print(f"{key:<24} {rec['bytes']:>12,}  {rec['sha256']}")

    if failures:
        print(f"\n{len(failures)} source(s) failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"\nall {len(manifest['sources'])} sources present and checksummed -> "
          f"{manifest_path(args.corpus).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
