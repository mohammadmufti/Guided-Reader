#!/usr/bin/env python3
"""
Generate `web/src/types/contracts.ts` from `pipeline/contracts.py`.

The contracts exist in two languages but must never diverge, so only one of
them is written by hand. Run this after editing contracts.py:

    python pipeline/codegen.py            # write the .ts file
    python pipeline/codegen.py --check    # exit 1 if the .ts file is stale

`--check` belongs in CI and in every phase gate that touches the contracts.
"""

from __future__ import annotations

import argparse
import sys
import types
import typing
from pathlib import Path

import contracts as C

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "src" / "types" / "contracts.ts"
OUT_NORM = ROOT / "web" / "src" / "lib" / "normalise.ts"

PRIMITIVES: dict[object, str] = {
    str: "string",
    int: "number",
    float: "number",
    bool: "boolean",
    type(None): "null",
}

_ALIASES = list(C.EXPORTED_ALIASES)
# Deliberately a SEPARATE list from _ALIASES. A literal alias is rendered by
# expanding its union; a type alias is rendered by naming its target. They are
# not interchangeable, and mixing them emits `export type X = ;`.
_TYPE_ALIASES = list(getattr(C, "EXPORTED_TYPE_ALIASES", []))
_EXPORTED_NAMES = {cls.__name__ for cls in C.EXPORTED}

# TypeScript's global utility and lib types. A contract named `Record` silently
# shadows `Record<K, V>` for every file that imports it, and the failure surfaces
# far from the cause — so refuse to generate rather than emit the landmine.
# (This is not hypothetical: §5.1's record type was originally called `Record`.)
TS_RESERVED = {
    "Record", "Partial", "Required", "Readonly", "Pick", "Omit", "Exclude",
    "Extract", "NonNullable", "Parameters", "ReturnType", "Awaited", "Map",
    "Set", "Date", "Array", "Object", "Function", "String", "Number", "Boolean",
    "Promise", "Iterator", "Element", "Event", "Document", "Node", "Range",
}


def check_names() -> None:
    """Fail fast on any contract name that collides with a TypeScript global."""
    # Recompute rather than reading the import-time snapshot: the snapshot is
    # taken before any caller can modify EXPORTED, which made an earlier version
    # of this guard silently pass.
    exported = [cls.__name__ for cls in C.EXPORTED]
    type_aliases = list(getattr(C, "EXPORTED_TYPE_ALIASES", []))
    all_names = (
        set(exported)
        | {n for n, _ in C.EXPORTED_ALIASES}
        | {n for n, _ in type_aliases}
    )
    # A type alias whose target is not exported would emit a reference to an
    # interface that does not exist in the file — valid text, broken TypeScript,
    # and --check compares text. Catch it here instead.
    dangling = sorted(
        f"{name} -> {target.__name__}"
        for name, target in type_aliases
        if target.__name__ not in set(exported)
    )
    if dangling:
        raise SystemExit(
            "EXPORTED_TYPE_ALIASES target(s) missing from EXPORTED: "
            + ", ".join(dangling)
        )
    shadowed = sorted({n for n, _ in type_aliases} & set(exported))
    if shadowed:
        raise SystemExit(
            "type alias name(s) collide with an exported interface: "
            + ", ".join(shadowed)
        )
    clashes = sorted(all_names & TS_RESERVED)
    if clashes:
        raise SystemExit(
            "contract type name(s) shadow TypeScript globals: "
            + ", ".join(clashes)
            + "\nRename them in contracts.py (e.g. Record -> CorpusRecord)."
        )
    dupes = sorted({n for n in exported if exported.count(n) > 1})
    if dupes:
        raise SystemExit("duplicate contract type name(s): " + ", ".join(dupes))


def _alias_name(tp: object) -> str | None:
    """Recover the declared alias name for a Literal, so we emit `Layer` not the union."""
    for name, alias in _ALIASES:
        if tp is alias or tp == alias:
            return name
    return None


def render(tp: object) -> str:
    """Render one Python type annotation as TypeScript."""
    named = _alias_name(tp)
    if named:
        return named

    if tp in PRIMITIVES:
        return PRIMITIVES[tp]

    origin = typing.get_origin(tp)
    args = typing.get_args(tp)

    if origin is typing.Annotated:
        return render(args[0])

    if origin is typing.Literal:
        return " | ".join(f'"{a}"' for a in args)

    # `X | None` arrives as types.UnionType (PEP 604) or typing.Union.
    if origin in (typing.Union, types.UnionType):
        parts = [render(a) for a in args]
        # Keep `null` last for readability.
        parts = [p for p in parts if p != "null"] + (["null"] if "null" in parts else [])
        return " | ".join(dict.fromkeys(parts))

    if origin in (list, typing.List):
        inner = render(args[0])
        return f"{inner}[]" if " " not in inner else f"({inner})[]"

    if origin in (dict, typing.Dict):
        return f"Record<{render(args[0])}, {render(args[1])}>"

    if isinstance(tp, type) and tp.__name__ in _EXPORTED_NAMES:
        return tp.__name__

    raise TypeError(f"codegen has no rule for {tp!r}")


def field_doc(tp: object) -> str | None:
    """Pull the Doc(...) note off an Annotated field, if present."""
    if typing.get_origin(tp) is typing.Annotated:
        for meta in typing.get_args(tp)[1:]:
            if isinstance(meta, C.Doc):
                return meta.text
    return None


