// ---------------------------------------------------------------------------
// GENERATED FILE — DO NOT EDIT.
//
// Source of truth: pipeline/normalise.py
// Regenerate:     python pipeline/codegen.py
//
// This is the join key between corpus tokens and the lexicon, asserted in the
// pipeline against all 22,464 `search_key` values. Note the hamza rule is NOT
// uniform: alef-seated hamza folds to bare ALEF, waw- and yeh-seated hamza fold
// to bare HAMZA. Getting that backwards mis-joins about 600 forms while still
// looking plausible.
// ---------------------------------------------------------------------------

const DIACRITICS = /[\u0640\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0653\u0654\u0655\u0670]/g;

const LETTERS: Record<string, string> = {
  "\u0623": "\u0627", // أ -> ا
  "\u0625": "\u0627", // إ -> ا
  "\u0622": "\u0627", // آ -> ا
  "\u0649": "\u064A", // ى -> ي
  "\u0629": "\u0647", // ة -> ه
  "\u0626": "\u0621", // ئ -> ء
  "\u0624": "\u0621", // ؤ -> ء
};

/** Fold a vocalised surface form to its `search_key`. */
export function normalise(form: string): string {
  let out = "";
  for (const ch of form.replace(DIACRITICS, "")) {
    out += LETTERS[ch] ?? ch;
  }
  return out;
}

/**
 * Canonical form of a ROOT, for lookup. Looser than normalise(): the
 * workbook writes hamza-initial roots as ءرض where a reader types أرض, and
 * recall matters more than precision when asking what shares a root.
 */
export function rootKey(root: string): string {
  let out = "";
  for (const ch of normalise(root)) {
    const c = ch === "\u0621" ? "\u0627" : ch;
    if (c >= "\u0621" && c <= "\u064A") out += c;
  }
  return out;
}
