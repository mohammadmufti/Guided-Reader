import { useEffect, useState } from "react";
import type {
  CliticSegment,
  IndexFile,
  HadithFile,
  Token,
  PanelEntry,
  ClassicalEntry,
  CorpusStats,
  LaneRoot,
  LaneEntry,
  LaneRun,
  Gloss,
} from "@/types/contracts";
import { loadPanel, type PanelData } from "@/lib/lexicon";
import { loadOccurrences, type Occurrence } from "@/lib/search";
import { Link, useParams } from "react-router-dom";

/**
 * The word panel. Phase 7.
 *
 * Ordered most-useful-first, provenance last. Two rules govern the whole thing:
 *
 *   A section that has nothing to say is not rendered. No empty boxes, no
 *   lonely labels. Where an absence is MEANINGFUL — a particle has no root by
 *   design, not by failure — the panel says why instead of showing a blank.
 *
 *   Nothing is presented as more certain than it is. `classical_sense_sample`
 *   is one sampled definition out of `lane_entry_count`, and for salah that
 *   sample reads "the middle of the back of a human being". It is labelled and
 *   sized accordingly, and never given the position of a definition.
 */

interface Props {
  index: IndexFile;
  record: HadithFile;
  token: Token | null;
  onSelect: (i: number | null) => void;
}

export function WordPanel({ index, record, token, onSelect }: Props) {
  const [data, setData] = useState<PanelData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token?.matchId) {
      setData(null);
      setError(null);
      return;
    }
    let live = true;
    setError(null);
    loadPanel(token.matchId, index).then(
      (d) => live && setData(d),
      (e: Error) => live && setError(e.message),
    );
    return () => {
      live = false;
    };
  }, [token?.matchId, index]);

  if (!token) return <EmptyState record={record} onSelect={onSelect} />;
  if (!token.clickable) {
    return (
      <Section title="لا يوجد مدخل">
        <p className="arabic text-2xl" lang="ar">
          {token.surface}
        </p>
        <Note>
          This form is not in the lexicon — 12 tokens in the whole corpus are
          not, all of them hamza spelling variants.
        </Note>
      </Section>
    );
  }
  if (error) {
    return (
      <Section title="تعذّر التحميل">
        <p className="font-mono text-xs" dir="ltr">
          {error}
        </p>
      </Section>
    );
  }
  if (!data) return <p className="text-sm text-(--color-ink-muted)">…</p>;

  const { entry, classical } = data;
  return (
    // `data-panel` is a readiness signal for the end-to-end tests. Both shards
    // are awaited together in loadPanel, so this appears once and the whole
    // panel is present — waiting on a fixed timeout instead sampled the DOM
    // mid-paint and reported sections as missing when they were not.
    <div className="space-y-6" data-panel="ready">
      <Headword entry={entry} />
      {/* The quick gloss first: it is short, modern, and exists for words no
          workbook covers. The curated gloss follows where there is one, and
          Lane sits below both. A reader who wants depth scrolls; a reader who
          wants the word does not have to. */}
      {/* Two glosses, but only where they say different things AND there are
          two. The BUILD decides sameness — `glossQuick` is null when it
          duplicates the curated one — because comparing them here as well
          meant two implementations of "the same meaning", and they drifted.
          The guard on BOTH existing is this panel's own job, and it was
          missing: on a word with no curated gloss — most words in every
          corpus after al-Tajrid — the first block rendered the quick gloss
          and the `??` fallback then rendered the same quick gloss again, two
          identical "Meaning" sections. The clitic and feature boxes hang off
          whichever gloss is shown, so nothing is lost either way. */}
      {entry.gloss && entry.glossQuick && (
        <Meaning gloss={entry.glossQuick} isName={entry.isName} quick />
      )}
      <Meaning gloss={entry.gloss ?? entry.glossQuick} isName={entry.isName} />
      <RootAndLemma entry={entry} classical={classical} token={token} />
      <Classical entry={entry} classical={classical} lane={data.lane} laneEntry={data.laneEntry} />
      <Divergence entry={entry} />
      <InThisCorpus stats={data.stats} index={index} record={record} token={token} />
      <ProperNoun entry={entry} />
      <Provenance entry={entry} token={token} />
    </div>
  );
}

/* ---------------------------------------------------------------- 1. head */

function Headword({ entry }: { entry: PanelEntry }) {
  return (
    <header>
      <p className="arabic text-4xl leading-tight" lang="ar" dir="rtl">
        {entry.vocalized}
      </p>
      {entry.din_31635 && (
        <p className="mt-1 text-sm italic text-(--color-ink-muted)" dir="ltr">
          {entry.din_31635}
        </p>
      )}
      {entry.pos && (
        <span className="mt-2 inline-block rounded border border-(--color-rule) px-1.5 py-0.5 text-[0.65rem] uppercase tracking-wide text-(--color-ink-muted)">
          {entry.pos.replace(/_/g, " ")}
        </span>
      )}
    </header>
  );
}

/* ------------------------------------------------------------- 2. meaning */

