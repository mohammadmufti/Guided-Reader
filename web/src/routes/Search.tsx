import { useEffect, useState } from "react";
import { Link, useSearchParams, useParams } from "react-router-dom";
import type { IndexFile } from "@/types/contracts";
import { loadIndex, setCorpus } from "@/lib/data";
import { search, searchByRoot, knownRoot, type Hit, type Mode } from "@/lib/search";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; hits: Hit[]; terms: string[]; total: number; rootAvailable: string | null }
  | { kind: "error"; message: string };

/**
 * Corpus search.
 *
 * Queries are normalised with the same function the lexicon joins on, so typing
 * `صلاه` finds `صَلَاةٍ`. A student looking a word up does not yet know its
 * vowelling — expecting them to type it would defeat the purpose.
 */
export function Search() {
  // The corpus comes from the route, so a link built here points at the
  // book the reader is actually in.
  const { corpus = "tajrid" } = useParams();
  // AND the data layer must be told, exactly as Reader.tsx tells it. This
  // page read the route for its back-link and never called setCorpus, so a
  // direct navigation to /bulugh/search searched whatever book the data
  // layer last had — al-Tajrid, on a fresh load — under Bulugh's banner.
  setCorpus(corpus);
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const mode: Mode = params.get("mode") === "root" ? "root" : "form";
  const [index, setIndex] = useState<IndexFile | null>(null);
  const [state, setState] = useState<State>({ kind: "idle" });
  const [draft, setDraft] = useState(q);

  useEffect(() => {
    // Re-fetch when the corpus changes: the index carries the record order
    // the postings' sequence numbers mean anything against.
    loadIndex().then(setIndex, (e: Error) =>
      setState({ kind: "error", message: e.message }),
    );
  }, [corpus]);

  useEffect(() => {
    setDraft(q);
    if (!index || !q.trim()) {
      setState({ kind: "idle" });
      return;
    }
    let live = true;
    setState({ kind: "loading" });
    const run = mode === "root" ? searchByRoot : search;
    run(q, index).then(
      (r) =>
        live &&
        setState({
          kind: "done",
          ...r,
          // Offer the other mode only when it would actually find something.
          rootAvailable: mode === "form" ? knownRoot(q) : null,
        }),
      (e: Error) => live && setState({ kind: "error", message: e.message }),
    );
    return () => {
      live = false;
    };
  }, [q, mode, index]);

  return (
    <main className="mx-auto max-w-4xl px-5 py-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-(--color-rule) pb-4">
        <h1 className="text-lg" lang="ar">
          البحث في النص
        </h1>
        <Link
          to={`/${corpus}/read/1`}
          className="rounded-md border border-(--color-rule) px-3 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
          lang="ar"
        >
          العودة إلى النص
        </Link>
      </header>

      {/* Form and root answer different questions: "where does this word
          appear" and "what else comes from this root". Neither is a fallback
          for the other, so both are offered rather than one guessed at. */}
      <div
        role="radiogroup"
        aria-label="نوع البحث"
        className="mb-3 inline-flex rounded-md border border-(--color-rule) p-0.5 text-sm"
      >
        {(["form", "root"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={mode === m}
            onClick={() => setParams({ q: draft, mode: m }, { replace: true })}
            className={`rounded px-3 py-1 transition-colors ${
              mode === m ? "bg-(--color-rule) font-semibold" : "text-(--color-ink-muted)"
            }`}
            lang="ar"
          >
            {m === "form" ? "الصيغة" : "الجذر"}
          </button>
        ))}
      </div>

      <div className="flex items-start gap-2">
        <input
          id="search-input"
          type="search"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") setParams({ q: draft, mode }, { replace: true });
          }}
          placeholder="اكتب كلمة أو أكثر — بالحركات أو بدونها"
          aria-label="ابحث في النص"
          dir="rtl"
          lang="ar"
          className="arabic w-full rounded-md border border-(--color-rule) bg-(--color-raised) px-3 py-2 text-xl"
        />
        <button
          type="button"
          onClick={() => setParams({ q: draft, mode }, { replace: true })}
          className="shrink-0 rounded-md border border-(--color-rule) px-3 py-2.5 text-sm transition-colors hover:bg-(--color-rule)"
          lang="ar"
        >
          ابحث
        </button>
      </div>

      <p className="mt-2 text-xs text-(--color-ink-muted)" lang="ar">
        {mode === "form"
          ? "الحركات غير مطلوبة؛ يُطابَق البحث على الصيغة كما وردت. الكلمات المتعددة تُطابَق معًا."
          : "ابحث بالجذر لتجد كل مشتقاته — «كتب» تجد «مكتوب» و«يكتب». نحو نصف الكلمات لها جذر."}
      </p>

      <div className="mt-7">
        {state.kind === "loading" && (
          <p role="status" className="text-sm text-(--color-ink-muted)" lang="ar">
            جارٍ البحث…
          </p>
        )}
        {state.kind === "error" && (
          <p className="text-sm text-(--color-flag)" dir="ltr">
            {state.message}
          </p>
        )}
        {state.kind === "done" && (
          <Results
            state={state}
            mode={mode}
            corpus={corpus}
            onRootSearch={() => setParams({ q: draft, mode: "root" }, { replace: true })}
          />
        )}
      </div>
    </main>
  );
}

