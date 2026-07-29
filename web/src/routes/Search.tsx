import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { IndexFile } from "@/types/contracts";
import { loadIndex } from "@/lib/data";
import { search, type Hit } from "@/lib/search";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; hits: Hit[]; terms: string[]; total: number }
  | { kind: "error"; message: string };

/**
 * Corpus search.
 *
 * Queries are normalised with the same function the lexicon joins on, so typing
 * `صلاه` finds `صَلَاةٍ`. A student looking a word up does not yet know its
 * vowelling — expecting them to type it would defeat the purpose.
 */
export function Search() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const [index, setIndex] = useState<IndexFile | null>(null);
  const [state, setState] = useState<State>({ kind: "idle" });
  const [draft, setDraft] = useState(q);

  useEffect(() => {
    loadIndex().then(setIndex, (e: Error) =>
      setState({ kind: "error", message: e.message }),
    );
  }, []);

  useEffect(() => {
    setDraft(q);
    if (!index || !q.trim()) {
      setState({ kind: "idle" });
      return;
    }
    let live = true;
    setState({ kind: "loading" });
    search(q, index).then(
      (r) => live && setState({ kind: "done", ...r }),
      (e: Error) => live && setState({ kind: "error", message: e.message }),
    );
    return () => {
      live = false;
    };
  }, [q, index]);

  return (
    <main className="mx-auto max-w-4xl px-5 py-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-(--color-rule) pb-4">
        <h1 className="text-lg" lang="ar">
          البحث في النص
        </h1>
        <Link
          to="/hadith/1"
          className="rounded-md border border-(--color-rule) px-3 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
          lang="ar"
        >
          العودة إلى النص
        </Link>
      </header>

      <div className="flex items-start gap-2">
        <input
          id="search-input"
          type="search"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") setParams({ q: draft }, { replace: true });
          }}
          placeholder="اكتب كلمة أو أكثر — بالحركات أو بدونها"
          aria-label="ابحث في النص"
          dir="rtl"
          lang="ar"
          className="arabic w-full rounded-md border border-(--color-rule) bg-(--color-raised) px-3 py-2 text-xl"
        />
        <button
          type="button"
          onClick={() => setParams({ q: draft }, { replace: true })}
          className="shrink-0 rounded-md border border-(--color-rule) px-3 py-2.5 text-sm transition-colors hover:bg-(--color-rule)"
          lang="ar"
        >
          ابحث
        </button>
      </div>

      <p className="mt-2 text-xs text-(--color-ink-muted)" lang="ar">
        الحركات غير مطلوبة؛ يُطابَق البحث على الصيغة المجرَّدة. الكلمات المتعددة
        تُطابَق معًا.
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
        {state.kind === "done" && <Results state={state} />}
      </div>
    </main>
  );
}

function Results({
  state,
}: {
  state: { hits: Hit[]; terms: string[]; total: number };
}) {
  if (state.total === 0) {
    return (
      <div className="max-w-prose">
        <p lang="ar">لا نتائج.</p>
        <p className="mt-2 text-sm leading-relaxed text-(--color-ink-muted)" lang="ar">
          جرّب كلمة واحدة، أو صيغة أخرى للكلمة. البحث يطابق الصيغة كما وردت، لا
          الجذر — فـ«كتب» لا تجد «مكتوب».
        </p>
      </div>
    );
  }
  return (
    <>
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
              to={`/hadith/${hit.number}`}
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