function Meaning({
  gloss,
  isName,
  quick = false,
}: {
  gloss: Gloss | null;
  isName: boolean;
  /** True when a curated gloss follows this one, so the two can be told apart. */
  quick?: boolean;
}) {
  if (!gloss || gloss.senses.length === 0) return null;
  const chain = [...gloss.before, ...gloss.after];
  // A name is a person; the dictionary sense belongs to the common word that
  // shares its spelling. Presenting "suitors" as the MEANING of al-Khaṭṭāb
  // taught an error — reframed, it teaches the homograph, which is useful.
  return (
    <Section
      title="المعنى"
      subtitle={
        isName ? "As a common word" : quick ? "Meaning — at a glance" : "Meaning"
      }
    >
      {isName && (
        <p className="mb-1.5 text-[0.7rem] text-(--color-ink-muted)" dir="ltr">
          This is a proper noun — a name. The common word spelled the same way
          means:
        </p>
      )}
      <ul className="flex flex-wrap gap-x-2 gap-y-1" dir="ltr">
        {gloss.senses.map((s, i) => (
          <li key={s} className="panel-scaled">
            {s}
            {i < gloss.senses.length - 1 && (
              <span className="text-(--color-ink-muted)">,</span>
            )}
          </li>
        ))}
      </ul>
      {(chain.length > 0 || gloss.features) && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5" dir="ltr">
          {chain.map((slot, i) => (
            <span
              key={i}
              className="rounded bg-(--color-rule) px-1.5 py-0.5 text-[0.7rem] text-(--color-ink-muted)"
              title="attached clitic"
            >
              {slot.senses.join(" / ")}
            </span>
          ))}
          {gloss.features?.map((f) => (
            <span
              key={f}
              className="rounded border border-(--color-rule) px-1.5 py-0.5 text-[0.7rem] text-(--color-ink-muted)"
              title="morphological feature"
            >
              {f}
            </span>
          ))}
        </div>
      )}
    </Section>
  );
}

/* -------------------------------------------------------- 3. root & lemma */

