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

## A hazard worth knowing: shard counts live in index.json

Shard counts are derived from payload size, so they CHANGE when content changes
— the surface set went from 64 shards to 32 the moment the statistics moved into
their own files. The client reads those counts from `index.json` and routes with
`hash % count`.

So a stale `index.json` is not a cosmetic problem: it makes the client ask for
shards that do not exist, and roughly half the words in the book 404.

`web/public/_headers` says `index.json` must revalidate — but **GitHub Pages
ignores `_headers`**. The client therefore fetches it with `cache: "no-cache"`,
which does not depend on the host, and retries once against a freshly fetched
index if a shard 404s. Both are needed: the first prevents the problem, the
second recovers from it on a CDN that ignores the first.

If you ever see `stats-0NN.json: HTTP 404` after a deploy, that is this, and a
hard refresh clears it.

## Pipeline step order is load-bearing

`build.py` consumes the output of `analyse.py` and `disambiguate.py`. Both are
OPTIONAL — the build prints a warning and carries on without them — which makes
mis-ordering them a silent correctness bug rather than a crash.

It happened: `disambiguate.py` was placed after `build.py` in CI, so the payload
was written before the context roots existed and shipped with none. Nothing
failed at build time. The pipeline tests caught it, which is the only reason it
was noticed.

The order inside `Run the pipeline` is therefore fixed:

```
segment  ->  disambiguate  ->  lexicon  ->  bind  ->  build
             (needs records.json)          (both consumed by build)
```

`analyse.py` and `lane.py` may run any time before `build.py`.

## Host notes

**GitHub Pages** — simplest, free, no account beyond GitHub.

A **user site** (`<you>.github.io`) and any number of **project sites** coexist:
the user site serves at `https://<you>.github.io/`, a project repo at
`https://<you>.github.io/<repo>/`. You do not copy the build into the user-site
repo — enable Pages on the project repo and it deploys itself. Copying 3,132
generated files into another repository is exactly what this arrangement avoids.

A subpath deploy needs **two** things, and the second is easy to miss:

1. `BASE_PATH` — sets Vite's `base`, so assets and data resolve under `/<repo>/`.
   The workflow derives it from the repository name.
2. `basename` on the router — sets where ROUTE MATCHING starts. Vite's `base`
   does not do this. Without it, `/<repo>/hadith/1` is matched against the route
   `/hadith/:number`, fails, falls through to the catch-all, and every page
   renders the "no such hadith" state while assets load perfectly. `App.tsx`
   passes `import.meta.env.BASE_URL`, which is `"/"` for a root deploy, so the
   same build works either way.

Verified against a server that mimics Pages' project-site behaviour: `/`, deep
links, the word panel's shard fetches, search and `/about` all work under
`/Guided-Reader/`, and unchanged at the root. Pages has no SPA fallback, so
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
