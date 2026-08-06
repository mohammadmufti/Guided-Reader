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
    // `min-w-0` and `max-w-full` throughout: a <select> sizes itself to its
    // WIDEST OPTION, so the longest book title silently becomes a floor on
    // the page width. That floor moves with the font — this measured 0px of
    // overflow at 380px locally and 29px on CI, which has different Arabic
    // font fallbacks. Constraining the box means the text is clipped
    // instead, and the page can never be pushed wider than the viewport by
    // a name.
    // Three columns, the outer two equal: the select sits in the middle one
    // and is therefore centred on the page regardless of how wide the Switch
    // button is. Centring a flex row containing both put the select half the
    // button's width to the left — 37px off the midpoint of the previous/next
    // controls it is supposed to line up with.
    <div
      className="grid w-full min-w-0 grid-cols-[1fr_auto_1fr] items-center gap-2"
      dir="ltr"
    >
      <span aria-hidden="true" />
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
        // justify-self-start keeps it hard against the select rather than
        // floating to the far edge of its column.
        onClick={() => onSwitch(pending)}
        className="justify-self-start rounded-md border border-(--color-rule) px-2.5
                   py-1 text-sm transition-colors hover:bg-(--color-rule)
                   disabled:cursor-default disabled:opacity-40
                   disabled:hover:bg-transparent"
      >
        Switch
      </button>
    </div>
  );
}