def wrap(text: str, width: int = 92, indent: str = "  ") -> list[str]:
    """Wrap a doc comment to a sane width."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) == 1:
        return [f"{indent}/** {lines[0]} */"]
    out = [f"{indent}/**"]
    out += [f"{indent} * {ln}" for ln in lines]
    out.append(f"{indent} */")
    return out


def emit() -> str:
    check_names()
    out: list[str] = [
        "// ---------------------------------------------------------------------------",
        "// GENERATED FILE — DO NOT EDIT.",
        "//",
        "// Source of truth: pipeline/contracts.py",
        "// Regenerate:     python pipeline/codegen.py",
        "// Verify:         python pipeline/codegen.py --check",
        "//",
        "// Nulls are meaningful throughout. `root: string | null` means a null root is a",
        "// real answer — particles and proper nouns have none — not a missing value.",
        "// Do not widen these to optional (`?:`) and do not default them to \"\".",
        "// ---------------------------------------------------------------------------",
        "",
    ]

    for name, alias in _ALIASES:
        doc = getattr(C, f"__doc_{name}__", None) or ""
        rendered = " | ".join(f'"{a}"' for a in typing.get_args(alias))
        if doc:
            out += wrap(doc, indent="")
        out.append(f"export type {name} = {rendered};")
        out.append("")

    for cls in C.EXPORTED:
        hints = typing.get_type_hints(cls, globalns=vars(C), include_extras=True)
        if cls.__doc__:
            out += wrap(" ".join(cls.__doc__.split()), indent="")
        out.append(f"export interface {cls.__name__} {{")
        for field, tp in hints.items():
            doc = field_doc(tp)
            if doc:
                out += wrap(doc)
            out.append(f"  {field}: {render(tp)};")
        out.append("}")
        out.append("")

    # After the interfaces, so the file reads top-down even though TypeScript
    # hoists types. These exist so a rename in contracts.py is not a breaking
    # change for every importing component at once — see EXPORTED_TYPE_ALIASES.
    if _TYPE_ALIASES:
        out.append("// Compatibility aliases for renamed contracts.")
        for name, target in _TYPE_ALIASES:
            out.append(f"export type {name} = {target.__name__};")
        out.append("")

    return "\n".join(out)


def emit_normalise() -> str:
    """
    Emit the TypeScript twin of normalise.py.

    Search normalises the query with the same function the lexicon joins on, so
    a student can type without diacritics and still match vocalised text. Two
    hand-written copies of that mapping would eventually disagree, and the
    failure would be silent — a query that quietly matches nothing. So the
    TypeScript is generated from the Python tables, and `--check` fails on drift
    exactly as it does for the contracts.
    """
    import normalise as N

    diacritics = sorted(chr(c) for c in N.DIACRITICS)
    stripped = "".join("\\u%04X" % ord(c) for c in diacritics)
    lines = []
    for k, v in N.LETTERS.items():
        lines.append('  "\\u%04X": "\\u%04X", // %s -> %s' % (k, ord(v), chr(k), v))
    pairs = "\n".join(lines)

    header = [
        "// ---------------------------------------------------------------------------",
        "// GENERATED FILE — DO NOT EDIT.",
        "//",
        "// Source of truth: pipeline/normalise.py",
        "// Regenerate:     python pipeline/codegen.py",
        "//",
        "// This is the join key between corpus tokens and the lexicon, asserted in the",
        "// pipeline against all 22,464 `search_key` values. Note the hamza rule is NOT",
        "// uniform: alef-seated hamza folds to bare ALEF, waw- and yeh-seated hamza fold",
        "// to bare HAMZA. Getting that backwards mis-joins about 600 forms while still",
        "// looking plausible.",
        "// ---------------------------------------------------------------------------",
        "",
        "const DIACRITICS = /[" + stripped + "]/g;",
        "",
        "const LETTERS: Record<string, string> = {",
        pairs,
        "};",
        "",
        "/** Fold a vocalised surface form to its `search_key`. */",
        "export function normalise(form: string): string {",
        '  let out = "";',
        '  for (const ch of form.replace(DIACRITICS, "")) {',
        "    out += LETTERS[ch] ?? ch;",
        "  }",
        "  return out;",
        "}",
        "",
        "/**",
        " * Canonical form of a ROOT, for lookup. Looser than normalise(): the",
        " * workbook writes hamza-initial roots as ءرض where a reader types أرض, and",
        " * recall matters more than precision when asking what shares a root.",
        " */",
        "export function rootKey(root: string): string {",
        '  let out = "";',
        "  for (const ch of normalise(root)) {",
        '    const c = ch === "\\u0621" ? "\\u0627" : ch;',
        '    if (c >= "\\u0621" && c <= "\\u064A") out += c;',
        "  }",
        "  return out;",
        "}",
        "",
    ]
    return "\n".join(header)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the generated file is stale")
    args = ap.parse_args()

    generated = emit()
    generated_norm = emit_normalise()

    if args.check:
        if not OUT_NORM.exists() or OUT_NORM.read_text(encoding="utf-8") != generated_norm:
            print(f"FAIL  {OUT_NORM.relative_to(ROOT)} is stale. Run: python pipeline/codegen.py")
            return 1
        if not OUT.exists():
            print(f"FAIL  {OUT.relative_to(ROOT)} does not exist. Run: python pipeline/codegen.py")
            return 1
        if OUT.read_text(encoding="utf-8") != generated:
            print(f"FAIL  {OUT.relative_to(ROOT)} is stale. Run: python pipeline/codegen.py")
            return 1
        print(f"OK    {OUT.relative_to(ROOT)} is in sync with contracts.py")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(generated, encoding="utf-8")
    OUT_NORM.parent.mkdir(parents=True, exist_ok=True)
    OUT_NORM.write_text(generated_norm, encoding="utf-8")
    print(f"wrote {OUT_NORM.relative_to(ROOT)}")
    n_types = len(C.EXPORTED) + len(_ALIASES)
    print(f"wrote {OUT.relative_to(ROOT)}  ({n_types} types, {len(generated.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
