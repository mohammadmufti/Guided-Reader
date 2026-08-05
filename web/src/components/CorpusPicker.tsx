import { useEffect, useState } from "react";
import { loadCorpora, getCorpus, type CorpusSummary } from "@/lib/data";

/**
 * Switch which book is being read.
 *
 * Renders nothing when the deployment serves one corpus: a dropdown with a
 * single option is a control that cannot be used, and it would appear on
 * every screen of a reader whose whole design is about getting out of the way.
 *
 * The corpus lives in the URL rather than in a store, so a switch is a
 * navigation and a link carries the book it points at.
 */
export default function CorpusPicker({
  onSelect,
}: {
  onSelect: (id: string) => void;
}) {
  const [corpora, setCorpora] = useState<CorpusSummary[] | null>(null);
  const current = getCorpus();

  useEffect(() => {
    let live = true;
    loadCorpora()
      .then((c) => live && setCorpora(c))
      // A missing registry is not worth an error state: the reader still works
      // on the corpus it already has.
      .catch(() => live && setCorpora([]));
    return () => {
      live = false;
    };
  }, []);

  if (!corpora || corpora.length < 2) return null;

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="sr-only">Book</span>
      <select
        value={current}
        onChange={(e) => onSelect(e.target.value)}
        className="rounded-md border border-(--color-rule) bg-transparent px-2 py-1
                   text-(--color-ink) focus-visible:outline-2
                   focus-visible:outline-(--color-accent)"
        aria-label="Choose a book"
      >
        {corpora.map((c) => (
          <option key={c.id} value={c.id}>
            {c.titleEn ?? c.id}
            {/* Said plainly rather than hidden behind an icon: a corpus with no
                workbook can show vowelling but not meaning, and a reader
                should know that before choosing it, not after clicking a word
                and finding an empty panel. */}
            {c.hasGlosses ? "" : " — vowelling only"}
          </option>
        ))}
      </select>
    </label>
  );
}
