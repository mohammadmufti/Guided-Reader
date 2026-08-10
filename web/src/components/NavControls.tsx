import { Link, useParams } from "react-router-dom";

/**
 * DIRECTION DECISION — read this before changing an arrow.
 *
 * Arabic runs right to left, so moving FORWARD through the book moves LEFT
 * across the screen. Therefore:
 *
 *   next hadith      -> sits on the LEFT,  arrow points LEFT  (←), key ArrowLeft
 *   previous hadith  -> sits on the RIGHT, arrow points RIGHT (→), key ArrowRight
 *
 * This is the opposite of an English interface and it is intentional. Because
 * an arrow alone is ambiguous to a reader who has both conventions in their
 * head, every control is labelled with a word as well as an arrow, and the same
 * mapping is used for the keyboard in useKeyboard.ts. The two must not drift.
 */

interface Props {
  prevNumber: number | null;
  nextNumber: number | null;
  /** Rendered between the two arrows, centred on the row. */
  centre?: React.ReactNode;
}

export function NavControls({ prevNumber, nextNumber, centre }: Props) {
  return (
    <nav
      // Grid, not flex: the two arrows have different label widths ("Next"
      // against "Previous"), so justify-between leaves the middle slot a few
      // pixels off the row's midpoint. Equal outer tracks put it dead centre.
      className="grid grid-cols-[1fr_auto_1fr] items-center gap-4"
      aria-label="التنقل بين الأحاديث"
    >
      {/* Physically left: forward. */}
      <div className="justify-self-start">
        <Step to={nextNumber} labelAr="التالي" labelEn="Next" arrow="←" side="next" />
      </div>
      {/* The book controls belong between the arrows, not stacked under them:
          there is room on this row, and putting them below pushed the reader's
          eye past the navigation to find them. */}
      <div className="min-w-0 px-2">{centre}</div>
      <div className="justify-self-end">
        <Step to={prevNumber} labelAr="السابق" labelEn="Previous" arrow="→" side="prev" />
      </div>
    </nav>
  );
}

function Step({
  to,
  labelAr,
  labelEn,
  arrow,
  side,
  compact = false,
}: {
  to: number | null;
  labelAr: string;
  labelEn: string;
  arrow: string;
  side: "prev" | "next";
  /** Header size: no number, tighter box, so it sits beside the other controls. */
  compact?: boolean;
}) {
  // The corpus comes from the route, so a link built here points at the
  // book the reader is actually in.
  const { corpus = "tajrid" } = useParams();
  const shared =
    "inline-flex items-center rounded-md border border-(--color-rule) text-sm " +
    (compact ? "gap-1 px-2 py-1.5" : "gap-2 px-3 py-2");
  if (to === null) {
    return (
      <span
        className={`${shared} cursor-default text-(--color-ink-muted) opacity-45`}
        aria-disabled="true"
      >
        {side === "next" && <span aria-hidden="true">{arrow}</span>}
        <span lang="ar">{labelAr}</span>
        {side === "prev" && <span aria-hidden="true">{arrow}</span>}
      </span>
    );
  }
  return (
    <Link
      to={`/${corpus}/read/${to}`}
      className={`${shared} transition-colors hover:bg-(--color-rule)/40`}
      aria-label={`${labelEn} — ${labelAr} (${to})`}
      rel={side === "next" ? "next" : "prev"}
    >
      {side === "next" && <span aria-hidden="true">{arrow}</span>}
      <span lang="ar">{labelAr}</span>
      {!compact && (
        <span className="tabular-nums text-(--color-ink-muted)">{to}</span>
      )}
      {side === "prev" && <span aria-hidden="true">{arrow}</span>}
    </Link>
  );
}

/**
 * The same two controls, header-sized.
 *
 * They lived only in the footer, which is fine until a word panel runs long —
 * then moving to the next hadith means scrolling past a Lane article to reach
 * a button. Navigation belongs where the other navigation is, beside the book
 * browser.
 *
 * Next stays on the LEFT. Arabic runs right to left, so forward is leftward;
 * see the note at the top of this file.
 */
export function NavCompact({
  prevNumber,
  nextNumber,
}: {
  prevNumber: number | null;
  nextNumber: number | null;
}) {
  return (
    // `dir="ltr"` on the row, so source order IS screen order. The header is
    // rtl, which mirrored the pair and put next on the right — the footer nav
    // escapes this because it positions by grid track rather than by flow.
    // Each label keeps its own `lang="ar"`, so only the boxes are placed ltr.
    <span className="inline-flex items-center gap-1.5" dir="ltr">
      <Step to={nextNumber} labelAr="التالي" labelEn="Next" arrow="←" side="next" compact />
      <Step to={prevNumber} labelAr="السابق" labelEn="Previous" arrow="→" side="prev" compact />
    </span>
  );
}