function RootAndLemma({
  entry,
  classical,
  token,
}: {
  entry: PanelEntry;
  classical: ClassicalEntry | null;
  token: Token;
}) {
  // Precedence: the workbook, then the analysers run directly, then recovery
  // from the corpus itself. Whichever answers, the panel says which.
  //
  // One measured exception (2026-07-30): where BOTH analyser stacks agree on
  // a root that contradicts the workbook, the agreed root is shown — Lane
  // sides with the analysers 532:419 in workbook disputes, and two
  // convergent engines beat one derivative source. entry.root remains the
  // workbook's claim; `rootPreferAnalysed` carries the choice.
  const ana = entry.analysed;
  const rec = entry.recovered;
  // Context beats the workbook only where it was measured to: a hollow root
  // against a geminate one. `كُنْتُ` is كون, not كنن.
  const root =
    token.contextRoot ??
    (entry.rootPreferAnalysed ? ana?.root ?? null : null) ??
    entry.root ??
    ana?.root ??
    rec?.root ??
    null;
  // Vocalised first. `lemma` is the bare join key, and a lemma shown without
  // its harakat is the one thing this reader exists to avoid — سمع tells a
  // student nothing about whether it is samiʿa or sammaʿa.
  const lemma =
    token.contextLemma ??
    entry.lemmaVocalised ??
    (entry.lemma && !entry.morphSuspect ? entry.lemma : (ana?.lemma ?? rec?.lemma ?? null));
  const source: "context" | "analysers-agree" | "workbook" | "analyser" | "corpus" | null =
    token.contextRoot
      ? "context"
      : entry.rootPreferAnalysed && ana?.root
        ? "analysers-agree"
        : entry.root
          ? "workbook"
          : ana?.root
            ? "analyser"
            : rec?.root
              ? "corpus"
              : null;

  return (
    <Section title="الجذر واللفظ" subtitle="Root and lemma">
      <WordBreakdown surface={token.surface} segments={entry.segments} />
      {root ? (
        <div className="flex items-baseline gap-3">
          <span className="arabic text-2xl tracking-[0.35em]" lang="ar" dir="rtl">
            {[...root].join(" ")}
          </span>
          {classical?.nLemmas != null && !rec && (
            <span className="text-xs text-(--color-ink-muted)">
              {classical.nLemmas} lemma{classical.nLemmas === 1 ? "" : "s"} in this corpus
            </span>
          )}
        </div>
      ) : entry.morphSuspect ? (
        // A null root here does NOT mean "absent by design". The analysis kept a
        // clitic and lost the stem, and the stem is not attested on its own
        // anywhere in this corpus either, so there is nothing to recover from.
        <Note>
          The morphological analysis of this form is unreliable — it identified
          only a prefix and lost the stem — and the stem does not occur on its own
          anywhere in this book, so the root could not be recovered. It is
          missing, not absent: this word has one. The meaning above is derived
          from the whole form and is unaffected.
        </Note>
      ) : (
        <Note>
          No root — particles, pronouns and proper nouns do not have one. About
          48% of tokens in this corpus are in that position by design.
        </Note>
      )}

      {lemma && (
        // Flex with a real gap, not an inline margin. The two spans have
        // OPPOSITE directions — Arabic rtl, transliteration ltr — inside an rtl
        // document, so `ms-2` resolved to the side the transliteration was not
        // on and the two ran into each other. A flex row places them by box
        // rather than by text flow, and the gap holds whichever way they read.
        <p className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="arabic panel-scaled-ar" lang="ar" dir="rtl">
            {lemma}
          </span>
          {!rec && entry.lemma_din && (
            <span
              className="text-sm italic text-(--color-ink-muted)"
              dir="ltr"
              style={{ unicodeBidi: "isolate" }}
            >
              {entry.lemma_din}
            </span>
          )}
        </p>
      )}
      {entry.verb && (
        // Both citation forms. One does not fix the scale — samiʿa could be
        // yasmaʿu, yasmiʿu or yasmuʿu — so the pair is how the wazn is stated,
        // and the pattern beside it states it outright.
        <p className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="arabic panel-scaled-ar" lang="ar" dir="rtl">
            {entry.verb.perfect} — {entry.verb.imperfect}
          </span>
          {entry.verb.pattern && (
            <span
              className="arabic text-sm text-(--color-ink-muted)"
              lang="ar"
              dir="rtl"
              title="The scale (wazn) of the imperfect"
            >
              {entry.verb.pattern}
            </span>
          )}
        </p>
      )}

      {source === "context" && (
        <p className="mt-2 text-[0.7rem] leading-relaxed text-(--color-ink-muted)" dir="ltr">
          The source data gives a doubled root here, which is the shape a hollow
          verb is mistaken for when its weak middle radical vanishes from the
          written form. The root above comes from analysing this word in its
          sentence instead. Adjudicated against Lane, context is right in every
          case of this kind that could be decided.
        </p>
      )}
      {source === "analyser" && (
        <p className="mt-2 text-[0.7rem] leading-relaxed text-(--color-ink-muted)" dir="ltr">
          The source data lost this word&rsquo;s stem and recorded only a prefix.
          The root and lemma above come from running morphological analysers
          directly — CAMeL Tools and the qalsadi/arramooz dictionary chain.
          {ana?.rootBasis === "agree" &&
            " Both analyser stacks name this root independently."}
          {ana?.rootBasis === "camel" && (
            <>
              {" "}The two stacks disagree; shown is CAMeL&rsquo;s reading —
              where they differ, Lane&rsquo;s Lexicon sides with CAMeL about
              2.5 to 1 — and the other stack&rsquo;s root is listed below.
            </>
          )}
          {ana?.rootBasis === "camel-only" &&
            " Only CAMeL analysed this form; the dictionary chain had no answer."}
          {ana?.rootBasis?.startsWith("arramooz-") &&
            " CAMeL had no reading here; the dictionary chain answered alone."}
          {ana?.rootAlternatives.length ? (
            <>
              {" "}Also on offer:{" "}
              <span className="arabic" lang="ar" dir="rtl">
                {ana.rootAlternatives.join("، ")}
              </span>
              .
              {ana.rootBasis === "arramooz-vocalised" &&
                " The word's own vowels decided among them."}
              {ana.rootBasis === "arramooz-majority" &&
                " The root shown is the one more dictionary entries give."}
              {ana.rootBasis === "arramooz-lane" &&
                " The root shown is the candidate that has an entry in Lane."}
              {ana.rootBasis === "arramooz-unresolved" && (
                <span className="text-(--color-flag)">
                  {" "}Nothing decides between them — the root shown may be the
                  wrong one.
                </span>
              )}
            </>
          ) : null}
        </p>
      )}

      {source === "analysers-agree" && entry.root && (
        <p className="mt-2 text-[0.7rem] leading-relaxed text-(--color-ink-muted)" dir="ltr">
          The source data roots this word{" "}
          <span className="arabic" lang="ar" dir="rtl">{entry.root}</span>, but
          both analyser stacks — CAMeL Tools and the qalsadi/arramooz chain —
          independently give the root shown above. In disputes like this,
          Lane&rsquo;s Lexicon sides with the analysers slightly more often
          than not (532 to 419, measured at adoption), and two convergent
          engines outweigh one derived source.
        </p>
      )}

      {entry.rootDisputed && source === "workbook" && (
        <p className="mt-2 text-[0.7rem] leading-relaxed text-(--color-flag)" dir="ltr">
          The source data and the analysers give different roots for this word
          {ana?.root ? (
            <>
              {" "}— the analysers read it as{" "}
              <span className="arabic" lang="ar" dir="rtl">{ana.root}</span>
            </>
          ) : null}
          . The one shown is the source data&rsquo;s. Neither is authoritative:
          they differ on about 10% of comparable forms, and where they do,
          Lane&rsquo;s Lexicon splits nearly evenly between them.
        </p>
      )}

      {source === "corpus" && rec && (
        // Provenance in place, not buried. The supplied analysis is wrong for
        // this form; what is shown was reconstructed from the corpus, and the
        // reader should be able to check it.
        <p className="mt-2 text-[0.7rem] leading-relaxed text-(--color-ink-muted)" dir="ltr">
          The supplied analysis lost this word&rsquo;s stem and recorded only a
          prefix. The root and lemma above were recovered by stripping the
          affixes and looking up{" "}
          <span className="arabic" lang="ar" dir="rtl">
            {rec.viaStem}
          </span>
          , which occurs elsewhere in this book. That method is {rec.accuracy}%
          accurate on forms whose root is already known.
        </p>
      )}
    </Section>
  );
}

