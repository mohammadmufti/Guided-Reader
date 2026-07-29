# Deploying, and seeing changes live

The goal: push a change, get a live site, run nothing locally.

## First push: exact steps

```bash
tar xzf tajrid-reader-source.tar.gz -C tajrid-reader
cd tajrid-reader

# The workbook is NOT in the archive — it is a user-supplied input with no
# public URI, so CI cannot fetch it. fetch.py looks for it at the repo root.
cp /path/to/Tajrid_frequency_tables.xlsx .

git init && git add -A && git commit -m "Tajrid Reader"
git remote add origin git@github.com:<you>/<repo>.git
git push -u origin main
```

Then, once, in the repository settings: **Settings → Pages → Source →
GitHub Actions**. Without that the workflow builds and the deploy step fails.

The first run takes about four and a half minutes; later ones about two, once
the source downloads and the Lane ingest are cached. The live URL appears on
the workflow run under the `deploy` job.

## What goes in the repository

**Commit:** `pipeline/`, `web/src`, `web/package*.json`, the config files, the
docs, `.github/workflows/`. About 3.5 MB.

**Commit the lexicon workbook too** (`Tajrid_frequency_tables.xlsx`, 7.4 MB).
It is a user-supplied input with no public URI, so CI cannot fetch it. If it
grows past ~50 MB, move it to a release asset and add it to `fetch.py` as an
`http` source.

**Do not commit:** `pipeline/cache/` (70 MB of downloads), `pipeline/build/`
(intermediates), `web/public/data/` (81 MB, generated), `web/dist/`,
`node_modules/`. All of these are rebuilt by CI in about four minutes.

Committing generated data is the tempting mistake. It would put 81 MB and 3,132
files in every clone, and every rebuild would show as a 3,132-file diff.

## The workflow

`.github/workflows/deploy.yml` does the whole thing on push to `main`:

```
checkout → cache sources → fetch → ingest Lane → codegen --check
        → segment → lexicon → bind → build → tsc → vite build → Pages
```

Timings measured on this build:

| stage | cold | cached |
|---|--:|--:|
| fetch (70 MB, incl. Lane's 61 MB db) | ~60 s | ~2 s |
| `lane.py` (5,078 roots, 47,919 entries) | ~90 s | 0 |
| segment · lexicon · bind | 49 s | 49 s |
| `build.py --no-precompress` | 33 s | 33 s |
| `npm ci` + vite build | ~45 s | ~25 s |
| **total** | **~4½ min** | **~2 min** |

Two caches carry the cost: the source downloads keyed on the corpus configs,
and the Lane ingest keyed on `lane.py`. A cache hit does not weaken the
checksum guarantee — `fetch.py` still verifies every file and fails loudly on a
mismatch.

## Why `--no-precompress` on Pages

The build normally writes `.gz` and `.br` siblings for every file. That is
right for a host that serves them and pure waste on one that does not:

| | with | without |
|---|--:|--:|
| build time | 169 s | **33 s** |
| files | 9,396 | **3,132** |
| on disk | 123 MB | **81 MB** |

GitHub Pages compresses on the fly and ignores the siblings, so drop them
there. **On Cloudflare Pages or Netlify, remove the flag** — they do serve
precompressed files, and brotli-11 beats their on-the-fly compression.

## Host notes

**GitHub Pages** — simplest, free, no account beyond GitHub. Serves from
`/<repo>/`, which is why the workflow sets `BASE_PATH`; the app already reads
`import.meta.env.BASE_URL` for every data fetch. Pages has no SPA fallback, so
the workflow copies `index.html` to `404.html` — without it, reloading
`/hadith/42` returns a 404. Site limit 1 GB; we use 81 MB.

**Cloudflare Pages** — better fit if you keep precompression. It also honours
`web/public/_headers`, which is already written with the right policy:
`index.json` revalidates, everything else is `immutable` because the client
requests it with `?v={buildId}`. Pages ignores that file, so caching there is
whatever GitHub decides.

**Netlify** — same as Cloudflare for our purposes; `_headers` works.

## Adding a text, live

1. Add `pipeline/corpora/mytext.yaml` and its workbook.
2. Add the two lines to the workflow's pipeline step.
3. Push.

Lane does not need re-ingesting — it is fetched once, whole, and `build.py`
ships only the roots each corpus uses.

Open a pull request instead of pushing to `main` and the workflow builds and
runs all four end-to-end gates without deploying, so a regression is visible
before it is live.
