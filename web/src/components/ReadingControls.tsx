import type { ArStep, Theme, Face } from "@/hooks/useSettings";
import { FACES } from "@/hooks/useSettings";

interface Props {
  step: ArStep;
  harakat: boolean;
  theme: Theme;
  face: Face;
  onStep: (s: ArStep) => void;
  onHarakat: () => void;
  onTheme: () => void;
  onFace: () => void;
}

const THEME_LABEL: Record<Theme, string> = {
  system: "المظهر: حسب الجهاز",
  light: "المظهر: فاتح",
  dark: "المظهر: داكن",
};

/** Sun, moon, or a device outline — whichever state the toggle is in. */
function ThemeIcon({ theme }: { theme: Theme }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  if (theme === "dark")
    return (
      <svg {...common}>
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
      </svg>
    );
  if (theme === "light")
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
      </svg>
    );
  return (
    <svg {...common}>
      <rect x="2" y="4" width="20" height="13" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </svg>
  );
}

const STEPS: ArStep[] = [1, 2, 3, 4, 5];

/**
 * The two reading controls.
 *
 * Size is a five-step scale rendered as five ticks of increasing height — the
 * control shows what it does rather than labelling it "A A A". It applies to
 * the Arabic only; the apparatus stays where it is, because a student enlarging
 * the text wants more of the text, not a bigger interface.
 *
 * The harakat toggle exists because the data makes it free and it turns the
 * reader into a self-test: hide the vowels, read the line, show them back.
 */
export function ReadingControls({
  step,
  harakat,
  theme,
  face,
  onStep,
  onHarakat,
  onTheme,
  onFace,
}: Props) {
  const current = FACES.find((f) => f.id === face) ?? FACES[0]!;
  return (
    // `flex-wrap` matters here: the control row grew a face selector and at
    // 360px the fixed row ran 7px past the viewport. Controls wrap rather than
    // overflow, and the gap tightens on small screens.
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 sm:gap-x-4">
      <div
        role="radiogroup"
        aria-label="حجم الخط"
        className="flex items-end gap-0.5 rounded-md border border-(--color-rule) px-1.5 py-1"
      >
        {STEPS.map((s) => (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={s === step}
            aria-label={`حجم ${s} من ${STEPS.length}`}
            onClick={() => onStep(s)}
            className="group flex h-7 w-6 items-end justify-center"
          >
            <span
              aria-hidden="true"
              className={`w-2.5 rounded-t-[1px] transition-colors ${
                s === step
                  ? "bg-(--color-accent)"
                  : "bg-(--color-rule) group-hover:bg-(--color-ink-muted)"
              }`}
              style={{ height: `${4 + s * 3}px` }}
            />
          </button>
        ))}
      </div>

      {/* Legibility is partly the face and partly the reader's eyes and screen,
          so it is offered rather than decided. The label is set in the face it
          selects, which says more than a name would. */}
      <button
        type="button"
        onClick={onFace}
        title={current.note}
        aria-label={`الخط: ${current.label}`}
        className="arabic rounded-md border border-(--color-rule) px-2.5 py-1 text-base transition-colors hover:bg-(--color-rule)"
        lang="ar"
      >
        {current.label}
      </button>

      <button
        type="button"
        onClick={onTheme}
        title={THEME_LABEL[theme]}
        aria-label={THEME_LABEL[theme]}
        className="flex h-8 w-8 items-center justify-center rounded-md border border-(--color-rule) transition-colors hover:bg-(--color-rule)"
      >
        <ThemeIcon theme={theme} />
      </button>

      <button
        type="button"
        onClick={onHarakat}
        aria-pressed={harakat}
        className="rounded-md border border-(--color-rule) px-2.5 py-1.5 text-sm transition-colors hover:bg-(--color-rule)"
      >
        <span className="arabic text-base" lang="ar" aria-hidden="true">
          {harakat ? "بَ" : "ب"}
        </span>
        <span className="ms-2 text-xs text-(--color-ink-muted)" lang="ar">
          {harakat ? "إخفاء الحركات" : "إظهار الحركات"}
        </span>
      </button>
    </div>
  );
}
