"""
Phase 5 gate check, driven through a real browser.

Verifies the four things the gate asks for:
  1. first -> last -> first by EVERY navigation mechanism
  2. deep links restore exact state
  3. browser back/forward behave
  4. no layout shift on navigation
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Where the app under test lives. CI builds under /<repo>/ and sets this;
# the default matches a local root build.
BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:5173").rstrip("/")
SHOTS = Path(__file__).resolve().parent.parent / "pipeline" / "reports" / "shots"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def number_in_url(page) -> int | None:
    tail = page.url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


def settle(page) -> None:
    """Wait for the record body to render, not just for the URL to change."""
    page.wait_for_selector("article p[lang=ar]", timeout=8000)
    page.wait_for_timeout(120)


def heading_number(page) -> int | None:
    el = page.locator("[data-hadith-number]").first
    try:
        return int(el.inner_text(timeout=4000).strip())
    except Exception:
        return None


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960})

        # --- CLS instrumentation, installed before any navigation ------------
        page.add_init_script(
            """
            window.__cls = 0;
            new PerformanceObserver((list) => {
              for (const e of list.getEntries()) {
                if (!e.hadRecentInput) window.__cls += e.value;
              }
            }).observe({ type: 'layout-shift', buffered: true });
            """
        )

        # --- root redirect ---------------------------------------------------
        page.goto(BASE, wait_until="networkidle")
        check("/ redirects to hadith 1", number_in_url(page) == 1, page.url)
        check("document is RTL", page.get_attribute("html", "dir") == "rtl")
        check("hadith 1 renders text", len(page.locator("article p[lang=ar]").last.inner_text()) > 80)
        page.screenshot(path=str(SHOTS / "phase5-hadith-1.png"))

        index = page.evaluate("fetch('/data/corpora/tajrid/index.json').then(r=>r.json())")
        numbers = sorted(int(n) for n in index["navigation"]["numberIndex"])
        first, last = numbers[0], numbers[-1]

        # --- mechanism 1: next / prev buttons --------------------------------
        page.goto(f"{BASE}/tajrid/read/{first}", wait_until="networkidle")
        page.get_by_role("link", name="Next", exact=False).click()
        page.wait_for_url(f"**/tajrid/read/{numbers[1]}")
        settle(page)
        page.get_by_role("link", name="Previous", exact=False).click()
        page.wait_for_url(f"**/tajrid/read/{first}")
        settle(page)
        check("buttons step forward and back", number_in_url(page) == first)

        # --- mechanism 2: keyboard, RTL mapping ------------------------------
        page.keyboard.press("ArrowLeft")
        page.wait_for_url(f"**/tajrid/read/{numbers[1]}")
        settle(page)
        forward_ok = number_in_url(page) == numbers[1]
        page.keyboard.press("ArrowRight")
        page.wait_for_url(f"**/tajrid/read/{first}")
        settle(page)
        check(
            "ArrowLeft advances, ArrowRight retreats (RTL)",
            forward_ok and number_in_url(page) == first,
        )

        # --- mechanism 3: jump-to, reaching the last hadith ------------------
        page.keyboard.press("/")
        focused = page.evaluate("document.activeElement?.id")
        check("'/' focuses the jump field", focused == "jump", str(focused))
        page.fill("#jump", str(last))
        page.keyboard.press("Enter")
        page.wait_for_url(f"**/tajrid/read/{last}")
        settle(page)
        check("jump-to reaches the last hadith", number_in_url(page) == last)
        check("last hadith renders", heading_number(page) == last)
        check(
            "next is disabled at the end",
            page.locator("nav [aria-disabled=true]").count() >= 1,
        )
        page.screenshot(path=str(SHOTS / "phase5-hadith-last.png"))

        # --- jump-to validation ----------------------------------------------
        page.keyboard.press("/")
        page.fill("#jump", str(last + 500))
        page.keyboard.press("Enter")
        page.wait_for_timeout(250)
        check(
            "out-of-range number is rejected in place",
            number_in_url(page) == last and page.locator("#jump-error").inner_text().strip() != "",
            page.locator("#jump-error").inner_text().strip(),
        )
        page.fill("#jump", "abc")
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        check("non-numeric input is rejected", number_in_url(page) == last)

        # --- mechanism 4: kitab/bab browser, back to the first ---------------
        page.get_by_role("button", name="الكتب والأبواب").click()
        page.wait_for_selector("[role=dialog]")
        check("book browser opens", page.locator("[role=dialog]").is_visible())
        n_kitab = page.locator("[role=dialog] > div ul > li").count()
        check("browser lists every kitab", n_kitab == index["counts"]["kitab"], f"{n_kitab}")
        page.locator("[role=dialog] button", has_text="كتاب بدء الوحي").first.click()
        page.wait_for_url(f"**/tajrid/read/{first}")
        settle(page)
        check("browser jumps to the first hadith of a kitab", number_in_url(page) == first)

        # --- Esc closes overlays ---------------------------------------------
        page.get_by_role("button", name="الكتب والأبواب").click()
        page.wait_for_selector("[role=dialog]")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        check("Esc closes the browser", page.locator("[role=dialog]").count() == 0)

        # --- deep link restores exact state ----------------------------------
        target = numbers[len(numbers) // 2]
        page.goto(f"{BASE}/tajrid/read/{target}", wait_until="networkidle")
        deep_num = heading_number(page)
        deep_kitab = page.locator("article").inner_text()
        check("deep link restores the record", deep_num == target, f"showed {deep_num}")
        check("deep link restores kitab context", "كتاب" in deep_kitab)

        # --- back / forward ---------------------------------------------------
        page.goto(f"{BASE}/tajrid/read/{first}", wait_until="networkidle")
        page.keyboard.press("ArrowLeft")
        page.wait_for_url(f"**/tajrid/read/{numbers[1]}")
        settle(page)
        page.keyboard.press("ArrowLeft")
        page.wait_for_url(f"**/tajrid/read/{numbers[2]}")
        settle(page)
        page.go_back()
        page.wait_for_url(f"**/tajrid/read/{numbers[1]}")
        settle(page)
        back_ok = heading_number(page) == numbers[1]
        page.go_forward()
        page.wait_for_url(f"**/tajrid/read/{numbers[2]}")
        settle(page)
        check(
            "back/forward restore both URL and content",
            back_ok and heading_number(page) == numbers[2],
        )

        # --- unknown number gives a real page with a way out -----------------
        page.goto(f"{BASE}/tajrid/read/99999", wait_until="networkidle")
        body = page.inner_text("body")
        check("unknown number shows a 404 state", "لا يوجد حديث بهذا الرقم" in body)
        check("404 keeps the jump control", page.locator("#jump").count() == 1)
        page.get_by_role("link", name="ابدأ من الحديث الأول").click()
        page.wait_for_url(f"**/tajrid/read/{first}")
        settle(page)
        check("404 offers a working way out", number_in_url(page) == first)
        page.screenshot(path=str(SHOTS / "phase5-404.png"))

        # --- layout shift across a run of navigations ------------------------
        page.goto(f"{BASE}/tajrid/read/{first}", wait_until="networkidle")
        page.wait_for_timeout(400)
        page.evaluate("window.__cls = 0")
        header_box = page.locator("header").first.bounding_box()
        for _ in range(12):
            page.keyboard.press("ArrowLeft")
            page.wait_for_timeout(160)
        page.wait_for_timeout(400)
        cls = page.evaluate("window.__cls")
        header_after = page.locator("header").first.bounding_box()
        moved = abs((header_box or {}).get("y", 0) - (header_after or {}).get("y", 0))
        check("cumulative layout shift over 12 navigations < 0.02", cls < 0.02, f"CLS={cls:.4f}")
        check("header does not move", moved < 1.0, f"{moved:.2f}px")

        # --- layout: requirement 3, measured not eyeballed --------------------
        page.set_viewport_size({"width": 1440, "height": 960})
        page.goto(f"{BASE}/tajrid/read/{first}", wait_until="networkidle")
        settle(page)
        art = page.locator("article").bounding_box() or {}
        asd = page.locator("aside").bounding_box() or {}
        check(
            "Arabic column is on the left of the apparatus",
            art.get("x", 0) < asd.get("x", 0),
            f"article x={art.get('x')}, aside x={asd.get('x')}",
        )
        check(
            "Arabic column is the wider of the two",
            art.get("width", 0) > asd.get("width", 0),
            f"article {art.get('width')}px vs aside {asd.get('width')}px",
        )

        # --- mobile ------------------------------------------------------------
        page.set_viewport_size({"width": 380, "height": 800})
        page.goto(f"{BASE}/tajrid/read/{first}", wait_until="networkidle")
        page.wait_for_timeout(300)
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        check("no horizontal overflow at 380px", overflow <= 0, f"{overflow}px")
        page.screenshot(path=str(SHOTS / "phase5-mobile.png"), full_page=False)

        browser.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    (SHOTS.parent / "phase5_checks.json").write_text(
        json.dumps([{"check": n, "pass": ok, "detail": d} for n, ok, d in results],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
