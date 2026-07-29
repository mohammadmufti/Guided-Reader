import { Link } from "react-router-dom";

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
}

export function NavControls({ prevNumber, nextNumber }: Props) {
  return (
    <nav
      className="flex items-center justify-between gap-4"
      aria-label="التنقل بين الأحاديث"
    >
      {/* Physically left: forward. */}
      <Step to={nextNumber} labelAr="التالي" labelEn="Next" arrow="←" side="next" />
      <Step to={prevNumber} labelAr="السابق" labelEn="Previous" arrow="→" side="prev" />
    </nav>
  );
}

function Step({
  to,
  labelAr,
  labelEn,
  arrow,
  side,
}: {
  to: number | null;
  labelAr: string;
  labelEn: string;
  arrow: string;
  side: "prev" | "next";
}) {
  const shared =
    "inline-flex items-center gap-2 rounded-md border border-(--color-rule) px-3 py-2 text-sm";
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
      to={`/hadith/${to}`}
      className={`${shared} transition-colors hover:bg-(--color-rule)/40`}
      aria-label={`${labelEn} — ${labelAr} (${to})`}
      rel={side === "next" ? "next" : "prev"}
    >
      {side === "next" && <span aria-hidden="true">{arrow}</span>}
      <span lang="ar">{labelAr}</span>
      <span className="tabular-nums text-(--color-ink-muted)">{to}</span>
      {side === "prev" && <span aria-hidden="true">{arrow}</span>}
    </Link>
  );
}