/* ---------------------------------------------------------- 4. classical  */

const SIGLA: Record<string, string> = {
  K: "al-Qāmūs al-Muḥīṭ", S: "al-Ṣiḥāḥ", M: "al-Muḥkam", Msb: "al-Miṣbāḥ al-Munīr",
  TA: "Tāj al-ʿArūs", Mgh: "al-Mughrib", L: "Lisān al-ʿArab", A: "Asās al-Balāgha",
};

/** One inline run of a Lane sense. */
function Run({ run }: { run: LaneRun }) {
  if (run.t === "ar")
    return (
      <span className="arabic" lang="ar" dir="rtl">
        {run.v}
      </span>
    );
  if (run.t === "i") return <em>{run.v}</em>;
  if (run.t === "trop") return <em title="figurative usage">{run.v}</em>;
  if (run.t === "ref")
    return (
      <span className="arabic" lang="ar" dir="rtl" title="cross-reference">
        {run.v}
      </span>
    );
  return <>{run.v}</>;
}

/**
 * The classical apparatus.
 *
 * v1 showed ONE sense per root, sampled mechanically from the workbook. For
 * صلو that sample read "the middle of the back of a human being" — which is a
 * real sense of the root, is in fact sense A2 of this very entry, and is a
 * catastrophic thing to hand a student as the meaning of salah.
 *
 * This shows Lane's actual entry for the word: صَلَاةٌ has six senses, opening
 * "Prayer, supplication, or petition". The other entries under the root are
 * listed but not expanded, because a root averages 15.8 of them.
 *
 * Nothing is selected on the reader's behalf. The senses are Lane's, in Lane's
 * order, with Lane's own labels.
 */
