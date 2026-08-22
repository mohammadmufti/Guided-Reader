import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCorpus, loadIndex, setCorpus } from "@/lib/data";
import type { IndexFile } from "@/types/contracts";

/**
 * What a reader is trusting. Linked from every page.
 *
 * The numbers here are measured, not asserted: the Tier 3 and Tier 4 accuracy
 * figures come from holding out the Bukhari alignment on 55,728 tokens and
 * re-deriving the answer without it. Students deserve to know which words are
 * witnessed and which are guesses.
 */
export function Limitations() {
  // The page describes WHICHEVER BOOK IS OPEN. It used to state al-Tajrid's
  // measured shares whatever the reader was looking at — false for a corpus
  // bound off a different witness, and meaningless for one bound off its own
  // harakat, where three quarters of the words are the edition's own vowelling
  // and nothing was inferred at all.
  const [index, setIndex] = useState<IndexFile | null>(null);
  // From the URL, not from module state: this page can be linked to directly
  // and loaded cold, at which point module state is still the default and the
  // page would describe al-Tajrid whatever book the reader came from.
  const { corpus: corpusParam } = useParams();
  const corpus = corpusParam ?? getCorpus();
  useEffect(() => {
    let live = true;
    setCorpus(corpus);
    loadIndex().then((i) => live && setIndex(i), () => {});
    return () => {
      live = false;
    };
  }, [corpus]);

  const b = index?.binding;
  const rows: [string, string, string][] = b
    ? ([
        ["Vowelled in the source itself", b.source, "not inferred"],
        ["Transferred from a vocalised parent edition", b.aligned, "high"],
        ["One entry matched, and its vowelling was witnessed", b.unique, "not in doubt"],
        ["Inferred — from syntax, or the same phrase elsewhere", b.heuristic, "see below"],
        ["Not in the lexicon at all", b.unbound, "shown bare"],
      ].filter(([, v]) => v != null && (v as number) > 0) as [string, number, string][])
        .map(([a, v, c]) => [a, `${v.toFixed(1)}%`, c])
    : [];

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <p className="mb-6">
        <Link
          to={`/${corpus}/read/1`}
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
        This reader shows the vowelling, root, meaning, case and classical
        dictionary entries for every word. Some of that is witnessed and some
        is inferred, and the difference matters when you are learning. Every
        word panel ends with <em>How this reading was arrived at</em>. Open it.
      </p>

      <section className="mt-8" dir="ltr">
        <h2 className="text-lg">1. The vowelling is not always certain</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Arabic is written without vowels, so a great many words could be read
          more than one way. Where the answer came from is set out below, for
          the book you are reading — not for a different one.
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
            {rows.map(([a, b, c]) => (
              <tr key={a} className="border-b border-(--color-rule)">
                <td className="py-1.5">{a}</td>
                <td className="py-1.5 text-end tabular-nums">{b}</td>
                <td className="py-1.5 text-end tabular-nums">{c}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-sm leading-relaxed text-(--color-ink-muted)">
          Measured on this book, not estimated, and recomputed on every build.
          Words that were inferred rather than witnessed carry a dotted
          underline, and the panel names the tier for each.{" "}
          {b?.uniqueUncertain != null && b.uniqueUncertain > 0 && (
            <>
              Of the words above that matched a single entry,{" "}
              <strong className="text-(--color-ink)">
                {b.uniqueUncertain.toFixed(1)}%
              </strong>{" "}
              of all words matched one whose own vowelling was itself a guess —
              unopposed is not the same as certain.{" "}
            </>
          )}
          The accuracy of the inference rules is measured by hiding the witness
          and re-deriving the answer: on al-Tajrīd that puts the syntax rules at
          97.2% and the most-frequent fallback at 71.3%.
        </p>
      </section>

      <section className="mt-8" dir="ltr">
        <h2 className="text-lg">2. Three dictionaries, and what each is for</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          The panel shows Lane's <em>Lexicon</em> in English, Ibn Manẓūr's{" "}
          <em>Lisān al-ʿArab</em> in Arabic, and — where the root has an article
          — Ibn al-Athīr's <em>al-Nihāya fī Gharīb al-Ḥadīth</em>, a dictionary
          of the words he judged difficult in hadith. Each shows the author's
          own words and his own order. Nothing is summarised and nothing is
          picked out as <em>the</em> definition.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          An earlier version of this reader chose one sense from Lane
          mechanically and printed it as the meaning. Under{" "}
          <strong>ṣalāh</strong> it read{" "}
          <em>“the middle of the back of a human being”</em> — a real sense of
          the root, and useless as a gloss. That is why you are now given the
          entry rather than a sample of it.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Lane and al-Nihāya are keyed to a root. Because hamza is normalised
          when roots are matched, two different roots can share one key —{" "}
          <span lang="ar" dir="rtl" className="arabic">بدأ</span> (to begin) and{" "}
          <span lang="ar" dir="rtl" className="arabic">بدا</span> (to appear).
          Where that happens both articles are shown, spelled as the book
          spells them, and the one your word most likely belongs to is put
          first. It is put first, not alone, because that guess is right about
          fifteen times in sixteen.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          The Arabic dictionaries carry the harakāt their editors printed, which
          is not every word: an editor points what he thinks needs pointing. A
          few articles carry none at all, because their text could not be
          verified against a second copy and we would rather leave those bare
          than guess.
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
        <h2 className="text-lg">4. The case is read, not worked out</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Some words carry a second label beside the part of speech —{" "}
          <span lang="ar" dir="rtl" className="arabic">مرفوع</span>,{" "}
          <span lang="ar" dir="rtl" className="arabic">منصوب</span>,{" "}
          <span lang="ar" dir="rtl" className="arabic">مجرور</span> or{" "}
          <span lang="ar" dir="rtl" className="arabic">مجزوم</span>. It is the
          case of that word <em>in that sentence</em>, so the same word carries
          a different label elsewhere.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          It comes from reading the ending, not from parsing the sentence. The
          work is in knowing whether the ending <em>is</em> a case marker: a
          past-tense verb is <span lang="ar" dir="rtl" className="arabic">مبني</span>{" "}
          on a fatḥa and takes no case, the five verbs are{" "}
          <span lang="ar" dir="rtl" className="arabic">مرفوع</span> by keeping a
          nūn that itself carries a fatḥa, and a sukūn is not a case on a noun.
          Where the ending is bare, no label is shown at all — that is most of
          the reason you will see it on some words and not others.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Checked against the vowelling printed in two editions, on 5,000-plus
          words in each, it is right about 96 times in a hundred. It is least
          reliable on a{" "}
          <span lang="ar" dir="rtl" className="arabic">ممنوع من الصرف</span>{" "}
          noun, whose genitive is marked with a fatḥa and therefore reads as an
          accusative — many of the names in an isnād are of this kind. Treat the
          label as a prompt to check, not as an answer.
        </p>
      </section>

      <section className="mt-8" dir="ltr">
        <h2 className="text-lg">5. The editorial layers are less reliable</h2>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)">
          Where a book is aligned against a vocalised parent edition, only its
          hadith have such a target. Prefaces, headings and editorial additions
          do not, so their vowelling comes from the lower tiers. Additions are
          marked in the text. Some books arrive vowelled and need no alignment
          at all — Shāh Walī Allāh's Forty, and Riyāḍ al-Ṣāliḥīn in Dr Māhir
          Yāsīn al-Faḥl's edition, whose harakāt are the editor's own. The table
          above says which, for the book you have open.
        </p>
      </section>
    </main>
  );
}
