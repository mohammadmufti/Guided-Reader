import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, Link, useSearchParams } from "react-router-dom";
import type { IndexFile } from "@/types/contracts";
import { loadIndex, loadPage, neighbours, setCorpus, getCorpus, type Page } from "@/lib/data";
import CorpusPicker from "@/components/CorpusPicker";
import { useKeyboard } from "@/hooks/useKeyboard";
import { useSettings } from "@/hooks/useSettings";
import { useDragDismiss } from "@/hooks/useDragDismiss";
import { NavCompact } from "@/components/NavControls";
import AboutBook from "@/components/AboutBook";
import AudioButton from "@/components/AudioButton";
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
  const { number: raw, corpus: corpusParam } = useParams();
  const navigate = useNavigate();

  // The URL is the source of truth for which book this is. Done before the
  // index load below, because `loadIndex` reads the corpus-scoped path.
  const corpus = corpusParam ?? getCorpus();
  setCorpus(corpus);

  /**
   * Leave the page entirely rather than navigate within it.
   *
   * A client-side switch has to invalidate the index, the record cache, the
   * search index and the per-corpus lexicon stats, while requests for all of
   * them may still be in flight — and anything that survives is one book's
   * data answering another book's questions. That is what broke the word
   * panel. A document load discards every bit of it by construction.
   *
   * Switching books is rare and deliberate. Paying a full load for it buys a
   * guarantee that no amount of cache-clearing can.
   */
  function switchCorpus(id: string) {
    window.location.assign(`${import.meta.env.BASE_URL}${id}/read/1`);
  }
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
      if (near.next) navigate(`/${corpus}/read/${near.next}`);
    }, [near.next, navigate]),
    onPrev: useCallback(() => {
      if (near.prev) navigate(`/${corpus}/read/${near.prev}`);
    }, [near.prev, navigate]),
    onFocusJump: useCallback(() => jumpRef.current?.focus(), []),
    onSearch: useCallback(() => navigate(`/${corpus}/search`), [navigate]),
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
        <div className="flex items-start gap-3">
          <div>
            <Link to={`/${corpus}/read/1`} className="arabic block text-xl leading-tight" lang="ar">
              {index.corpus.titleAr}
            </Link>
            <p className="mt-1 text-xs text-(--color-ink-muted)" dir="ltr" lang="en">
              {index.corpus.titleEn} · {index.counts.hadith.toLocaleString()} hadith
            </p>
          </div>
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
            to={`/${corpus}/search`}
            className="rounded-md border border-(--color-rule) px-2.5 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
            lang="ar"
          >
            بحث
          </Link>
          {/* A text with no kitab structure has nothing to browse. Shah Wali
              Allah's Forty is one continuous sequence, and the drawer opened on
              an empty list. Disabled rather than hidden, so the control does
              not move between books. */}
          <button
            type="button"
            onClick={() => setBrowserOpen(true)}
            disabled={index.tree.length === 0}
            title={
              index.tree.length === 0
                ? "This text has no kitab divisions"
                : undefined
            }
            className="rounded-md border border-(--color-rule) px-2.5 py-1.5 text-sm
                       transition-colors hover:bg-(--color-rule)
                       disabled:cursor-default disabled:opacity-40
                       disabled:hover:bg-transparent"
            lang="ar"
          >
            الكتب والأبواب
          </button>
          {/* Navigation beside the browser, which is also navigation. */}
          <NavCompact prevNumber={near.prev} nextNumber={near.next} />
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
            panelStep={settings.panelStep}
            nudgePanel={settings.nudgePanel}
          />
        )}
      </div>

      {status.kind !== "missing" && (
        <footer className="mt-10 border-t border-(--color-rule) pt-4 max-lg:pb-24">
          {/* Choosing a book and asking what this book IS are both rare,
              deliberate acts, but they belong on the row the reader is already
              using — not stacked beneath it, where the eye has to travel past
              the navigation to find them. Info button, picker and Switch sit
              together between the two arrows. */}
          {/* The arrows moved to the header — see NavCompact. What stays here
              is the book picker, which is a deliberate act rather than
              something reached for every few seconds. */}
          <div className="flex items-center justify-center">
            <CorpusPicker
              onSwitch={switchCorpus}
              before={<AboutBook corpus={index.corpus} />}
            />
          </div>

          <p className="mt-3 text-center text-xs text-(--color-ink-muted)" dir="ltr">
            <Link to={`/${corpus}/about`} className="underline underline-offset-2">
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
  panelStep,
  nudgePanel,
}: {
  page: Page;
  selection: Selection | null;
  onSelect: (recordId: string | null, i: number | null) => void;
  index: IndexFile;
  harakat: boolean;
  panelStep: number;
  nudgePanel: (by: 1 | -1) => void;
}) {
  const { main, additions } = page;

  // Back to the top on every new word. The panel keeps its scroll position
  // otherwise, so choosing a word after reading a long Lane article opened the
  // next one halfway down — past the reading, the root and the gloss, which is
  // exactly the part a reader wants first.
  const panelRef = useRef<HTMLElement>(null);

  // Which record is the selection in, and which token?
  const activeRecord =
    selection === null
      ? null
      : selection.recordId === null
        ? main
        : (additions.find((a) => a.id === selection.recordId) ?? null);
  const activeToken = activeRecord?.tokens[selection!.index] ?? null;

  // Keyed on the record AND the index, so moving between two words of the same
  // hadith resets too — not only moving between hadith.
  useEffect(() => {
    panelRef.current?.scrollTo({ top: 0 });
  }, [selection?.recordId, selection?.index, main.id]);
  const indexIn = (recordId: string) =>
    selection !== null && (selection.recordId ?? main.id) === recordId
      ? selection.index
      : null;

  // Pull-down-to-dismiss for the phone sheet. No-op on desktop, where the
  // aside is a static column and the hook never arms.
  const sheet = useDragDismiss({
    active: activeToken !== null,
    onDismiss: () => onSelect(null, null),
  });

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
          // A sticky item stops travelling at the bottom of its grid area, and
          // the area is the row — which ends where the article ends. Padding
          // the ARTICLE lengthens the row so the panel holds through the last
          // screen of a long hadith. It cannot fix the very bottom on its own,
          // because padding grows the row and the document by the same amount;
          // that part is the panel's height, below.
          "lg:order-2 lg:pb-40" +
          (activeToken !== null ? " max-lg:pb-[55dvh]" : "")
        }
      >
        <div className="mb-5 flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-(--color-rule) pb-3">
          {/* Stable hook: tests should not depend on styling classes. */}
          <span data-hadith-number className="text-3xl tabular-nums">
            {main.number}
          </span>
          {/* Where the edition numbers differently from us, say so. Our number
              is an address — a running count that matches no printed copy —
              and a reader who cited it would be citing us. This, with the
              kitab beside it, is the form every external reference uses. */}
          {main.editionNumber != null && (
            <span
              className="text-xs text-(--color-ink-muted)"
              dir="ltr"
              title="The number this edition prints, within its kitab"
            >
              ed. {main.editionNumber}
            </span>
          )}
          {/* recitation, when this hadith has a recording — header row only,
              never inside the matn */}
          <AudioButton tracks={main.audio} />
          {main.kitab && (
            <span className="arabic text-sm" lang="ar">
              {index.corpus.chapterLink ? (
                // sunnah.com has no per-hadith anchor for this text, only a
                // page per book — so the link goes to the kitab, which is
                // where the reader would actually land anyway.
                <a
                  href={index.corpus.chapterLink.url.replace(
                    "{n}",
                    String(main.kitab.index),
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`${main.kitab.titleAr} on ${index.corpus.chapterLink.label} — opens in a new tab`}
                  className="underline decoration-dotted underline-offset-2 transition-colors hover:text-(--color-accent)"
                >
                  {main.kitab.titleAr}
                </a>
              ) : (
                main.kitab.titleAr
              )}
            </span>
          )}
          {/* Ibn Rajab's ziyadat are numbered hadith in their own right, so
              they are the main record rather than something appended below one
              — but they are still another hand's, and say so. */}
          {index.corpus.asideLayer && main.layer === index.corpus.asideLayer && (
            <span
              className="arabic rounded border border-dashed border-(--color-rule) px-1.5 py-0.5 text-[0.7rem] text-(--color-ink-muted)"
              lang="ar"
            >
              {index.corpus.asideNote}
            </span>
          )}
          {main.bab && (
            <span className="arabic text-sm text-(--color-ink-muted)" lang="ar">
              {/* The heading already names the hadith — الحديث الأول — so the
                  link goes on that, not on a bolted-on "sunnah.com 4". The
                  reader clicks the thing they are reading. Same treatment the
                  Muwatta's kitab title gets. */}
              {index.corpus.recordLink && main.recordLinkNumber != null ? (
                <a
                  href={index.corpus.recordLink.url.replace("{n}", String(main.recordLinkNumber))}
                  target="_blank"
                  rel="noopener noreferrer"
                  // SAY WHICH NUMBER IT OPENS. Where a corpus renumbers — the
                  // Shama'il runs to 417 against sunnah.com's 402 — a reader
                  // reading "hadith 330" lands on 317 and reasonably calls that
                  // a mismatch. The link is right; it was silent about being a
                  // different numbering.
                  title={
                    main.recordLinkNumber === main.number
                      ? `${main.bab.titleAr} — ${index.corpus.recordLink.label}`
                      : `${index.corpus.recordLink.label} ${main.recordLinkNumber}` +
                        ` — this edition numbers it ${main.number}`
                  }
                  className="underline decoration-dotted underline-offset-2 transition-colors hover:text-(--color-accent)"
                >
                  {main.bab.titleAr}
                  {main.recordLinkNumber !== main.number && (
                    <span className="ms-1 text-[0.7rem]" dir="ltr">
                      ({index.corpus.recordLink.label} {main.recordLinkNumber})
                    </span>
                  )}
                </a>
              ) : (
                main.bab.titleAr
              )}
            </span>
          )}
          <span className="ms-auto flex gap-3 text-xs text-(--color-ink-muted)" dir="ltr">
            {main.pages.length > 0 && <span className="tabular-nums">{main.pages.join(" · ")}</span>}
            {main.crossRefs.length > 0 && (
              <CrossRefs refs={main.crossRefs} link={index.corpus.referenceLink} />
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

        {/* ONE APPARATUS, not a stack. Several notes on the same hadith belong
            together: a dashed rule between each read as unrelated fragments,
            and the 2.25rem gap pushed the last one off the screen. The rule
            opens the set once and the notes follow, spaced tightly. */}
        {additions.length > 0 && (
          <div className="mt-9 space-y-4 border-t border-dashed border-(--color-rule) pt-5">
            {additions.map((add) => (
          <section key={add.id}>
            {/* Whose addition, and that it is not the original — from the
                corpus, not from this file. It named al-Diya' al-Daghistani for
                every text that has additions, which by now is two. */}
            <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              {index.corpus.asideNote && (
                <p className="text-xs text-(--color-ink-muted)" lang="ar">
                  {index.corpus.asideNote}
                </p>
              )}
              {/* Where the addition is found in Bukhari. al-Zabidi left these
                  out, so the editor wrote no `(بخاري: N)` note for them and
                  the reader had no way through. The reference is ours, not
                  his, and says so. */}
              {add.crossRefs.length > 0 && (
                <span className="text-xs text-(--color-ink-muted)" dir="ltr">
                  <CrossRefs refs={add.crossRefs} link={index.corpus.referenceLink} />
                </span>
              )}
            </div>
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
          </div>
        )}
      </article>

      <aside
        ref={(el) => {
          // Two owners: the phone sheet's drag gesture needs the node, and so
          // does the scroll reset below. A callback ref serves both without
          // either having to know about the other.
          (sheet.ref as React.MutableRefObject<HTMLElement | null>).current = el;
          (panelRef as React.MutableRefObject<HTMLElement | null>).current = el;
        }}
        aria-label="تفاصيل الكلمة"
        // Follows the finger while dragging; springs back (or settles) with a
        // short ease when released. Both are inert on desktop, where offset is
        // always 0 and the transform never moves anything.
        style={{
          transform: sheet.offset ? `translateY(${sheet.offset}px)` : undefined,
          transition: sheet.dragging ? "none" : "transform 0.25s ease-out",
        }}
        className={
          // `lg:relative` rather than `lg:static`: the close button is absolutely
          // positioned in the column's top corner and needs this element as its
          // containing block. On a phone the sheet is already `fixed`, which
          // establishes one.
          "lg:order-1 lg:relative lg:block lg:rounded-lg lg:border lg:border-(--color-rule) " +
          "lg:bg-(--color-raised) lg:p-5 lg:shadow-sm " +
          // STICKY, WITH ITS OWN SCROLL. The panel is a column beside a text
          // that can run for pages: scrolling the page to read the matn used to
          // carry the word panel away with it, and a long Lane article could
          // not be read at all without losing your place in the hadith.
          //
          // `sticky` keeps the top of the panel in view as the page moves;
          // capping its height and letting it scroll internally means a long
          // entry scrolls inside the box. `overscroll-contain` stops that inner
          // scroll from continuing into the page once it reaches the end, which
          // is the behaviour that makes the two feel separate rather than
          // chained. The phone sheet already has all of this.
          // `self-start` matters: a grid item stretches to the row height by
          // default, and a full-height box has nothing to stick to.
          // The cap leaves room for the FOOTER. At full scroll the footer is on
          // screen, and a panel of `100dvh-2rem` plus its 1rem offset is taller
          // than what remains — so the row ran out and the panel was dragged
          // up out of view. Sized to fit beside the footer instead, which is
          // the one place padding could never help.
          "lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100dvh-10rem)] " +
          "lg:overflow-y-auto lg:overscroll-contain " +
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
          <div className="sticky -top-5 z-10 -mx-5 -mt-5 mb-2 border-b border-(--color-rule) bg-(--color-raised) lg:hidden">
            {/* The grabber. It signals that the sheet pulls down — the gesture
                itself (see useDragDismiss) is claimed from anywhere in the
                sheet whenever a downward drag starts at the top of the scroll,
                not only from this pill. The X stays as the explicit, keyboard-
                and screen-reader-reachable way out. */}
            <div className="flex justify-center pt-2 pb-1">
              <span
                aria-hidden="true"
                className="h-1 w-9 rounded-full bg-(--color-ink-muted)/40"
              />
            </div>
            <div className="flex items-center justify-between px-3 pb-2">
              <span className="ps-2 text-xs text-(--color-ink-muted)" lang="ar">
                تفاصيل الكلمة
              </span>
              {/* Same control as the desktop column's. The sheet header has
                  room, and a phone is where a reader is most likely to want
                  the entries larger. */}
              <span className="me-auto flex items-center gap-0.5">
                {([-1, 1] as const).map((by) => (
                  <button
                    key={by}
                    type="button"
                    onClick={() => nudgePanel(by)}
                    aria-label={by === 1 ? "تكبير نص التفاصيل" : "تصغير نص التفاصيل"}
                    disabled={by === 1 ? panelStep >= 5 : panelStep <= 1}
                    className="flex h-9 w-9 items-center justify-center rounded-md
                               border border-(--color-rule) text-sm
                               text-(--color-ink-muted) disabled:opacity-35"
                  >
                    {by === 1 ? "+" : "−"}
                  </button>
                ))}
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
          </div>
        )}
        {/* On a desktop the panel is a column beside the text, so it never
            traps anyone — but there was no way to dismiss it except Escape or
            choosing another word, and neither is discoverable. Same X, same
            hit target, floated at the top of the column. Hidden on a phone,
            where the sheet header above already carries one. */}
        {/* Text size for the panel's own entries, beside the close control.
            Separate from the matn's size: a reader who needs a Lane article
            bigger does not necessarily want the hadith bigger too. The setting
            is stored, so it survives the next word, the next hadith and the
            next book. */}
        {activeToken !== null && (
          <div className="absolute end-12 top-2 z-10 hidden items-center gap-0.5 lg:flex">
            {([-1, 1] as const).map((by) => (
              <button
                key={by}
                type="button"
                onClick={() => nudgePanel(by)}
                aria-label={by === 1 ? "تكبير نص التفاصيل" : "تصغير نص التفاصيل"}
                title={by === 1 ? "Larger panel text" : "Smaller panel text"}
                disabled={by === 1 ? panelStep >= 5 : panelStep <= 1}
                className="flex h-8 w-8 items-center justify-center rounded-md border
                           border-(--color-rule) text-sm text-(--color-ink-muted)
                           transition-colors hover:bg-(--color-rule)
                           hover:text-(--color-ink) disabled:cursor-default
                           disabled:opacity-35 disabled:hover:bg-transparent"
              >
                {by === 1 ? "+" : "−"}
              </button>
            ))}
          </div>
        )}
        {activeToken !== null && (
          <button
            type="button"
            onClick={() => onSelect(null, null)}
            aria-label="إغلاق تفاصيل الكلمة"
            title="Close (Esc)"
            className="absolute end-2 top-2 z-10 hidden h-10 w-10 items-center
                       justify-center rounded-md text-(--color-ink-muted)
                       transition-colors hover:bg-(--color-rule)
                       hover:text-(--color-ink) lg:flex"
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
function CrossRefs({
  refs,
  link,
}: {
  refs: number[];
  link: { label: string; labelAr: string; url: string } | null;
}) {
  if (!link) {
    return <span className="tabular-nums">{refs.join(", ")}</span>;
  }
  // The LABEL is part of the link, not text beside it. A bare underlined
  // number is a small target and reads as decoration; "Bukhari 4508" reads as
  // a place to go. With several numbers the label leads and each number is its
  // own link, since they point at different hadith.
  const single = refs.length === 1;
  return (
    <span className="tabular-nums">
      {!single && `${link.label} `}
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
            {single ? `${link.label} ${n}` : n}
          </a>
        </span>
      ))}
    </span>
  );
}

function MissingState({ number, index }: { number: number; index: IndexFile }) {
  // The corpus comes from the route, so a link built here points at the
  // book the reader is actually in.
  const { corpus = "tajrid" } = useParams();
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
          to={`/${corpus}/read/1`}
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
