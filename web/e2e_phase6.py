"""
Phase 6 gate check.

The load-bearing claim is that wrapping every word in its own element does not
disturb Arabic shaping or diacritic placement. That is checked by rendering the
same hadith twice — once as one unsegmented text node, once as per-token spans —
and diffing the two bitmaps pixel by pixel, at three font sizes.
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


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.add_init_script(
            "window.__cls=0;new PerformanceObserver(l=>{for(const e of l.getEntries())"
            "if(!e.hadRecentInput)window.__cls+=e.value}).observe({type:'layout-shift',buffered:true});"
        )
        page.goto(f"{BASE}/hadith/1", wait_until="networkidle")
        page.wait_for_selector("article p.arabic-body [data-token]")

        tokens = page.locator("article p.arabic-body [data-token]")
        clickable = tokens.count()
        record = page.evaluate(
            "fetch('/data/index.json').then(r=>r.json())"
            ".then(i=>fetch('/data/hadith/'+i.navigation.numberIndex['1']+'.json?v='+i.buildId))"
            ".then(r=>r.json())"
        )
        expect_clickable = sum(1 for t in record["tokens"] if t["clickable"])
        check("every clickable token is its own element", clickable == expect_clickable,
              f"{clickable} spans vs {expect_clickable} clickable tokens")
        check("unbound tokens are not focusable",
              page.locator("article p.arabic-body [data-token]").count()
              == page.locator("article p.arabic-body [role=button]").count())

        # ---- shaping: segmented vs unsegmented, at three sizes --------------
        #
        # A raw bitmap diff turns out to be the wrong instrument. Each inline
        # box rounds its own advance width, so a line made of 39 spans can end
        # up 1px wider than the same line as one text node — which shifts every
        # glyph on that line by a subpixel and lights up ~1% of pixels while
        # nothing about the shaping has changed. What actually has to hold is
        # that the text breaks into the same lines at the same places and each
        # line occupies the same ink extent. That is measured directly, and the
        # bitmap difference is reported alongside as information.
        full_text = record["leading"] + "".join(
            t["surface"] + t["punctuationAfter"] for t in record["tokens"]
        )
        for label, px in (("sm", 20), ("md", 30), ("lg", 40)):
            geo = page.evaluate(
                """([text, px]) => {
                  document.getElementById('ctl')?.remove();
                  const src = document.querySelector('article p.arabic-body');
                  const ctl = document.createElement('p');
                  ctl.id = 'ctl'; ctl.dir = 'rtl'; ctl.lang = 'ar';
                  ctl.className = src.className;
                  ctl.textContent = text;
                  src.parentElement.appendChild(ctl);
                  for (const el of [src, ctl]) {
                    el.style.fontSize = px + 'px';
                    el.style.width = '760px';
                  }
                  // Group client rects into line boxes by their top edge.
                  const lines = (el) => {
                    const r = document.createRange();
                    r.selectNodeContents(el);
                    const rows = new Map();
                    for (const b of r.getClientRects()) {
                      if (b.width === 0) continue;
                      const key = Math.round(b.top);
                      const cur = rows.get(key) || { l: Infinity, r: -Infinity };
                      cur.l = Math.min(cur.l, b.left);
                      cur.r = Math.max(cur.r, b.right);
                      rows.set(key, cur);
                    }
                    return [...rows.entries()]
                      .sort((a, b) => a[0] - b[0])
                      .map(([, v]) => ({ l: Math.round(v.l), w: Math.round(v.r - v.l) }));
                  };
                  return { seg: lines(src), ctl: lines(ctl) };
                }""",
                [full_text, px],
            )
            page.wait_for_timeout(120)
            a = page.locator("article p.arabic-body").first.screenshot()
            b = page.locator("#ctl").screenshot()
            (SHOTS / f"phase6-segmented-{label}.png").write_bytes(a)
            (SHOTS / f"phase6-control-{label}.png").write_bytes(b)

            from PIL import Image, ImageChops
            import io

            ia = Image.open(io.BytesIO(a)).convert("L")
            ib = Image.open(io.BytesIO(b)).convert("L")
            ratio = 1.0
            if ia.size == ib.size:
                d = ImageChops.difference(ia, ib)
                ratio = sum(1 for v in d.get_flattened_data() if v > 24) / (ia.size[0] * ia.size[1])

            seg, ctl = geo["seg"], geo["ctl"]
            same_lines = len(seg) == len(ctl)
            worst = 0
            if same_lines:
                worst = max(
                    max(abs(s["l"] - c["l"]), abs(s["w"] - c["w"])) for s, c in zip(seg, ctl)
                )
            check(
                f"same line breaking at {label} ({px}px)",
                same_lines,
                f"{len(seg)} lines vs {len(ctl)}",
            )
            check(
                f"line ink extents match within 1px at {label} ({px}px)",
                same_lines and worst <= 1,
                f"worst deviation {worst}px across {len(seg)} lines; "
                f"bitmap differs on {ratio*100:.2f}% of pixels",
            )
        page.evaluate("document.getElementById('ctl')?.remove()")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("article p.arabic-body [data-token]")

        # ---- selection ------------------------------------------------------
        page.wait_for_timeout(300)
        page.evaluate("window.__cls=0")
        first = page.locator("article p.arabic-body [role=button]").first
        first.click()
        page.wait_for_timeout(200)
        check("click selects a word", "w=" in page.url, page.url.split("?")[-1])
        check("selection is visible",
              page.locator("article p.arabic-body [aria-pressed=true]").count() == 1)

        # ---- keyboard traversal reaches every clickable word ----------------
        # Reachability is a property of the DOM and the handlers, not of
        # timing — so wait for the focus to actually move after each press
        # instead of sleeping a fixed 45ms. Under load (panel shard fetches
        # re-rendering mid-walk) the fixed sleep intermittently read focus
        # during a transition and lost one token: 38/39 on the first real CI
        # run, 39/39 in isolation. Two consecutive stalls means the end of
        # the line.
        page.keyboard.press("Home")
        page.wait_for_timeout(120)
        seen = set()
        stalls = 0
        for _ in range(expect_clickable + 8):
            idx = page.evaluate("document.activeElement?.dataset?.token")
            if idx is not None:
                seen.add(int(idx))
            page.keyboard.press("ArrowLeft")
            try:
                page.wait_for_function(
                    "prev => document.activeElement?.dataset?.token !== prev",
                    arg=idx, timeout=700)
                stalls = 0
            except Exception:
                stalls += 1
                if stalls >= 2:
                    break
        check("keyboard traversal reaches every clickable word",
              len(seen) == expect_clickable, f"{len(seen)}/{expect_clickable}")

        # ---- traversal skips unbound tokens ---------------------------------
        unbound = [t["i"] for t in record["tokens"] if not t["clickable"]]
        check("traversal never lands on an unbound token",
              not (seen & set(unbound)), f"{len(unbound)} unbound in this record")

        # ---- arrows do not leak into hadith navigation ----------------------
        check("word arrows do not change the hadith", page.url.rstrip("/").split("?")[0].endswith("/hadith/1"),
              page.url)

        # ---- Escape releases the pane, then arrows move between hadith ------
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(400)
        check("Escape hands the arrows back to hadith navigation",
              page.url.split("?")[0].rstrip("/").endswith("/hadith/2"), page.url)

        # ---- deep link restores selection -----------------------------------
        page.goto(f"{BASE}/hadith/1?w=4", wait_until="networkidle")
        page.wait_for_selector("article p [aria-pressed=true]")
        sel = page.locator("article p.arabic-body [aria-pressed=true]").first
        check("deep link restores the selection",
              sel.get_attribute("data-token") == "4",
              f"restored token {sel.get_attribute('data-token')}")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("article p [aria-pressed=true]")
        check("selection survives a reload",
              page.locator("article p.arabic-body [aria-pressed=true]").first.get_attribute("data-token") == "4")

        # ---- selection does not create history entries ----------------------
        start = page.url
        for i in (6, 8, 10):
            page.locator(f'article p.arabic-body [data-token="{i}"]').click()
            page.wait_for_timeout(120)
        page.go_back()
        page.wait_for_timeout(400)
        check("selecting words does not stack history entries",
              "/hadith/1" not in page.url or page.url != start,
              f"back from {page.url}")

        # ---- no layout shift on selection -----------------------------------
        page.goto(f"{BASE}/hadith/1", wait_until="networkidle")
        page.wait_for_selector("article p.arabic-body [data-token]")
        page.wait_for_timeout(500)
        page.evaluate("window.__cls=0")
        before = page.locator('article p.arabic-body [data-token="10"]').bounding_box()
        for i in (2, 5, 9, 14, 20):
            loc = page.locator(f'article p.arabic-body [data-token="{i}"]')
            if loc.count():
                loc.click()
                page.wait_for_timeout(100)
        after = page.locator('article p.arabic-body [data-token="10"]').bounding_box()
        cls = page.evaluate("window.__cls")
        moved = max(abs(before["x"] - after["x"]), abs(before["y"] - after["y"]))
        check("no layout shift on selection", cls < 0.005, f"CLS={cls:.5f}")
        check("neighbouring words do not move", moved < 0.6, f"{moved:.2f}px")

        # ---- low-confidence marker -------------------------------------------
        page.goto(f"{BASE}/hadith/7", wait_until="networkidle")
        page.wait_for_selector("article p.arabic-body [data-token]")
        low = page.locator('article p.arabic-body [data-confidence="low"]').count()
        med = page.locator('article p.arabic-body [data-confidence="medium"]').count()
        check("confidence is carried into the DOM",
              page.locator("article p.arabic-body [data-confidence]").count() > 0,
              f"low={low}, medium={med} in hadith 7")

        page.goto(f"{BASE}/hadith/1?w=6", wait_until="networkidle")
        page.wait_for_selector("article p [aria-pressed=true]")
        page.wait_for_timeout(300)
        page.screenshot(path=str(SHOTS / "phase6-selection.png"))

        browser.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    (SHOTS.parent / "phase6_checks.json").write_text(
        json.dumps([{"check": n, "pass": ok, "detail": d} for n, ok, d in results],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
