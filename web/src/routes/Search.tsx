import { useEffect, useState } from "react";
import { Link, useSearchParams, useParams } from "react-router-dom";
import { setCorpus } from "@/lib/data";
import {
  searchAll,
  searchBook,
  type BookHits,
  type Mode,
  type ScopedResult,
} from "@/lib/search";

export type Scope = "all" | "book";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | ({ kind: "done" } & ScopedResult)
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
  // ALL BOOKS is the default: a reader searching for a hadith rarely knows
  // which collection carries it, and finding it in another book is the
  // answer, not a distraction. `scope=book` narrows to the one they are in.
  const scope: Scope = params.get("scope") === "book" ? "book" : "all";
  const [state, setState] = useState<State>({ kind: "idle" });
  const [draft, setDraft] = useState(q);

  useEffect(() => {
    setDraft(q);
    if (!q.trim()) {
      setState({ kind: "idle" });
      return;
    }
    let live = true;
    setState({ kind: "loading" });
    const run =
      scope === "book"
        ? searchBook(corpus, q, mode)
        : searchAll(corpus, q, mode);
    run.then(
      (r) => live && setState({ kind: "done", ...r }),
      (e: Error) => live && setState({ kind: "error", message: e.message }),
    );
    return () => {
      live = false;
    };
  }, [q, mode, scope, corpus]);

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
      {/* Scope: every book, or this one. Both states are honest — the
          all-books view says per book how much it is not showing. */}
      <div
        role="radiogroup"
        aria-label="نطاق البحث"
        className="mb-3 me-3 inline-flex rounded-md border border-(--color-rule) p-0.5 text-sm"
      >
        {(["all", "book"] as Scope[]).map((sc) => (
          <button
            key={sc}
            type="button"
            role="radio"
            aria-checked={scope === sc}
            onClick={() => setParams({ q, mode, scope: sc }, { replace: true })}
            className={`rounded px-3 py-1 transition-colors ${
              scope === sc
                ? "bg-(--color-rule) text-(--color-ink)"
                : "text-(--color-ink-muted) hover:text-(--color-ink)"
            }`}
            lang="ar"
          >
            {sc === "all" ? "كل الكتب" : "هذا الكتاب"}
          </button>
        ))}
      </div>
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
            if (e.key === "Enter") setParams({ q: draft, mode, scope }, { replace: true });
          }}
          placeholder="اكتب كلمة أو أكثر — بالحركات أو بدونها"
          aria-label="ابحث في النص"
          dir="rtl"
          lang="ar"
          className="arabic w-full rounded-md border border-(--color-rule) bg-(--color-raised) px-3 py-2 text-xl"
        />
        <button
          type="button"
          onClick={() => setParams({ q: draft, mode, scope }, { replace: true })}
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
            scope={scope}
            corpus={corpus}
            onRootSearch={() => setParams({ q: draft, mode: "root", scope }, { replace: true })}
          />
        )}
      </div>
    </main>
  );
}

function Results({
  state,
  mode,
  scope,
  corpus,
  onRootSearch,
}: {
  state: ScopedResult;
  mode: Mode;
  scope: Scope;
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
            : scope === "book"
              ? "لا جذر بهذا الشكل في هذا الكتاب. الجذور ثلاثية غالبًا، مثل «كتب»."
              : "لا جذر بهذا الشكل في هذه الكتب. الجذور ثلاثية غالبًا، مثل «كتب»."}
        </p>
      </div>
    );
  }
  return (
    <>
      {offer}
      <p className="mb-4 text-sm text-(--color-ink-muted)" lang="ar">
        {state.total.toLocaleString("ar-EG")} حديثًا
        {scope === "all" && state.books.length > 1
          ? ` في ${state.books.length.toLocaleString("ar-EG")} كتب`
          : ""}
      </p>
      {state.books.map((book) => (
        <BookSection key={book.corpus} book={book} scope={scope} current={corpus} />
      ))}
    </>
  );
}

function BookSection({
  book,
  scope,
  current,
}: {
  book: BookHits;
  scope: Scope;
  current: string;
}) {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const mode = params.get("mode") ?? "form";
  return (
    <section className="mb-7">
      {/* The book's name heads its results even in single-book scope: a
          reader landing on a shared link should not have to infer which
          text they are looking at. */}
      <h2
        className="mb-2 flex items-baseline gap-3 border-b border-(--color-rule) pb-1 text-base"
        lang="ar"
        dir="rtl"
      >
        <span className="arabic">{book.titleAr ?? book.corpus}</span>
        {book.corpus === current && scope === "all" && (
          <span className="text-xs text-(--color-ink-muted)">الكتاب الحالي</span>
        )}
      </h2>
      <ol className="space-y-1">
        {book.hits.map((hit) => (
          <li key={`${hit.corpus}-${hit.id}`}>
            <Link
              // Into the book the hit lives in — never a default.
              to={`/${hit.corpus}/read/${hit.number}`}
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
      {book.hits.length < book.total && (
        <p className="mt-1 text-sm" lang="ar" dir="rtl">
          <Link
            // The rest of this book's results live in its own single-book
            // scope — which also carries the reader INTO that book's search,
            // back-link and all.
            to={`/${book.corpus}/search?q=${encodeURIComponent(q)}&mode=${mode}&scope=book`}
            className="underline underline-offset-4 hover:text-(--color-accent)"
          >
            {(book.total - book.hits.length).toLocaleString("ar-EG")} نتيجة أخرى
            في هذا الكتاب
          </Link>
        </p>
      )}
    </section>
  );
}