function Results({
  state,
  mode,
  corpus,
  onRootSearch,
}: {
  state: { hits: Hit[]; terms: string[]; total: number; rootAvailable: string | null };
  mode: Mode;
  corpus: string;
  onRootSearch: () => void;
}) {
  const offer = state.rootAvailable && (
    <p className="mb-4 text-sm" dir="rtl" lang="ar">
      <button
        type="button"
        onClick={onRootSearch}
        className="underline underline-offset-4 hover:text-(--color-accent)"
      >
        ابحث بالجذر{" "}
        <span className="arabic tracking-[0.3em]">
          {[...state.rootAvailable].join(" ")}
        </span>{" "}
        لتجد كل المشتقات
      </button>
    </p>
  );

  if (state.total === 0) {
    return (
      <div className="max-w-prose">
        {offer}
        <p lang="ar">لا نتائج.</p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)" lang="ar">
          {mode === "form"
            ? "جرّب كلمة واحدة، أو صيغة أخرى، أو ابحث بالجذر."
            : "لا جذر بهذا الشكل في هذا الكتاب. الجذور ثلاثية غالبًا، مثل «كتب»."}
        </p>
      </div>
    );
  }
  return (
    <>
      {offer}
      <p className="mb-4 text-sm text-(--color-ink-muted)" lang="ar">
        {state.total.toLocaleString("ar-EG")} حديثًا
        {state.hits.length < state.total
          ? ` — تُعرض أول ${state.hits.length.toLocaleString("ar-EG")}`
          : ""}
      </p>
      <ol className="space-y-1">
        {state.hits.map((hit) => (
          <li key={hit.id}>
            <Link
              // Into THIS book. `/hadith/N` is the legacy route from when
              // al-Tajrid was the only text, and it still redirects there —
              // which meant every result of every book's search opened
              // al-Tajrid at whatever hadith happened to share the number.
              to={`/${corpus}/read/${hit.number}`}
              className="block rounded-md border border-transparent px-3 py-3 transition-colors hover:border-(--color-rule) hover:bg-(--color-raised)"
            >
              <div className="mb-1 flex items-baseline gap-3 text-xs text-(--color-ink-muted)">
                <span className="tabular-nums text-base text-(--color-ink)">
                  {hit.number}
                </span>
                {hit.kitab && (
                  <span className="arabic" lang="ar">
                    {hit.kitab}
                  </span>
                )}
              </div>
              <p className="arabic text-xl leading-loose" lang="ar" dir="rtl">
                {hit.snippet.map((part, i) =>
                  part.match ? (
                    <mark
                      key={i}
                      className="bg-(--color-accent-soft) text-(--color-ink)"
                    >
                      {part.text}
                    </mark>
                  ) : (
                    <span key={i}>{part.text}</span>
                  ),
                )}
              </p>
            </Link>
          </li>
        ))}
      </ol>
    </>
  );
}
