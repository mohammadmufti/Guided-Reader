import { useEffect, useState } from "react";
import { loadCorpora, getCorpus, type CorpusSummary } from "@/lib/data";

/**
 * Choose which book to read.
 *
 * Renders nothing when the deployment serves one corpus: a dropdown with a
 * single option is a control that cannot be used.
 *
 * SELECTING DOES NOTHING ON ITS OWN. The dropdown holds a local pending value
 * and only the Switch button acts on it. The first version fired on `change`,
 * which had two problems: the reader could not see what they had picked before
 * committing to it, and — worse — the change ran while the current book's
 * index, records and lexicon shards were still loaded and in flight. Words
 * bound against one book were being looked up in another's lexicon, so the
 * panel broke in ways that had nothing to do with the book chosen.
 *
 * Nothing here mutates module state. Switching is the caller's business.
 */
export default function CorpusPicker({
  onSwitch,
}: {
  onSwitch: (id: string) => void;
}) {
  const [corpora, setCorpora] = useState<CorpusSummary[] | null>(null);
  const current = getCorpus();
  const [pending, setPending] = useState(current);

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

  const changed = pending !== current;

  return (
    <div className="flex flex-wrap items-center justify-center gap-2" dir="ltr">
      <label htmlFor="corpus" className="sr-only">
        Book
      </label>
      <select
        id="corpus"
        value={pending}
        onChange={(e) => setPending(e.target.value)}
        className="rounded-md border border-(--color-rule) bg-transparent px-2 py-1
                   text-sm text-(--color-ink) focus-visible:outline-2
                   focus-visible:outline-(--color-accent)"
      >
        {corpora.map((c) => (
          <option key={c.id} value={c.id}>
            {c.titleEn ?? c.id}
            {/* Said plainly rather than hidden behind an icon: a corpus with no
                workbook can show vowelling but not meaning, and a reader should
                know that before choosing it, not after clicking a word and
                finding an empty panel. */}
            {c.hasGlosses ? "" : " — vowelling only"}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={!changed}
        onClick={() => onSwitch(pending)}
        className="rounded-md border border-(--color-rule) px-2.5 py-1 text-sm
                   transition-colors hover:bg-(--color-rule)
                   disabled:cursor-default disabled:opacity-40
                   disabled:hover:bg-transparent"
      >
        Switch
      </button>
    </div>
  );
}