function Classical({
  entry,
  classical,
  lane,
  laneEntry,
}: {
  entry: PanelEntry;
  classical: ClassicalEntry | null;
  lane: LaneRoot | null;
  laneEntry: LaneEntry | null;
}) {
  const [expanded, setExpanded] = useState(false);
  // Collapsed by default. See the headword button below.
  const [entryOpen, setEntryOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const keywords = classical?.keywords ?? [];
  if (!lane && keywords.length === 0) return null;

  const shown = laneEntry ?? lane?.entries[0] ?? null;
  const senses = shown?.senses ?? [];
  const visible = expanded ? senses : senses.slice(0, 2);
  const others = (lane?.entries ?? []).filter((e) => e.nodeid !== shown?.nodeid);

  return (
    <Section subtitle="Lane's Lexicon" testId="lane">
      {keywords.length > 0 && (
        <ul className="mb-3 flex flex-wrap gap-1.5" dir="ltr">
          {keywords.map((k) => (
            <li key={k} className="rounded-full bg-(--color-rule) px-2 py-0.5 text-xs">
              {k}
            </li>
          ))}
        </ul>
      )}

      {shown && (
        <>
          {/* The headword line IS the control. Collapsed by default: a Lane
              article can run to a dozen senses, and this panel will carry more
              than one dictionary before long — a reader should choose what to
              open rather than scroll past everything.

              The control stays ABOVE what it reveals, like the "other entries"
              toggle below, so the thing you pressed does not move. */}
          <button
            type="button"
            onClick={() => setEntryOpen((v) => !v)}
            aria-expanded={entryOpen}
            className="mb-2 flex w-full items-baseline gap-2 text-start"
          >
            <span
              className="text-(--color-ink-muted) transition-transform"
              aria-hidden="true"
              style={{ transform: entryOpen ? "rotate(90deg)" : "none" }}
            >
              ›
            </span>
            <span className="arabic text-xl" lang="ar" dir="rtl">
              {shown.headword}
            </span>
            {/* Underlined like every other disclosure control in this panel
                — an unadorned phrase did not read as pressable, and this is
                the one control readers most need to find. */}
            <span
              className="text-[0.65rem] text-(--color-ink-muted) underline underline-offset-2"
              dir="ltr"
            >
              {laneEntry ? "this word's own entry" : "first entry under this root"}
              {lane?.page ? ` · p. ${lane.page}` : ""}
            </span>
          </button>

          {/* The headword again, OUTSIDE the button, because text inside a
              button cannot be selected: a reader who wants to copy Lane's
              citation form — which is not always the form they tapped in
              the matn (نَوَاهُ for نَوَى) — had nothing to copy. Shown only
              once the entry is open, beside what it heads. */}
          <div
            className={`mb-1 select-text arabic text-lg ${entryOpen ? "" : "hidden"}`}
            lang="ar"
            dir="rtl"
          >
            {shown.headword}
          </div>

          <ol className={`space-y-2 ${entryOpen ? "" : "hidden"}`} dir="ltr">
            {visible.map((sense, i) => (
              <li key={i} className="panel-scaled leading-relaxed">
                {sense.label && (
                  <span className="me-1.5 rounded bg-(--color-rule) px-1 text-[0.65rem] text-(--color-ink-muted)">
                    {sense.label}
                  </span>
                )}
                {sense.runs.map((run, j) => (
                  <Run key={j} run={run} />
                ))}
              </li>
            ))}
          </ol>

          {entryOpen && senses.length > 2 && (
            <button
              type="button"
              onClick={() => setExpanded((e) => !e)}
              aria-expanded={expanded}
              className="mt-2 text-xs text-(--color-ink-muted) underline underline-offset-2"
              dir="ltr"
            >
              {expanded
                ? "Show fewer senses"
                : `Show all ${senses.length} Lane senses of this entry`}
            </button>
          )}
        </>
      )}

      {others.length > 0 && (
        <div className="mt-3 border-t border-(--color-rule) pt-2">
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            aria-expanded={showAll}
            className="text-xs text-(--color-ink-muted) underline underline-offset-2"
            dir="ltr"
          >
            {showAll ? "Hide" : `${others.length} other Lane entries under `}
            {!showAll && (
              <span className="arabic" lang="ar" dir="rtl">
                {entry.lane_root}
              </span>
            )}
          </button>
          {showAll && (
            <ul className="mt-2 space-y-1.5">
              {others.map((e) => (
                <li key={e.nodeid} className="text-sm">
                  <span className="arabic text-lg" lang="ar" dir="rtl">
                    {e.headword}
                  </span>
                  <span className="ms-2 text-xs text-(--color-ink-muted)" dir="ltr">
                    {e.senses.length} sense{e.senses.length === 1 ? "" : "s"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="mt-3 text-[0.65rem] leading-relaxed text-(--color-ink-muted)" dir="ltr">
        Lane's own senses and ordering. Letters in brackets are his sources —{" "}
        {Object.entries(SIGLA)
          .slice(0, 4)
          .map(([k, v]) => `${k} = ${v}`)
          .join(", ")}.
      </p>
    </Section>
  );
}

/* --------------------------------------------------------- 5. divergence  */

const DIVERGENCE_COPY: Record<
  string,
  { title: string; blurb: string }
> = {
  curated: {
    title: "Literal and technical senses differ",
    blurb: "The everyday sense of the root and the sense this word carries as a term of art are not the same.",
  },
  divergent: {
    title: "Classical and modern senses diverge",
    blurb: "Reading this with its modern meaning will mislead you.",
  },
  developed_sense: {
    title: "The modern sense grew out of the classical one",
    blurb: "Related, but the modern reading has travelled from where it started.",
  },
  aligned: {
    title: "Classical and modern senses agree",
    blurb: "The modern meaning is safe here.",
  },
};

function Divergence({ entry }: { entry: PanelEntry }) {
  const key = entry.divergence ?? "";
  const copy = DIVERGENCE_COPY[key];
  // not_applicable / no_classical_entry / no_msa_gloss: say nothing at all.
  if (!copy) return null;
  const hasPair = Boolean(entry.literal_sense || entry.technical_sense);

  if (!hasPair) {
    return (
      <p className="text-xs leading-relaxed text-(--color-ink-muted)" dir="ltr">
        <span className="font-medium text-(--color-ink)">{copy.title}.</span> {copy.blurb}
      </p>
    );
  }

  // THE SIGNATURE.
  //
  // Set as facing columns divided by a gutter rule, the way a critical edition
  // sets variant readings against each other — because that is what this is:
  // two readings of the same word, one everyday and one technical. The rule's
  // WEIGHT carries `overlap_score`. A hairline means the two senses nearly
  // coincide; a heavy rule means they have pulled apart. The brief forbids
  // printing the bare number, and rightly — 0.14 tells a student nothing, but a
  // thick rule between two columns tells them the gap is wide.
  //
  // No colour, no icon, no tinted box. This is the one place the design raises
  // its voice and it does it with type and rule alone.
  const distance = entry.overlap_score == null ? 0.5 : 1 - entry.overlap_score;
  const ruleWidth = Math.max(1, Math.round(distance * 6));

  return (
    <section className="border-y border-(--color-rule) py-4" aria-label="Literal and technical senses">
      <h3 className="text-sm font-semibold" dir="ltr">
        {copy.title}
      </h3>
      <p className="mt-0.5 text-xs leading-relaxed text-(--color-ink-muted)" dir="ltr">
        {copy.blurb}
      </p>

      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] gap-x-4" dir="ltr">
        <div>
          <p className="text-[0.65rem] uppercase tracking-widest text-(--color-ink-muted)">
            Literal
          </p>
          <p className="mt-1 text-sm leading-snug">{entry.literal_sense ?? "—"}</p>
        </div>
        <div
          aria-hidden="true"
          className="justify-self-center bg-(--color-ink)"
          style={{ width: ruleWidth }}
        />
        <div>
          <p className="text-[0.65rem] uppercase tracking-widest text-(--color-ink-muted)">
            Technical{entry.domain ? ` · ${entry.domain}` : ""}
          </p>
          <p className="mt-1 text-sm leading-snug">{entry.technical_sense ?? "—"}</p>
        </div>
      </div>

      <p className="mt-3 text-[0.65rem] leading-relaxed text-(--color-ink-muted)" dir="ltr">
        {distance > 0.66
          ? "The rule between them is heavy: these senses have travelled a long way apart."
          : distance > 0.33
            ? "The rule between them shows how far the two senses have separated."
            : "A thin rule: the two senses still overlap closely."}
      </p>
    </section>
  );
}

/* ------------------------------------------------------ 6. in this corpus */

/**
 * Every other place this spelling occurs, fetched on request.
 *
 * The panel turns from a dictionary entry into a concordance: a reader stops
 * asking what a word means and starts asking how this author uses it. The index
 * that makes it possible is 310 KB, so it is loaded when asked for rather than
 * with every panel — the count is already known from `doc_freq`, so the offer
 * is free until taken.
 */
function Occurrences({
  stats,
  index,
  record,
  token,
}: {
  stats: CorpusStats;
  index: IndexFile;
  record: HadithFile;
  token: Token;
}) {
  // The corpus comes from the route, so a link built here points at the
  // book the reader is actually in.
  const { corpus = "tajrid" } = useParams();
  const [state, setState] = useState<
    { kind: "idle" } | { kind: "loading" } | { kind: "done"; total: number; shown: Occurrence[] }
  >({ kind: "idle" });

  useEffect(() => setState({ kind: "idle" }), [token.matchId, record.id]);

  const elsewhere = stats.boundFreq - 1;
  if (elsewhere < 1) return null;

  if (state.kind === "idle") {
    return (
      <button
        type="button"
        onClick={() => {
          setState({ kind: "loading" });
          // The search key is the first half of the identifier — no need to
          // ship it twice on 22,464 entries.
          loadOccurrences(token.matchId ?? "", index, {
            id: record.id,
            index: token.i,
          }).then(
            (r) => setState({ kind: "done", ...r }),
            () => setState({ kind: "done", total: 0, shown: [] }),
          );
        }}
        className="mt-2 text-xs text-(--color-ink-muted) underline underline-offset-2"
        dir="ltr"
      >
        Show the other {elsewhere.toLocaleString()} occurrence
        {elsewhere === 1 ? "" : "s"} of this reading
      </button>
    );
  }
  if (state.kind === "loading") {
    return (
      <p className="mt-2 text-xs text-(--color-ink-muted)" role="status" lang="ar">
        …
      </p>
    );
  }
  return (
    <div className="mt-3 border-t border-(--color-rule) pt-2">
      <p className="mb-2 text-[0.65rem] uppercase tracking-wide text-(--color-ink-muted)" dir="ltr">
        Elsewhere{state.total > state.shown.length ? ` — first ${state.shown.length} of ${state.total}` : ""}
      </p>
      <ol className="space-y-2">
        {state.shown.filter((o) => o.number !== null).map((o) => (
          <li key={`${o.id}:${o.index}`}>
            <Link
              to={`/${corpus}/read/${o.number}?w=${o.target}`}
              className="block rounded px-1 py-0.5 transition-colors hover:bg-(--color-rule)"
            >
              <span className="me-2 text-xs tabular-nums text-(--color-ink-muted)">
                {o.number}
              </span>
              <span className="arabic text-base leading-loose" lang="ar" dir="rtl">
                {o.snippet.map((part, i) =>
                  part.match ? (
                    <mark key={i} className="bg-(--color-accent-soft) text-(--color-ink)">
                      {part.text}
                    </mark>
                  ) : (
                    <span key={i}>{part.text}</span>
                  ),
                )}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}

function InThisCorpus({
  stats,
  index,
  record,
  token,
}: {
  stats: CorpusStats | null;
  index: IndexFile;
  record: HadithFile;
  token: Token;
}) {
  if (!stats) return null;
  const layers = (stats.layers ?? "")
    .split(",")
    .map((p) => p.split(":"))
    .filter((p) => p.length === 2)
    .map(([name, n]) => ({ name: (name ?? "").trim(), n: Number(n) }));

  const framing =
    stats.boundFreq === 1
      ? "A hapax — it occurs exactly once in the whole book."
      : stats.rank <= 50
        ? stats.cum_pct
          ? `Among the 50 most frequent forms; the top ${stats.rank} account for ${(stats.cum_pct * 100).toFixed(0)}% of all tokens.`
          : "Among the 50 most frequent forms in this book."
        : stats.boundFreq >= 100
          ? "A common form you will meet repeatedly."
          : null;

  return (
    <Section title="في هذا الكتاب" subtitle="In this corpus">
      <p className="text-sm" dir="ltr">
        <strong className="tabular-nums">{stats.boundFreq.toLocaleString()}</strong>{" "}
        occurrence{stats.boundFreq === 1 ? "" : "s"} across{" "}
        <strong className="tabular-nums">{stats.boundDocFreq.toLocaleString()}</strong> of{" "}
        {index.counts.hadith.toLocaleString()} records · rank{" "}
        <span className="tabular-nums">{stats.rank.toLocaleString()}</span>
      </p>
      {framing && (
        <p className="mt-1 text-xs text-(--color-ink-muted)" dir="ltr">
          {framing}
        </p>
      )}
      {layers.length > 0 && (
        <p className="mt-2 text-xs text-(--color-ink-muted)" dir="ltr">
          {layers.map((l) => `${l.n} in ${l.name.replace("heading_", "")}`).join(" · ")}
        </p>
      )}
      <Occurrences stats={stats} index={index} record={record} token={token} />
    </Section>
  );
}

/* ------------------------------------------------------- 7. proper nouns  */

function ProperNoun({ entry }: { entry: PanelEntry }) {
  if (!entry.isName) return null;
  return (
    <section className="rounded-md border border-(--color-rule) p-3">
      <h3 className="text-sm font-semibold" dir="ltr">
        A person, not a word
      </h3>
      <p className="mt-0.5 text-xs text-(--color-ink-muted)" dir="ltr">
        This form is in the gazetteer of names mined from the isnād attribution
        patterns. Where the lexical apparatus above is thin, that is why — a name
        has no root and no dictionary sense.
      </p>
    </section>
  );
}

/* ---------------------------------------------------------- 8. provenance */

const BINDING_COPY: Record<string, string> = {
  // Tier 0. The strongest provenance there is: nothing was inferred.
  source:
    "This vowelling is printed in the source text itself. It was not inferred or transferred from another edition.",
  unique: "Only one lexicon entry matches this spelling.",
  // Deliberately does NOT name Bukhārī: the witness edition is per-corpus, and
  // hardcoding one book's name here is the same mistake `bukhariRefs` was.
  aligned:
    "The vowelling was transferred from the matching word in a fully vocalised parent edition.",
  heuristic: "The vowelling was inferred, not witnessed.",
  unbound: "No lexicon entry.",
};

const UNIQUE_COPY = {
  high: "Only one lexicon entry matches this spelling, and its vowelling comes from a witnessed reading.",
  // Unopposed is not the same as certain. 1,551 tokens are here.
  medium:
    "Only one lexicon entry matches this spelling, but that entry's own vowelling was the source data's most frequent guess rather than a witnessed reading. The consonants are not in doubt; the vowels are.",
} as const;

function Provenance({ entry, token }: { entry: PanelEntry; token: Token }) {
  const [open, setOpen] = useState(false);
  const shaky =
    entry.pos_agreement === "disagree" ||
    token.confidence === "low" ||
    (token.binding === "unique" && token.confidence === "medium") ||
    entry.reviewFlagged ||
    entry.morphSuspect;

  return (
    <section className="border-t border-(--color-rule) pt-3">
      {entry.morphSuspect && (
        <p className="mb-2 text-xs text-(--color-flag)" dir="ltr">
          {entry.recovered
            ? "The source data's part of speech describes a prefix, not this word. The root and lemma shown were reconstructed from the corpus."
            : "The source data's part of speech and lemma describe a prefix, not this word."}
        </p>
      )}
      {entry.pos_agreement === "disagree" && !entry.morphSuspect && (
        // The workbook's own flag for hollow and irregular verbs, where its
        // root extraction is known to go wrong. Say so plainly, above the fold.
        <p className="mb-2 text-xs text-(--color-flag)" dir="ltr">
          The root shown above may be wrong. This form is flagged where the two
          morphological analysers disagree, which happens on hollow and irregular
          verbs.
        </p>
      )}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between text-xs text-(--color-ink-muted)"
        dir="ltr"
      >
        <span>
          How this reading was arrived at
          {shaky && !open ? " · worth checking" : ""}
        </span>
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <dl className="mt-2 space-y-1.5 text-xs" dir="ltr">
          <Row label="Binding">
            {token.binding} · {token.confidence} confidence
          </Row>
          <p className="text-(--color-ink-muted)">
            {token.binding === "unique"
              ? UNIQUE_COPY[token.confidence === "medium" ? "medium" : "high"]
              : BINDING_COPY[token.binding]}
          </p>
          {entry.voc_source && <Row label="Vowelling source">{entry.voc_source}</Row>}
          {entry.morph_confidence && (
            <Row label="Morphology">{entry.morph_confidence.replace(/_/g, " ")}</Row>
          )}
          {entry.pos_agreement && (
            <Row label="Analyser agreement">{entry.pos_agreement}</Row>
          )}
          {entry.reviewFlagged && (
            <p className="text-(--color-ink-muted)">
              The workbook could not settle this form's vowelling from context and
              fell back to its most frequent reading.
            </p>
          )}
        </dl>
      )}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    // `min-w-0` on the value: a flex item defaults to min-width:auto, which
    // refuses to shrink below its content and pushes it out of the panel.
    // `overflow-wrap: anywhere` because these values have no spaces to break
    // at — `aligned:945,lexicon_unique:78` is one unbreakable run to the line
    // breaker, and normal word-wrapping leaves it hanging over the edge.
    <div className="flex gap-2">
      <dt className="w-36 shrink-0 text-(--color-ink-muted)">{label}</dt>
      <dd className="min-w-0 [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

/* ------------------------------------------------------------ empty state */

function EmptyState({
  record,
  onSelect,
}: {
  record: HadithFile;
  onSelect: (i: number | null) => void;
}) {
  // Offer the hadith's rarest word — the one most worth looking up.
  const suggestion = record.tokens.filter((t) => t.clickable).at(-1);
  const rarest = record.tokens
    .filter((t) => t.clickable)
    .reduce<Token | undefined>((best, t) => (best ? best : t), suggestion);

  return (
    <div className="space-y-3">
      <p className="text-sm" dir="ltr">
        Select any word to see how it works.
      </p>
      <p className="text-xs leading-relaxed text-(--color-ink-muted)" dir="ltr">
        You get its vowelling and transliteration, what it means in Modern
        Standard Arabic, its root and lemma, what the classical dictionaries say,
        and — where the two differ — the gap between them.
      </p>
      {rarest && (
        <button
          type="button"
          onClick={() => onSelect(rarest.i)}
          className="rounded-md border border-(--color-rule) px-3 py-1.5 text-sm transition-colors hover:bg-(--color-rule)/40"
        >
          <span className="arabic" lang="ar">
            {rarest.surface}
          </span>
          <span className="ms-2 text-xs text-(--color-ink-muted)" dir="ltr">
            try this one
          </span>
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- primitives */

function Section({
  title,
  subtitle,
  children,
  testId,
}: {
  // Optional: a section whose source has no Arabic name of its own carries the
  // English one alone. Lane's Lexicon is one, and there will be more.
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Stable hook for the browser gates. */
  testId?: string;
}) {
  return (
    <section data-section={testId}>
      <h3 className="mb-1.5 flex items-baseline gap-2">
        {title && (
          <span className="text-xs text-(--color-ink-muted)" lang="ar">
            {title}
          </span>
        )}
        {subtitle && (
          <span className="text-[0.65rem] uppercase tracking-wide text-(--color-ink-muted)" dir="ltr">
            {subtitle}
          </span>
        )}
      </h3>
      {children}
    </section>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs leading-relaxed text-(--color-ink-muted)" dir="ltr">
      {children}
    </p>
  );
}

/**
 * The word, split into what is attached and what is the word.
 *
 * Colours by KIND ONLY — prefix, stem, attached pronoun. Not by which prefix:
 * the analyser labels the types, and gets them wrong in plain cases, reading
 * the emphatic lam of `إِنَّ الأمرَ لَيَسيرٌ` as a preposition. A colour that
 * says "something is attached here" is true; one that says "this is the lam of
 * purpose" would sometimes not be.
 *
 * The letters are the SOURCE's. `segments` carries counts, never text, so this
 * splits the word already on screen rather than substituting the analyser's
 * spelling. Marks travel with the letter they sit on.
 */
function WordBreakdown({
  surface,
  segments,
}: {
  surface: string;
  segments: CliticSegment[] | null;
}) {
  if (!segments || segments.length < 2) return null;

  const MARK = /[\u064b-\u0652\u0670\u0640]/;
  const chunks: { kind: string; text: string }[] = [];
  let i = 0;
  for (const seg of segments) {
    let taken = 0;
    let text = "";
    while (i < surface.length) {
      const ch = surface[i] as string;
      const isMark = MARK.test(ch);
      if (!isMark && taken >= seg.letters) break;
      if (!isMark) taken += 1;
      text += ch;
      i += 1;
    }
    chunks.push({ kind: seg.kind, text });
  }
  // Anything left over means the counts and the word disagreed. Say nothing
  // rather than colour the word wrongly.
  if (i < surface.length) return null;

  const style: Record<string, string> = {
    prefix: "text-(--color-accent)",
    stem: "text-(--color-ink)",
    enclitic: "text-(--color-accent)",
  };
  const label: Record<string, string> = {
    prefix: "prefix",
    stem: "the word",
    enclitic: "attached pronoun",
  };

  return (
    <div className="mb-3">
      <p className="arabic text-2xl leading-loose" lang="ar" dir="rtl">
        {chunks.map((c, n) => (
          <span
            key={n}
            className={
              (style[c.kind] ?? "") +
              (c.kind === "stem"
                ? ""
                : " underline decoration-dotted underline-offset-4")
            }
            title={label[c.kind] ?? c.kind}
          >
            {c.text}
          </span>
        ))}
      </p>
      <p className="text-xs text-(--color-ink-muted)" dir="ltr">
        {chunks
          .map((c) => label[c.kind] ?? c.kind)
          .filter((v, n, a) => a.indexOf(v) === n)
          .join(" · ")}
      </p>
    </div>
  );
}

