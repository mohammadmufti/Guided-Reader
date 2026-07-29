import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { IndexFile } from "@/types/contracts";
import { numberAtRecord } from "@/lib/data";

interface Props {
  index: IndexFile;
  open: boolean;
  onClose: () => void;
  currentKitab: number | null;
}

/**
 * Books and chapters, jumping to the first hadith of each.
 *
 * Headings are records in their own right but they are not readable pages —
 * a kitab heading is three words — so selecting one navigates to the first
 * NUMBERED hadith at or after it rather than to the heading itself.
 */
export function BookBrowser({ index, open, onClose, currentKitab }: Props) {
  const navigate = useNavigate();
  const panelRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<number | null>(currentKitab);

  useEffect(() => {
    if (open) {
      setExpanded(currentKitab);
      panelRef.current?.focus();
    }
  }, [open, currentKitab]);

  async function go(recordId: string) {
    const n = await numberAtRecord(recordId);
    if (n !== null) {
      onClose();
      navigate(`/hadith/${n}`);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="إغلاق"
        onClick={onClose}
        className="absolute inset-0 h-full w-full cursor-default bg-black/30"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="الكتب والأبواب"
        tabIndex={-1}
        className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col
                   border-s border-(--color-rule) bg-(--color-surface) shadow-2xl"
      >
        <header className="flex items-baseline justify-between border-b border-(--color-rule) px-5 py-4">
          <h2 className="text-lg" lang="ar">
            الكتب والأبواب
          </h2>
          <span className="text-xs text-(--color-ink-muted)">
            {index.counts.kitab} كتابًا · {index.counts.bab} بابًا
          </span>
        </header>

        <div className="flex-1 overflow-y-auto overscroll-contain px-2 py-2">
          <ul>
            {index.tree.map((kitab) => {
              const isOpen = expanded === kitab.index;
              return (
                <li key={kitab.index}>
                  <div className="flex items-stretch gap-1">
                    <button
                      type="button"
                      onClick={() => setExpanded(isOpen ? null : kitab.index)}
                      aria-expanded={isOpen}
                      className="w-9 shrink-0 rounded-md text-xs text-(--color-ink-muted)
                                 transition-colors hover:bg-(--color-rule)/40"
                    >
                      {kitab.babs.length ? (isOpen ? "▾" : "▸") : ""}
                    </button>
                    <button
                      type="button"
                      onClick={() => void go(kitab.firstRecordId)}
                      className={`flex-1 rounded-md px-2 py-2 text-start transition-colors
                                  hover:bg-(--color-rule)/40 ${
                                    currentKitab === kitab.index ? "font-semibold" : ""
                                  }`}
                      lang="ar"
                    >
                      <span className="me-2 text-xs text-(--color-ink-muted) tabular-nums">
                        {kitab.index}
                      </span>
                      {kitab.titleAr}
                    </button>
                  </div>
                  {isOpen && kitab.babs.length > 0 && (
                    <ul className="mb-1 ms-9 border-s border-(--color-rule) ps-2">
                      {kitab.babs.map((bab) => (
                        <li key={bab.index}>
                          <button
                            type="button"
                            onClick={() => void go(bab.firstRecordId)}
                            className="w-full rounded-md px-2 py-1.5 text-start text-sm
                                       text-(--color-ink-muted) transition-colors
                                       hover:bg-(--color-rule)/40"
                            lang="ar"
                          >
                            {bab.titleAr}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        <footer className="border-t border-(--color-rule) px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-(--color-rule) px-3 py-1.5 text-sm
                       transition-colors hover:bg-(--color-rule)/40"
          >
            <span lang="ar">إغلاق</span>
            <span className="ms-2 text-xs text-(--color-ink-muted)">Esc</span>
          </button>
        </footer>
      </div>
    </div>
  );
}
