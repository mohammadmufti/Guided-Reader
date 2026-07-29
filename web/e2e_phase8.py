"""
Phase 8 gate check: contrast, keyboard-only operation, reduced motion, and the
three viewport widths.

Contrast is measured on RENDERED colours, not on the token values, and includes
the hover and selection states against the Arabic text — those are the pairs
that get missed, because they only exist while a pointer or a selection is on
the word.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
SHOTS = Path(__file__).resolve().parent.parent / "pipeline" / "reports" / "shots"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


CONTRAST_JS = """
() => {
  // getComputedStyle returns oklab()/lab() here, because the design tokens are
  // authored in oklch and Chromium preserves the colour space. Parsing those
  // channels as if they were RGB gives nonsense (near-black on near-white came
  // out as 1.5:1). Resolve every colour through a canvas instead, which hands
  // back true sRGB bytes whatever the input notation.
  const cv = document.createElement('canvas');
  cv.width = cv.height = 1;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const parse = (str) => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = str;
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = (rgb) => 0.2126*lin(rgb[0]) + 0.7152*lin(rgb[1]) + 0.0722*lin(rgb[2]);
  const over = (fg, bg) => [0,1,2].map(i => fg[i]*fg[3] + bg[i]*(1-fg[3]));
  const ratio = (a, b) => {
    const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (l1 + 0.05) / (l2 + 0.05);
  };
  const bgOf = (el) => {
    let node = el;
    let acc = null;
    while (node && node !== document.documentElement) {
      const c = parse(getComputedStyle(node).backgroundColor);
      if (c[3] > 0) {
        acc = acc === null ? c : [...over(acc, c), 1];
        if (c[3] === 1) return acc.slice(0, 3);
      }
      node = node.parentElement;
    }
    const body = parse(getComputedStyle(document.body).backgroundColor);
    return acc === null ? body.slice(0, 3) : over(acc, body);
  };
  const measure = (sel, label) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    const bg = bgOf(el);
    return { label, ratio: +ratio(over(parse(cs.color), bg), bg).toFixed(2),
             size: parseFloat(cs.fontSize), weight: cs.fontWeight };
  };
  // A bar with no text is a non-text UI component (WCAG 1.4.11): what matters
  // is its own fill against what sits behind it, not its inherited text colour.
  const nonText = (sel, label) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const own = parse(getComputedStyle(el).backgroundColor);
    const behind = bgOf(el.parentElement);
    return { label, ratio: +ratio(over(own, behind), behind).toFixed(2),
             size: 99, weight: '400', nonText: true };
  };

  return [
    nonText('[role="radio"][aria-checked="true"] span', 'active size tick (non-text)'),
    measure('.arabic-body [data-token]', 'Arabic word on paper'),
    measure('.arabic-body [aria-pressed="true"]', 'Arabic word, SELECTED'),
    measure('.arabic-body [data-token]:hover', 'Arabic word, HOVERED'),
    measure('aside p', 'panel body text'),
    measure('header p', 'header subtitle (muted)'),
    measure('main footer p', 'keyboard hint (muted, small)'),
  ].filter(Boolean);
}
"""


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---- contrast, light and dark ---------------------------------------
        for scheme in ("light", "dark"):
            page = browser.new_page(
                viewport={"width": 1440, "height": 1100}, color_scheme=scheme
            )
            page.goto(f"{BASE}/hadith/38?w=48", wait_until="networkidle")
            page.wait_for_selector('aside [data-panel="ready"]')
            page.wait_for_timeout(400)
            # Put a real hover on a word so the hover pair can be measured.
            page.locator('.arabic-body [data-token="10"]').hover()
            page.wait_for_timeout(120)
            rows = page.evaluate(CONTRAST_JS)
            hover = page.evaluate(
                """() => {
                  const el = document.querySelector('.arabic-body [data-token="10"]');
                  const cs = getComputedStyle(el);
                  return { bg: cs.backgroundColor, fg: cs.color };
                }"""
            )
            for r in rows:
                large = r["size"] >= 24 or (r["size"] >= 18.66 and int(r["weight"]) >= 700)
                # WCAG 1.4.3 for text; 1.4.11 for non-text UI components.
                need = 3.0 if (large or r.get("nonText")) else 4.5
                check(
                    f"contrast {scheme}: {r['label']}",
                    r["ratio"] >= need,
                    f"{r['ratio']}:1 (needs {need}, {r['size']:.0f}px)",
                )
            check(f"hover state resolves a colour ({scheme})", bool(hover["bg"]), str(hover))
            page.close()

        # ---- reduced motion --------------------------------------------------
        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
        )
        page.goto(f"{BASE}/hadith/1", wait_until="networkidle")
        page.wait_for_selector(".arabic-body [data-token]")
        durations = page.evaluate(
            """() => [...document.querySelectorAll('*')]
                 .map(e => getComputedStyle(e).transitionDuration)
                 .filter(d => d && d !== '0s')
                 .filter(d => parseFloat(d) > 0.001)"""
        )
        check("reduced motion kills all transitions", not durations, str(durations[:4]))
        page.close()

        # ---- keyboard-only walkthrough ---------------------------------------
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(f"{BASE}/hadith/1", wait_until="networkidle")
        page.wait_for_selector(".arabic-body [data-token]")
        page.wait_for_timeout(300)

        # size control, reached by tabbing only
        page.keyboard.press("Tab")
        for _ in range(14):
            role = page.evaluate("document.activeElement?.getAttribute('role')")
            if role == "radio":
                break
            page.keyboard.press("Tab")
        check("size control is reachable by Tab",
              page.evaluate("document.activeElement?.getAttribute('role')") == "radio")
        before = page.evaluate("getComputedStyle(document.querySelector('.arabic-body')).fontSize")
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        after = page.evaluate("getComputedStyle(document.querySelector('.arabic-body')).fontSize")
        check("size control works from the keyboard", before != after, f"{before} -> {after}")
        check("size step is recorded on the document",
              page.evaluate("document.documentElement.dataset.arStep") is not None)

        # persistence across a reload
        step = page.evaluate("document.documentElement.dataset.arStep")
        page.reload(wait_until="networkidle")
        page.wait_for_selector(".arabic-body")
        page.wait_for_timeout(250)
        check("size choice persists across a reload",
              page.evaluate("document.documentElement.dataset.arStep") == step,
              f"step {step}")

        # harakat toggle
        page.get_by_role("button", name="إخفاء الحركات").click()
        page.wait_for_timeout(250)
        stripped = page.locator('.arabic-body [data-token="0"]').inner_text()
        check("harakat toggle removes the vowel marks",
              not any("\u064b" <= c <= "\u0652" for c in stripped), repr(stripped))
        page.get_by_role("button", name="إظهار الحركات").click()
        page.wait_for_timeout(250)
        restored = page.locator('.arabic-body [data-token="0"]').inner_text()
        check("harakat toggle restores them",
              any("\u064b" <= c <= "\u0652" for c in restored), repr(restored))

        # word selection by keyboard, then panel, then escape
        page.locator('.arabic-body [data-token="4"]').focus()
        page.keyboard.press("Enter")
        page.wait_for_selector('aside [data-panel="ready"]')
        check("word selectable by keyboard", "w=4" in page.url, page.url)
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        check("Escape clears the selection", "w=" not in page.url, page.url)

        page.close()

        # ---- three viewport widths -------------------------------------------
        for width, label in ((360, "360"), (768, "768"), (1440, "1440")):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(f"{BASE}/hadith/38?w=48", wait_until="networkidle")
            page.wait_for_selector('aside [data-panel="ready"]')
            page.wait_for_timeout(500)
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            check(f"no horizontal overflow at {label}px", overflow <= 0, f"{overflow}px")
            aside = page.locator("aside").bounding_box()
            if width < 1024:
                vh = page.viewport_size["height"]
                check(f"panel is a bottom sheet at {label}px",
                      aside is not None and aside["y"] + aside["height"] >= vh - 2,
                      f"bottom at {aside['y'] + aside['height']:.0f} of {vh}")
            else:
                art = page.locator("article").bounding_box()
                check("panel is a right column at 1440px",
                      art["x"] < aside["x"] and art["width"] > aside["width"],
                      f"article {art['width']:.0f}px, aside {aside['width']:.0f}px")
            page.screenshot(path=str(SHOTS / f"phase8-{label}.png"))
            page.close()

        browser.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    (SHOTS.parent / "phase8_checks.json").write_text(
        json.dumps([{"check": n, "pass": ok, "detail": d} for n, ok, d in results],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
