import { useState, forwardRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { IndexFile } from "@/types/contracts";
import { numberedList } from "@/lib/data";

interface Props {
  index: IndexFile;
}

/**
 * Validates against the numbers that actually resolve, not against a range.
 *
 * al-Tajrid happens to have no gaps — 1202 shares an opener line with 1201 and
 * resolves to that record, so `missingNumbers` is empty. Other corpora will
 * have real gaps, so the check is a set membership test rather than a bounds
 * test, and a number inside the range but absent gets its own message.
 */
export const JumpTo = forwardRef<HTMLInputElement, Props>(function JumpTo({ index }, ref) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const numbers = numberedList(index);
  const max = numbers[numbers.length - 1] ?? 0;

  function submit() {
  // The corpus comes from the route, so a link built here points at the
  // book the reader is actually in.
  const { corpus = "tajrid" } = useParams();
    const trimmed = value.trim();
    if (!trimmed) return;
    if (!/^\d+$/.test(trimmed)) {
      setError("أدخل رقمًا");
      return;
    }
    const n = Number(trimmed);
    if (n < 1 || n > max) {
      setError(`النطاق ١ إلى ${max}`);
      return;
    }
    if (!index.navigation.numberIndex[String(n)]) {
      setError("هذا الرقم غير موجود في هذه النسخة");
      return;
    }
    setError(null);
    setValue("");
    navigate(`/${corpus}/read/${n}`);
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex items-center gap-2">
        <label htmlFor="jump" className="text-sm text-(--color-ink-muted)" lang="ar">
          انتقل إلى
        </label>
        <input
          id="jump"
          ref={ref}
          type="text"
          inputMode="numeric"
          value={value}
          placeholder={`١–${max}`}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
            if (e.key === "Escape") (e.target as HTMLInputElement).blur();
          }}
          aria-invalid={error !== null}
          aria-describedby={error ? "jump-error" : undefined}
          className="w-28 rounded-md border border-(--color-rule) bg-transparent px-2 py-1
                     text-sm tabular-nums"
        />
        <button
          type="button"
          onClick={submit}
          className="rounded-md border border-(--color-rule) px-2 py-1 text-sm
                     transition-colors hover:bg-(--color-rule)/40"
        >
          <span lang="ar">اذهب</span>
        </button>
      </div>
      {/* Reserved so an error message cannot shift the header. */}
      <p
        id="jump-error"
        role="status"
        className="min-h-4 text-xs text-(--color-ink-muted)"
        lang="ar"
      >
        {error}
      </p>
    </div>
  );
});
