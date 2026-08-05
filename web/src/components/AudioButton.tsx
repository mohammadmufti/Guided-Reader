import { useEffect, useRef, useState } from "react";

/**
 * The recitation play/pause button, shown in the hadith header row — never
 * inside the matn. Renders NOTHING when the record carries no audioFile; the
 * build decides which records have audio (matched by hadith number against
 * the corpus config's declared release assets, or local files), so
 * presence here is data, not a probe.
 *
 * The file is not fetched until the reader presses play (`preload="none"`),
 * and navigating to another hadith unmounts the component, which stops
 * playback — two hadith never sound at once.
 *
 * WHY THERE IS A FALLBACK LINK. The recitation is hosted as a GitHub release
 * asset, and GitHub serves those as:
 *
 *     content-type: application/octet-stream
 *     content-disposition: attachment
 *     (no access-control-allow-origin)
 *
 * Desktop browsers sniff the container and play it regardless. iOS Safari
 * does not: it requires a real media MIME type and refuses the element
 * outright. Nothing in this component can fix that — the absent CORS header
 * also rules out fetching the bytes and re-wrapping them in a Blob with the
 * right type, which would otherwise be the way around it.
 *
 * So on the platforms where playback cannot work, this at least SAYS so and
 * offers the file directly, instead of a button that does nothing when
 * pressed. The real fix is to rehost with `audio/mpeg`.
 */
export default function AudioButton({ url }: { url: string | null }) {
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  const ref = useRef<HTMLAudioElement>(null);

  // Unmount (navigation) stops the sound.
  useEffect(() => () => ref.current?.pause(), []);

  if (!url) return null;
  // Absolute (release-hosted asset) plays as-is; a bare filename is a local
  // file under the app's own /audio/ and needs the base path prepended.
  const src = /^https?:\/\//.test(url) ? url : `${import.meta.env.BASE_URL}audio/${url}`;

  return (
    <span className="inline-flex items-center">
      <audio
        ref={ref}
        src={src}
        preload="none"
        onPlay={() => {
          setPlaying(true);
          setFailed(false);
        }}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        // Fires when the browser rejects the source itself, which is the iOS
        // case: no exception is thrown at the call site, the element simply
        // errors. Without this the press produced no sound and no sign.
        onError={() => {
          setPlaying(false);
          setFailed(true);
        }}
      />
      <button
        type="button"
        data-audio-button
        onClick={() => {
          const el = ref.current;
          if (!el) return;
          if (!el.paused) {
            el.pause();
            return;
          }
          // Called synchronously in the gesture — awaiting anything first
          // would spend the user activation and iOS would refuse on those
          // grounds instead, hiding the real reason.
          const started = el.play();
          if (started) started.catch(() => setFailed(true));
        }}
        aria-label={playing ? "إيقاف التلاوة مؤقتًا" : "تشغيل تلاوة هذا الحديث"}
        aria-pressed={playing}
        title={playing ? "Pause recitation" : "Play recitation"}
        className="flex h-8 w-8 items-center justify-center rounded-full border border-(--color-rule) text-(--color-ink-muted) transition-colors hover:bg-(--color-rule) hover:text-(--color-ink)"
      >
        {playing ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <rect x="6" y="5" width="4" height="14" rx="1" />
            <rect x="14" y="5" width="4" height="14" rx="1" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M8 5.5v13a1 1 0 0 0 1.5.87l11-6.5a1 1 0 0 0 0-1.74l-11-6.5A1 1 0 0 0 8 5.5z" />
          </svg>
        )}
      </button>
      {failed && (
        <a
          href={src}
          target="_blank"
          rel="noopener noreferrer"
          className="ms-2 text-xs underline underline-offset-2 text-(--color-ink-muted)"
          dir="ltr"
        >
          Open audio
        </a>
      )}
    </span>
  );
}
