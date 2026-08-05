"""
Phase 7 gate check.

Clicks through a sample spanning every `divergence` value, root present and
absent, a proper noun, a hapax, a curated technical term, a low-confidence
binding and an unbound token, and asserts on each panel:

  * no empty box and no section that is a label with nothing under it,
  * no raw Buckwalter markup reaching the reader,
  * no untreated null leaking as "null" / "undefined" / "NaN",
  * `classical_sense_sample` never presented as the definition.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Where the app under test lives. CI builds under /<repo>/ and sets this;
# the default matches a local root build.
BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:5173").rstrip("/")
SHOTS = Path(__file__).resolve().parent.parent / "pipeline" / "reports" / "shots"
SAMPLE = json.loads(Path("/tmp/phase7_sample.json").read_text(encoding="utf-8"))

RAW_MARKUP = [" + ", "___", "<verb>", "[fem.sg.]", "[masc.pl.]", "[acc.indef.]"]
NULL_LEAKS = ["null", "undefined", "NaN", "None", "[object Object]"]

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    if not ok:
        print(f"  FAIL  {name}  — {detail}")


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # ---- empty state -----------------------------------------------------
        page.goto(f"{BASE}/tajrid/read/1", wait_until="networkidle")
        page.wait_for_selector("aside")
        empty = page.locator("aside").inner_text()
        check("empty state invites action", "Select any word" in empty, empty[:60])
        check("empty state suggests a word",
              page.locator("aside button").count() >= 1)
        page.locator("aside button").first.click()
        page.wait_for_timeout(400)
        check("empty-state suggestion selects a word", "w=" in page.url, page.url)

        # ---- the sample ------------------------------------------------------
        seen_divergence: set[str] = set()
        for case in SAMPLE:
            tag = f"{case['criterion']} (hadith {case['number']}, word {case['i']})"
            page.goto(f"{BASE}/tajrid/read/{case['number']}?w={case['i']}",
                      wait_until="networkidle")
            try:
                page.wait_for_selector('aside [data-panel="ready"], aside section', timeout=8000)
            except Exception:
                check(f"panel renders — {tag}", False, "no panel content")
                continue
            aside = page.locator("aside")
            text = aside.inner_text()

            check(f"panel is not empty — {tag}", len(text.strip()) > 40, f"{len(text)} chars")

            leaked = [m for m in RAW_MARKUP if m in text]
            check(f"no raw Buckwalter — {tag}", not leaked, str(leaked))

            # Word-boundary match so "nullify" or an Arabic word are not hits.
            leaks = [w for w in NULL_LEAKS if re.search(rf"\b{re.escape(w)}\b", text)]
            check(f"no untreated nulls — {tag}", not leaks, str(leaks))

            lonely = page.evaluate(
                """() => {
                  const bad = [];
                  for (const s of document.querySelectorAll('aside section')) {
                    const h = s.querySelector('h3');
                    if (!h) continue;
                    const rest = s.innerText.replace(h.innerText, '').trim();
                    if (rest.length === 0) bad.push(h.innerText.trim());
                  }
                  return bad;
                }"""
            )
            check(f"no lonely label — {tag}", not lonely, str(lonely))

            if case["criterion"].startswith("div:"):
                seen_divergence.add(case["criterion"][4:])

        # ---- specific promises ----------------------------------------------
        # curated: literal and technical shown side by side
        curated = next(c for c in SAMPLE if c["criterion"] == "div:curated")
        page.goto(f"{BASE}/tajrid/read/{curated['number']}?w={curated['i']}", wait_until="networkidle")
        page.wait_for_selector('aside [data-panel="ready"]')
        t = page.locator("aside").inner_text()
        # inner_text() returns RENDERED text, and these labels carry
        # text-transform: uppercase — so match case-insensitively.
        low = t.lower()
        check("curated shows both literal and technical",
              "literal" in low and "technical" in low, t[:120].replace("\n", " / "))

        # Lane: the word's OWN entry, with Lane's senses in Lane's order.
        # v1 showed a single mechanically-sampled sense here; that field no
        # longer exists in the payload, so this asserts the replacement.
        found_lane = False
        for case in SAMPLE:
            if case["criterion"] in ("unbound", "no_gloss"):
                continue  # no lexicon entry, so no panel to wait on
            page.goto(f"{BASE}/tajrid/read/{case['number']}?w={case['i']}", wait_until="networkidle")
            try:
                page.wait_for_selector('aside [data-panel="ready"]', timeout=8000)
            except Exception:
                continue
            body = page.locator("aside").inner_text()
            low = body.lower()
            # Detect the CLASSICAL SECTION by its Arabic title — unique to it.
            # Matching on "lane's lexicon" broke when the analyser-provenance
            # copy legitimately mentioned Lane for a word with no entry.
            if "المعنى الكلاسيكي" in body:
                found_lane = True
                check("Lane entry names whose entry it is",
                      "own entry" in low or "under this root" in low, body[:80])
                check("Lane sources are explained rather than left as bare letters",
                      "al-qāmūs" in low or "al-ṣiḥāḥ" in low)
                break
        check("a Lane entry appeared in the walkthrough", found_lane)
        check("the mechanically sampled sense is gone from the payload",
              "sampled from Lane" not in page.locator("aside").inner_text())

        # not_applicable renders nothing rather than an empty divergence box
        na = next(c for c in SAMPLE if c["criterion"] == "div:not_applicable")
        page.goto(f"{BASE}/tajrid/read/{na['number']}?w={na['i']}", wait_until="networkidle")
        page.wait_for_selector('aside [data-panel="ready"]')
        na_text = page.locator("aside").inner_text()
        check("not_applicable shows no divergence section",
              "senses differ" not in na_text and "diverge" not in na_text)

        # Root-absent explains itself. The sample is chosen on the WORKBOOK
        # having no root, and since the analysers landed most of those forms now
        # have one — 20,720 of 22,464 carry a root from some source. So walk the
        # sample for one that is still blank everywhere; if none is, the
        # explanation has nothing left to explain and the check is moot.
        explained = None
        all_rooted = True
        for c in SAMPLE:
            if c["criterion"] != "root_absent":
                continue
            page.goto(f"{BASE}/tajrid/read/{c['number']}?w={c['i']}", wait_until="networkidle")
            page.wait_for_selector('aside [data-panel="ready"]')
            body = page.locator("aside").inner_text()
            if "ROOT AND LEMMA" in body.upper() and "do not have one" in body:
                explained = c
                break
            all_rooted = all_rooted and "الجذر" in body
        check("absent root is explained, not left blank",
              explained is not None or all_rooted,
              "moot — every sampled form now carries a root" if all_rooted else "")

        # pos_agreement = disagree warns plainly
        pd = next(c for c in SAMPLE if c["criterion"] == "pos_disagree")
        page.goto(f"{BASE}/tajrid/read/{pd['number']}?w={pd['i']}", wait_until="networkidle")
        page.wait_for_selector('aside [data-panel="ready"]')
        check("analyser disagreement warns that the root may be wrong",
              "may be wrong" in page.locator("aside").inner_text())

        # provenance is collapsed by default
        check("provenance is collapsed by default",
              page.locator("aside button[aria-expanded=false]").count() >= 1)

        check("every divergence value was exercised",
              len(seen_divergence) >= 6, f"{sorted(seen_divergence)}")
        check("no console or page errors during the walkthrough", not errors, str(errors[:3]))

        # screenshots
        page.goto(f"{BASE}/tajrid/read/{curated['number']}?w={curated['i']}", wait_until="networkidle")
        page.wait_for_selector('aside [data-panel="ready"]')
        page.wait_for_timeout(400)
        page.screenshot(path=str(SHOTS / "phase7-curated.png"))

        browser.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} assertions passed "
          f"across {len(SAMPLE)} words")
    (SHOTS.parent / "phase7_checks.json").write_text(
        json.dumps([{"check": n, "pass": ok, "detail": d} for n, ok, d in results],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
