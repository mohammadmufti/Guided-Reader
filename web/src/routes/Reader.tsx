import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, Link, useSearchParams } from "react-router-dom";
import type { IndexFile } from "@/types/contracts";
import { loadIndex, loadPage, neighbours, type Page } from "@/lib/data";
import { useKeyboard } from "@/hooks/useKeyboard";
import { useSettings } from "@/hooks/useSettings";
import { NavControls } from "@/components/NavControls";
import { JumpTo } from "@/components/JumpTo";
import { BookBrowser } from "@/components/BookBrowser";
import { ReadingControls } from "@/components/ReadingControls";
import { ReadingPane } from "@/components/ReadingPane";
import { WordPanel } from "@/components/WordPanel";

type Status =
  | { kind: "loading" }
  | { kind: "ready"; page: Page }
  | { kind: "missing"; number: number }
  | { kind: "error"; message: string };

export function Reader() {
  const { number: raw } = useParams();
  const navigate = useNavigate();
  const [index, setIndex] = useState<IndexFile | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [browserOpen, setBrowserOpen] = useState(false);
  const [online, setOnline] = useState(() => navigator.onLine);
  const [params, setParams] = useSearchParams();
  const jumpRef = useRef<HTMLInputElement>(null);
  const settings = useSettings();

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // A page can hold more than one record: the hadith, plus any zawa'id
  // additions that follow it. So a selection has to say WHICH record, not just
  // which token — token 5 of the addition is not token 5 of the hadith.
  //
  //   ?w=5                  token 5 of the hadith        (unchanged, links keep working)
  //   ?w=zawaid-00008:3     token 3 of that addition
  const selectedRaw = params.get("w");
  const selection = parseSelection(selectedRaw);

  // Selection lives in the URL so a link carries it, but with `replace` — a
  // reader clicking through fifteen words should not have to press Back fifteen
  // times to leave the hadith.
  const select = useCallback(
    (recordId: string | null, i: number | null) => {
      const next = new URLSearchParams(params);
      if (i === null) next.delete("w");
      else next.set("w", recordId ? `${recordId}:${i}` : String(i));
      setParams(next, { replace: true });
    },
    [params, setParams],
  );
  const clearSelection = useCallback(() => select(null, null), [select]);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    loadIndex().then(setIndex, (e: Error) =>
      setStatus({ kind: "error", message: e.message }),
    );
  }, [reloadKey]);

  useEffect(() => {
    if (!index) return;
    const n = Number(raw);
    if (!raw || !/^\d+$/.test(raw) || !Number.isFinite(n)) {
      setStatus({ kind: "missing", number: NaN });
      return;
    }
    let live = true;
    loadPage(n).then(
      (page) => {
        if (!live) return;
        setStatus(page ? { kind: "ready", page } : { kind: "missing", number: n });
        window.scrollTo({ top: 0 });
      },
      (e: Error) => live && setStatus({ kind: "error", message: e.message }),
    );
    return () => {
      live = false;
    };
  }, [raw, index, reloadKey]);

  const page = status.kind === "ready" ? status.page : null;
  const current = raw && /^\d+$/.test(raw) ? Number(raw) : null;
  const near =
    index && current !== null ? neighbours(index, current) : { prev: null, next: null };

  useKeyboard({
    onNext: useCallback(() => {
      if (near.next) navigate(`/hadith/${near.next}`);
    }, [near.next, navigate]),
    onPrev: useCallback(() => {
      if (near.prev) navigate(`/hadith/${near.prev}`);
    }, [near.prev, navigate]),
    onFocusJump: useCallback(() => jumpRef.current?.focus(), []),
    onSearch: useCallback(() => navigate("/search"), [navigate]),
    onEscape: useCallback(() => {
      setBrowserOpen(false);
      clearSelection();
    }, [clearSelection]),
  });

  if (status.kind === "error") {
    return (
      <Shell>
        <ErrorState
          message={status.message}
          online={online}
          onRetry={() => {
            setStatus({ kind: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      </Shell>
    );
  }
  if (!index) return <Shell>{null}</Shell>;

  return (
    <Shell>
      {!online && (
        <p
          role="status"
          className="mb-4 rounded-md border border-(--color-flag) px-3 py-2 text-xs text-(--color-flag)"
          lang="ar"
        >
          لا يوجد اتصال. ما حُمِّل من قبل ما زال متاحًا.
        </p>
      )}

      <header className="mb-7 flex flex-wrap items-start justify-between gap-x-6 gap-y-4 border-b border-(--color-rule) pb-4">
        <div>
          <Link to="/hadith/1" className="arabic block text-xl leading-tight" lang="ar">
            {index.corpus.titleAr}
          </Link>
          <p className="mt-1 text-xs text-(--color-ink-muted)" dir="ltr" lang="en">
            {index.corpus.titleEn} · {index.counts.hadith.toLocaleString()} hadith
          </p>
        </div>
        <div className="flex flex-wrap items-start gap-3">
          <ReadingControls
            step={settings.step}
            harakat={settings.harakat}
            theme={settings.theme}
            face={settings.face}
            onStep={settings.setStep}
            onHarakat={settings.toggleHarakat}
            onTheme={settings.cycleTheme}
            onFace={settings.cycleFace}
          />
          <Link
            to="/search"
            className="rounded-md border border-(--color-rule) px-2.5 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
            lang="ar"
          >
            بحث
          </Link>
          <button
            type="button"
            onClick={() => setBrowserOpen(true)}
            className="rounded-md border border-(--color-rule) px-2.5 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
            lang="ar"
          >
            الكتب والأبواب
          </button>
          <JumpTo ref={jumpRef} index={index} />
        </div>
      </header>

      <div style={{ minHeight: "60vh" }}>
        {status.kind === "loading" && (
          <p className="text-sm text-(--color-ink-muted)" role="status" lang="ar">
            جارٍ التحميل…
          </p>
        )}
        {status.kind === "missing" && <MissingState number={status.number} index={index} />}
        {page && (
          <PageView
            page={page}
            selection={selection}
            onSelect={select}
            index={index}
            harakat={settings.harakat}
          />
        )}
      </div>

      {status.kind !== "missing" && (
        <footer className="mt-10 border-t border-(--color-rule) pt-4 max-lg:pb-24">
          <NavControls prevNumber={near.prev} nextNumber={near.next} />
          <p className="mt-3 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-center text-xs text-(--color-ink-muted)" dir="ltr">
            <span>← next · → previous · / jump · Esc close</span>
            <Link to="/about" className="underline underline-offset-2">
              What you are trusting
            </Link>
          </p>
        </footer>
      )}

      <BookBrowser
        index={index}
        open={browserOpen}
        onClose={() => setBrowserOpen(false)}
        currentKitab={page?.main.kitab?.index ?? null}
      />
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto max-w-6xl px-5 py-7">{children}</main>;
}

/**
 * Requirement 3: the Arabic occupies the LEFT of the page, the apparatus the
 * right. Those are physical sides and the document is RTL, so in a two-track
 * grid the NARROW track is declared first — track 1 is the rightmost when the
 * writing direction is right-to-left.
 *
 * Below `lg` the panel is a bottom sheet rather than a column stacked under the
 * fold, so selecting a word produces feedback you can actually see. Record
 * context sits above the text instead of inside the panel, so it stays visible
 * on narrow screens whether or not a word is selected.
 */
interface Selection {
  /** null means the page's main record. */
  recordId: string | null;
  index: number;
}

function parseSelection(raw: string | null): Selection | null {
  if (raw === null) return null;
  if (/^\d+$/.test(raw)) return { recordId: null, index: Number(raw) };
  const at = raw.lastIndexOf(":");
  if (at <= 0) return null;
  const i = raw.slice(at + 1);
  if (!/^\d+$/.test(i)) return null;
  return { recordId: raw.slice(0, at), index: Number(i) };
}

function PageView({
  page,
  selection,
  onSelect,
  index,
  harakat,
}: {
  page: Page;
  selection: Selection | null;
  onSelect: (recordId: string | null, i: number | null) => void;
  index: IndexFile;
  harakat: boolean;
}) {
  const { main, additions } = page;

  // Which record is the selection in, and which token?
  const activeRecord =
    selection === null
      ? null
      : selection.recordId === null
        ? main
        : (additions.find((a) => a.id === selection.recordId) ?? null);
  const activeToken = activeRecord?.tokens[selection!.index] ?? null;
  const indexIn = (recordId: string) =>
    selection !== null && (selection.recordId ?? main.id) === recordId
      ? selection.index
      : null;
  return (
    <div className="grid gap-10 lg:grid-cols-[21rem_minmax(0,1fr)]">
      {/* While the sheet is open on a phone, the article grows matching blank
          space at its foot — otherwise the text behind the sheet is
          unreachable and a short hadith leaves nothing to grab, so reading
          and word-tapping become mutually exclusive (reader-reported).
          55dvh = the 50dvh sheet plus room for the last line to sit clear
          above it. Desktop is untouched: the panel is a side column there. */}
      <article
        className={
          "lg:order-2" + (activeToken !== null ? " max-lg:pb-[55dvh]" : "")
        }
      >
        <div className="mb-5 flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-(--color-rule) pb-3">
          {/* Stable hook: tests should not depend on styling classes. */}
          <span data-hadith-number className="text-3xl tabular-nums">
            {main.number}
          </span>
          {main.kitab && (
            <span className="arabic text-sm" lang="ar">
              {main.kitab.titleAr}
            </span>
          )}
          {main.bab && (
            <span className="arabic text-sm text-(--color-ink-muted)" lang="ar">
              {main.bab.titleAr}
            </span>
          )}
          <span className="ms-auto flex gap-3 text-xs text-(--color-ink-muted)" dir="ltr">
            {main.pages.length > 0 && <span className="tabular-nums">{main.pages.join(" · ")}</span>}
            {main.bukhariRefs.length > 0 && (
              <BukhariRefs refs={main.bukhariRefs} link={index.corpus.referenceLink} />
            )}
          </span>
        </div>

        {main.numbersCovered.length > 1 && (
          <p className="mb-3 text-xs text-(--color-ink-muted)" lang="ar">
            هذا السجل يشمل الحديثين {main.numbersCovered.join(" و")}؛ جاءا في سطر واحد في الأصل.
          </p>
        )}

        <ReadingPane
          record={main}
          selected={indexIn(main.id)}
          onSelect={(i) => onSelect(null, i)}
          harakat={harakat}
        />

        {additions.map((add) => (
          <section key={add.id} className="mt-9 border-t border-dashed border-(--color-rule) pt-5">
            <p className="mb-3 text-xs text-(--color-ink-muted)" lang="ar">
              زيادة الضياء الداغستاني — ليست من أصل الزبيدي
            </p>
            {/* A zawa'id addition is an unnumbered hadith, not decoration.
                Its words were left inert in Phase 5, before the panel existed,
                and stayed that way — 6,063 tokens a reader could see but not
                look up. */}
            <ReadingPane
              record={add}
              selected={indexIn(add.id)}
              onSelect={(i) => onSelect(add.id, i)}
              harakat={harakat}
              muted
            />
          </section>
        ))}
      </article>

      <aside
        aria-label="تفاصيل الكلمة"
        className={
          "lg:order-1 lg:static lg:block lg:rounded-lg lg:border lg:border-(--color-rule) " +
          "lg:bg-(--color-raised) lg:p-5 lg:shadow-sm " +
          // Half the screen, no more: at 68vh the sheet owned the phone and the
          // text became a sliver. dvh, not vh, so the browser chrome
          // collapsing does not push the sheet over the cap.
          "max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:z-40 max-lg:max-h-[50dvh] " +
          "max-lg:overflow-y-auto max-lg:overscroll-contain max-lg:rounded-t-xl " +
          "max-lg:border-t max-lg:border-(--color-rule) max-lg:bg-(--color-raised) " +
          "max-lg:p-5 max-lg:shadow-2xl " +
          (activeToken === null ? "max-lg:hidden" : "")
        }
      >
        {/* On a phone the panel is a sheet, and since Lane entries landed it is
            a tall one. A close control at the top of a scrolling column scrolls
            out of reach, which is how a dismissible sheet becomes a trap. Pin it
            with `sticky`, give it a 40px hit target, and mark it with an X
            rather than a word so it reads as "close" at a glance. */}
        {activeToken !== null && (
          <div className="sticky -top-5 z-10 -mx-5 -mt-5 mb-2 flex items-center justify-between border-b border-(--color-rule) bg-(--color-raised) px-3 py-2 lg:hidden">
            <span className="ps-2 text-xs text-(--color-ink-muted)" lang="ar">
              تفاصيل الكلمة
            </span>
            <button
              type="button"
              onClick={() => onSelect(null, null)}
              aria-label="إغلاق تفاصيل الكلمة"
              className="flex h-10 w-10 items-center justify-center rounded-md transition-colors hover:bg-(--color-rule)"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
        )}
        <WordPanel
          index={index}
          record={main}
          token={activeToken}
          onSelect={(i) => onSelect(null, i)}
        />
      </aside>
    </div>
  );
}

/**
 * The editorial cross-reference, as links.
 *
 * al-Tajrid is an abridgement: it strips the isnad and keeps the matn, and the
 * `(بخاري: N)` note is the editor pointing at the full hadith. Making that
 * clickable gives a reader the chain, the surrounding chapter and an English
 * translation — none of which this project holds or redistributes.
 *
 * The URL template comes from the corpus config, not from here, because what a
 * text cites is a property of the text.
 */
function BukhariRefs({
  refs,
  link,
}: {
  refs: number[];
  link: { label: string; labelAr: string; url: string } | null;
}) {
  if (!link) {
    return <span className="tabular-nums">{refs.join(", ")}</span>;
  }
  return (
    <span className="tabular-nums">
      {link.label}{" "}
      {refs.map((n, i) => (
        <span key={n}>
          {i > 0 && ", "}
          <a
            href={link.url.replace("{n}", String(n))}
            target="_blank"
            rel="noopener noreferrer"
            title={`${link.label} ${n} — opens sunnah.com in a new tab`}
            aria-label={`${link.label} ${n}, opens in a new tab`}
            className="underline decoration-dotted underline-offset-2 transition-colors hover:text-(--color-accent)"
          >
            {n}
          </a>
        </span>
      ))}
    </span>
  );
}

function MissingState({ number, index }: { number: number; index: IndexFile }) {
  const max = Number(
    Object.keys(index.navigation.numberIndex).sort((a, b) => Number(b) - Number(a))[0],
  );
  return (
    <div className="max-w-prose">
      <h1 className="text-xl" lang="ar">
        لا يوجد حديث بهذا الرقم
      </h1>
      <p className="mt-2 text-sm text-(--color-ink-muted)" lang="ar">
        {Number.isNaN(number)
          ? "الرقم المطلوب غير صالح."
          : `الحديث رقم ${number} ليس في هذه النسخة.`}{" "}
        النطاق المتاح من ١ إلى {max}.
      </p>
      <p className="mt-4">
        <Link
          to="/hadith/1"
          className="rounded-md border border-(--color-rule) px-3 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
          lang="ar"
        >
          ابدأ من الحديث الأول
        </Link>
      </p>
    </div>
  );
}

function ErrorState({
  message,
  online,
  onRetry,
}: {
  message: string;
  online: boolean;
  onRetry: () => void;
}) {
  return (
    <div className="max-w-prose">
      <h1 className="text-xl" lang="ar">
        {online ? "تعذّر تحميل النص" : "لا يوجد اتصال بالإنترنت"}
      </h1>
      <p className="mt-2 text-sm text-(--color-ink-muted)" lang="ar">
        {online
          ? "فشل تحميل أحد ملفات البيانات."
          : "تحقّق من الاتصال ثم أعد المحاولة."}
      </p>
      <p className="mt-2 font-mono text-xs text-(--color-ink-muted)" dir="ltr">
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-md border border-(--color-rule) px-3 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
        lang="ar"
      >
        أعد المحاولة
      </button>
    </div>
  );
}
