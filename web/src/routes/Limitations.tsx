import { Link } from "react-router-dom";

/**
 * What a reader is trusting. Linked from every page.
 *
 * The numbers here are measured, not asserted: the Tier 3 and Tier 4 accuracy
 * figures come from holding out the Bukhari alignment on 55,728 tokens and
 * re-deriving the answer without it. Students deserve to know which words are
 * witnessed and which are guesses.
 */
export function Limitations() {
  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <p className="mb-6">
        <Link
          to="/hadith/1"
          className="rounded-md border border-(--color-rule) px-3 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
          lang="ar"
        >
          العودة إلى النص
        </Link>
      </p>

      <h1 className="text-2xl" dir="ltr">
        What you are trusting
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-(--color-ink-muted)" dir="ltr">
        This reader shows the vowelling, root and meaning of every word. Some of
        that is witnessed and some is inferred, and the difference matters when
        you are learning. Every word panel ends with{" "}
        <em>How this reading was arrived at</em>. Open it.
      </p>

      <section className="mt-8" dir="ltr">
        <h2 className="text-lg">1. The vowelling is not always certain</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Half the words in this book have a spelling that could be read more
          than one way — 49.7% of tokens, on 2,631 ambiguous spellings.
        </p>
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-(--color-rule) text-start text-xs uppercase tracking-wide text-(--color-ink-muted)">
              <th className="py-1.5 text-start font-normal">How it was arrived at</th>
              <th className="py-1.5 text-end font-normal">Share</th>
              <th className="py-1.5 text-end font-normal">Accuracy</th>
            </tr>
          </thead>
          <tbody>
            {[
              ["One entry matched, and its vowelling was witnessed", "49.0%", "not in doubt"],
              ["Transferred from a vocalised Bukhārī edition", "45.8%", "high"],
              ["Inferred from the same phrase elsewhere", "2.1%", "97.2%"],
              ["One entry matched, but its vowelling was itself a guess", "1.2%", "vowels uncertain"],
              ["Most frequent reading — a guess", "1.8%", "70.1%"],
              ["Not in the lexicon at all", "12 tokens", "—"],
            ].map(([a, b, c]) => (
              <tr key={a} className="border-b border-(--color-rule)">
                <td className="py-1.5">{a}</td>
                <td className="py-1.5 text-end tabular-nums">{b}</td>
                <td className="py-1.5 text-end tabular-nums">{c}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-sm leading-relaxed text-(--color-ink-muted)">
          The two accuracy figures are measured, not estimated, and are pinned
          by the test suite. Roughly{" "}
          <strong className="text-(--color-ink)">one word in every 56</strong> is
          a guess that is probably right and might not be. Those words carry a
          dotted underline.
        </p>
      </section>

      <section className="mt-8" dir="ltr">
        <h2 className="text-lg">2. The classical definitions are sampled</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          The keyword cluster is reliable. The single definition beneath it is
          one sample from Lane's <em>Lexicon</em>, picked mechanically, and often
          not the sense the word carries here. Under <strong>ṣalāh</strong> the
          sample reads <em>“the middle of the back of a human being.”</em> That is
          a real sense of the root and useless as a gloss. Where a curated
          literal/technical pair exists — 11.8% of tokens — trust that instead.
        </p>
      </section>

      <section className="mt-8" dir="ltr">
        <h2 className="text-lg">3. Some roots are wrong, some were reconstructed</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Root extraction fails predictably on hollow and irregular verbs. Where
          the analysers disagree the panel warns that the root may be wrong.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          409 forms lost their stem entirely — the source analysis kept a prefix
          and discarded the word. For 146 the root was reconstructed by stripping
          the affixes and looking the remainder up elsewhere in this same book, a
          method that is 98% accurate on forms whose root is already known. The
          panel says when it has been used. The other 263 stay blank and say the
          root is <em>missing, not absent</em>.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Separately, about 48% of tokens have no root at all — particles,
          pronouns and proper nouns do not have one. That is an answer, not a gap.
        </p>
      </section>

      <section className="mt-8" dir="ltr">
        <h2 className="text-lg">4. The editorial layers are less reliable</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          The hadith text is aligned against a vocalised Bukhārī. The preface,
          the headings, and al-Ḍiyāʾ al-Dāghistānī's 88 added hadith have no such
          target, so their vowelling comes from the lower tiers. Additions are
          marked in the text.
        </p>
      </section>
    </main>
  );
}
