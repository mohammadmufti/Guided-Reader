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
  before,
}: {
  onSwitch: (id: string) => void;
  /** Rendered immediately left of the select, inside the centred group. */
  before?: React.ReactNode;
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
    // `min-w-0` and `max-w-full` throughout: a <select> sizes itself to its
    // WIDEST OPTION, so the longest book title silently becomes a floor on
    // the page width. That floor moves with the font — this measured 0px of
    // overflow at 380px locally and 29px on CI, which has different Arabic
    // font fallbacks. Constraining the box means the text is clipped
    // instead, and the page can never be pushed wider than the viewport by
    // a name.
    // One centred row. The info button is passed in as `before` so it sits
    // immediately left of the select rather than pinned to the page edge, and
    // the whole group centres together between the previous/next controls.
    <div className="flex min-w-0 items-center justify-center gap-2" dir="ltr">
      {before}
      <label htmlFor="corpus" className="sr-only">
        Book
      </label>
      <select
        id="corpus"
        value={pending}
        onChange={(e) => setPending(e.target.value)}
        className="min-w-0 max-w-full flex-shrink rounded-md border border-(--color-rule)
                   bg-transparent px-2 py-1 text-sm text-(--color-ink)
                   focus-visible:outline-2 focus-visible:outline-(--color-accent)"
      >
        {corpora.map((c) => (
          // The title, and nothing else. A picker names things; what a book
          // IS belongs in its info panel, which every corpus now has.
          <option key={c.id} value={c.id}>
            {c.titleEn ?? c.id}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={!changed}
        onClick={() => onSwitch(pending)}
        className="rounded-md border border-(--color-rule) px-2.5
                   py-1 text-sm transition-colors hover:bg-(--color-rule)
                   disabled:cursor-default disabled:opacity-40
                   disabled:hover:bg-transparent"
      >
        Switch
      </button>
    </div>
  );
}
