import type { ArStep } from "@/hooks/useSettings";

interface Props {
  step: ArStep;
  harakat: boolean;
  onStep: (s: ArStep) => void;
  onHarakat: () => void;
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
export function ReadingControls({ step, harakat, onStep, onHarakat }: Props) {
  return (
    <div className="flex items-center gap-4">
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
