import { useEffect, useRef, useState } from "react";
import type { CorpusMeta } from "../types/contracts";

/**
 * The ⓘ next to the book title: a scrollable popup describing whatever book
 * is open — title, author, edition, source provenance, and the recitation
 * links. Every word of content comes from `corpus.about` in the payload
 * (written per corpus in `pipeline/corpora/{id}.yaml`); this component holds
 * no book knowledge, so a second text gets its own popup by writing its own
 * `about` block and nothing here changes.
 *
 * Renders nothing at all for a corpus that has not written one.
 */
export default function AboutBook({ corpus }: { corpus: CorpusMeta }) {
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLButtonElement>(null);

  // Esc closes; focus lands on the close control when the dialog opens and
  // returns to the opener when it shuts, so a keyboard user is never lost.
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      openerRef.current?.focus();
    };
  }, [open]);

  const about = corpus.about;
  if (!about) return null;

  return (
    <>
      <button
        ref={openerRef}
        type="button"
        onClick={() => setOpen(true)}
        aria-label="عن هذا الكتاب"
        aria-haspopup="dialog"
        title="About this book"
        className="flex h-8 w-8 items-center justify-center rounded-full border border-(--color-rule) text-sm text-(--color-ink-muted) transition-colors hover:bg-(--color-rule) hover:text-(--color-ink)"
      >
        {/* An i in a ring, drawn, so it cannot fall back to a tofu glyph. */}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 11v5" />
          <path d="M12 8h.01" />
        </svg>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-6"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="عن هذا الكتاب"
            className="flex max-h-[85dvh] w-full max-w-xl flex-col overflow-hidden rounded-t-xl border border-(--color-rule) bg-(--color-raised) shadow-2xl sm:max-h-[80dvh] sm:rounded-xl"
          >
            <div className="flex items-center justify-between border-b border-(--color-rule) px-4 py-2.5">
              <span className="text-sm text-(--color-ink-muted)" lang="ar">
                عن هذا الكتاب
              </span>
              <button
                ref={closeRef}
                type="button"
                onClick={() => setOpen(false)}
                aria-label="إغلاق"
                className="flex h-10 w-10 items-center justify-center rounded-md transition-colors hover:bg-(--color-rule)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>

            <div className="overflow-y-auto overscroll-contain p-5" dir="rtl">
              <h2 className="arabic mb-1 text-xl" lang="ar">
                {corpus.titleAr}
              </h2>
              <p className="mb-1 text-sm text-(--color-ink-muted)" dir="ltr">
                {corpus.titleEn} — {corpus.author}
                {corpus.authorDied ? ` (d. ${corpus.authorDied})` : ""}
              </p>
              {corpus.edition && (
                <p className="arabic mb-4 text-xs text-(--color-ink-muted)" lang="ar">
                  {corpus.edition}
                </p>
              )}

              <div dir="ltr">
                {about.description.map((para, i) => (
                  <p key={i} className="mb-3 text-sm leading-relaxed">
                    {para}
                  </p>
                ))}

                <h3 className="mt-5 mb-2 border-b border-(--color-rule) pb-1 text-xs font-bold uppercase tracking-wide text-(--color-ink-muted)">
                  Sources
                </h3>
                <ul>
                  {about.sources.map((s) => (
                    <li key={s.label} className="mb-3 text-sm">
                      <span className="font-semibold">{s.label}.</span>{" "}
                      {s.detail && <span>{s.detail}</span>}{" "}
                      {s.url && (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="break-all text-(--color-accent) underline decoration-dotted underline-offset-2"
                        >
                          source ↗
                        </a>
                      )}
                    </li>
                  ))}
                </ul>

                {about.audio && about.audio.files.length > 0 && (
                  <>
                    <h3 className="mt-5 mb-2 border-b border-(--color-rule) pb-1 text-xs font-bold uppercase tracking-wide text-(--color-ink-muted)">
                      Audio
                    </h3>
                    {about.audio.note && (
                      <p className="mb-2 text-sm text-(--color-ink-muted)">{about.audio.note}</p>
                    )}
                    <ul>
                      {about.audio.files.map((f) => (
                        <li key={f.url} className="mb-1.5 text-sm">
                          <a
                            href={f.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-(--color-accent) underline decoration-dotted underline-offset-2"
                          >
                            {f.label} ↗
                          </a>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
