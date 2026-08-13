import { useCallback, useEffect, useMemo, useRef } from "react";
import type { HadithFile, Token } from "@/types/contracts";
import { stripHarakat } from "@/hooks/useSettings";

/**
 * The reading pane. Phase 6.
 *
 * SHAPING. Each word is wrapped in its own element, which is only safe because
 * Arabic shaping is word-internal: letters join within a word and never across
 * the space between two words. The separator itself is emitted as a bare text
 * node BETWEEN the spans rather than inside them, so the browser still sees an
 * ordinary run of text with ordinary word boundaries. `e2e_phase6.py` renders
 * the same hadith as one unsegmented block and as spans and diffs the two
 * bitmaps, so this claim is checked rather than asserted.
 *
 * NO LAYOUT SHIFT ON SELECTION. The highlight is painted outside the box with
 * a spread box-shadow, so a selected word occupies exactly the same geometry as
 * an unselected one and nothing reflows.
 *
 * DIRECTION. Arabic runs right to left, so the next word is to the LEFT:
 * ArrowLeft advances, ArrowRight goes back. That is the same rule the hadith
 * controls use, applied at word scale.
 */

interface Props {
  record: HadithFile;
  selected: number | null;
  onSelect: (index: number | null) => void;
  /** False hides the vowel marks, turning the pane into a self-test. */
  harakat: boolean;
  /** Zawa'id additions are set slightly quieter than the hadith they follow. */
  muted?: boolean;
}

export function ReadingPane({ record, selected, onSelect, harakat, muted }: Props) {
  const paneRef = useRef<HTMLParagraphElement>(null);

  const clickable = record.tokens.filter((t) => t.clickable).map((t) => t.i);

  // Which words sit inside a Qur'anic quotation. Verses are wrapped in `{ … }`
  // in the source (the Shamela/OpenITI convention). The tokeniser only ever
  // puts Arabic letters and diacritics in a token, so a brace is never inside
  // `surface`/`raw` — it rides in `leading` or a token's `punctuationAfter`.
  // Walking the record's text in order and tracking brace depth therefore says,
  // for each word, whether it falls between an opening and a closing brace.
  // Braces are balanced and well-nested within every record, so a per-record
  // walk is sufficient — no verse straddles two panes.
  //
  // The vocalisation itself is untouched: `token.surface` still carries the
  // vowels, which is what search, the lexicon and the word panel are built on.
  // This only tells the pane to paint a Qur'anic word in bare rasm rather than
  // with the system's inferred vowels when harakat are on.
  const inAyah = useMemo(() => {
    const flags: boolean[] = new Array(record.tokens.length).fill(false);
    let depth = 0;
    const scan = (s: string) => {
      for (const ch of s) {
        if (ch === "{") depth++;
        else if (ch === "}") depth = Math.max(0, depth - 1);
      }
    };
    scan(record.leading);
    record.tokens.forEach((t, idx) => {
      flags[idx] = depth > 0; // state on entering this word's letters
      scan(t.punctuationAfter); // raw carries no braces; only this can
    });
    return flags;
  }, [record.leading, record.tokens]);

  /** Move to the next or previous CLICKABLE word, skipping inert ones. */
  const step = useCallback(
    (from: number | null, delta: 1 | -1) => {
      if (clickable.length === 0) return;
      if (from === null) {
        onSelect(delta === 1 ? clickable[0]! : clickable[clickable.length - 1]!);
        return;
      }
      const at = clickable.indexOf(from);
      const nextAt = at === -1 ? 0 : at + delta;
      const target = clickable[nextAt];
      if (target !== undefined) onSelect(target);
    },
    [clickable, onSelect],
  );

  // Roving tabindex: the pane is a single tab stop and the arrows move within
  // it. Giving every word its own tab stop would put 1,600 of them between the
  // reader and the footer on the longest hadith.
  useEffect(() => {
    if (selected === null) return;
    const el = paneRef.current?.querySelector<HTMLElement>(`[data-token="${selected}"]`);
    if (el && document.activeElement !== el) el.focus({ preventScroll: true });
  }, [selected, record.id]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    switch (e.key) {
      case "ArrowLeft":
        e.preventDefault();
        e.stopPropagation();
        step(selected, 1);
        break;
      case "ArrowRight":
        e.preventDefault();
        e.stopPropagation();
        step(selected, -1);
        break;
      case "Home":
        e.preventDefault();
        e.stopPropagation();
        if (clickable[0] !== undefined) onSelect(clickable[0]);
        break;
      case "End":
        e.preventDefault();
        e.stopPropagation();
        if (clickable.length) onSelect(clickable[clickable.length - 1]!);
        break;
      case "Escape":
        // Release the pane so the arrows go back to moving between hadith.
        e.stopPropagation();
        onSelect(null);
        (e.target as HTMLElement).blur();
        break;
      default:
    }
  }

  return (
    <p
      ref={paneRef}
      dir="rtl"
      lang="ar"
      onKeyDown={onKeyDown}
      // `whitespace-pre-line` ONLY on the aside: Bulugh merges a hadith's
      // several takhrij paragraphs into one record separated by newlines,
      // and this is what turns them into plain line breaks. The matn joins
      // its continuations with a space and never carries a newline, so the
      // main pane keeps normal whitespace.
      className={`arabic-body ${muted ? "whitespace-pre-line text-(--color-ink-muted)" : ""}`}
      style={muted ? { fontSize: "calc(var(--ar-size) * 0.82)" } : undefined}
    >
      {record.leading}
      {record.tokens.map((token) => (
        <TokenSpan
          key={token.i}
          token={token}
          selected={token.i === selected}
          tabbable={token.i === (selected ?? firstClickable(record))}
          onSelect={onSelect}
          harakat={harakat}
          inAyah={inAyah[token.i] ?? false}
        />
      ))}
    </p>
  );
}

function firstClickable(record: HadithFile): number | null {
  return record.tokens.find((t) => t.clickable)?.i ?? null;
}

function TokenSpan({
  token,
  selected,
  tabbable,
  onSelect,
  harakat,
  inAyah,
}: {
  token: Token;
  selected: boolean;
  tabbable: boolean;
  onSelect: (i: number | null) => void;
  harakat: boolean;
  /** Word sits inside a Qur'anic `{ … }` quotation; never show inferred vowels. */
  inAyah: boolean;
}) {
  // Harakat are hidden when the reader has them off, and always for Qur'anic
  // words: the system's vowels are inferred MSA readings, not the mushaf, so a
  // verse is shown in bare rasm rather than vocalised with a guess.
  const shown = harakat && !inAyah ? token.surface : stripHarakat(token.surface);
  if (!token.clickable) {
    return (
      <>
        <span className="opacity-60" title="غير موجود في المعجم">
          {shown}
        </span>
        {token.punctuationAfter}
      </>
    );
  }

  // The highlight is painted OUTSIDE the box with a spread box-shadow, so a
  // selected word occupies exactly the same geometry as an unselected one.
  // The obvious approach — horizontal padding cancelled by a negative margin —
  // nets to zero at integer sizes but not at fractional ones: 0.15em is 3px at
  // 20px text and 4.5px at 30px, and the rounding moved glyphs by a subpixel.
  // The pixel diff against unsegmented text caught it at 1.1% of pixels.
  const halo = "0 0 0 0.16em";
  const style = selected
    ? {
        backgroundColor: "var(--color-accent-soft)",
        boxShadow: `${halo} var(--color-accent-soft)`,
      }
    : undefined;

  return (
    <>
      <span
        role="button"
        tabIndex={tabbable ? 0 : -1}
        data-token={token.i}
        data-confidence={token.confidence}
        aria-pressed={selected}
        style={{
          ...style,
          // A guess is marked as a guess. Tier 4 is the most-frequent fallback,
          // measured at 69.9% correct against held-out Bukhari vocalisation, so
          // it should not look as settled as an aligned reading. Underlines do
          // not affect layout.
          ...(token.confidence === "low"
            ? { textDecoration: "underline dotted", textUnderlineOffset: "0.3em" }
            : {}),
        }}
        onClick={() => onSelect(selected ? null : token.i)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(selected ? null : token.i);
          }
        }}
        className={
          "cursor-pointer rounded-sm outline-none transition-colors " +
          (selected ? "" : "hover:bg-(--color-rule)")
        }
      >
        {shown}
      </span>
      {token.punctuationAfter}
    </>
  );
}
