# Splits

A database of split times from elite track races, where **every value can be traced to the
exact words of the official document it was read from**, and a website for athletes and
coaches to explore how the world's best run their races.

It currently holds 2,078 races from 115 competitions (20,507 performances by 4,631 athletes,
258,259 split times):

- every elite race from the 100 m to the 5000 m, hurdles, steeplechase and mile included (and
  the occasional 300 m, 1000 m, 2000 m and two miles), whose race analysis OMEGA published at
  a Diamond League meeting from 2021 to 2026 or at the FBK Games in Hengelo from 2022 to 2024,
  with Hengelo's 10,000 m. National undercard races, B races and invitationals are left out.
  Sprints are timed every 10 m or at every hurdle (every 20 m, to the tenth, in 2021–22),
  longer races every 100 m, 200 m or lap;
- at the Olympic Games, every archived round of 2024 from the 100 m to the 10,000 m, hurdles
  and steeplechase included, and every race analysed in 2016 and 2020: the 800 m to the
  10,000 m, the steeplechase in 2020 (Rio's was timed at quarter laps to go, which no document
  places on the track) and two heats of the 400 m hurdles;
- every Olympic final from 1932 to 2016 whose runners' splits or halfway times World
  Athletics' statistics handbook gives: the 400 m from 1956 (at 300 m) and the 800 m from 1932
  (every 200 m from 1968), the 1500 m from 1936 (every 400 m), the steeplechase from 1952 to
  1996 (at 1000 m and 2000 m), the 200 m (halves), the women's 10,000 m from 2004 (halves),
  and the women's 100 m (every 20 m) and 3000 m of 1988;
- at the World Championships, every race World Athletics published a race analysis for: the
  200 m, 400 m, 400 m hurdles, 800 m to 10,000 m and steeplechase in 2022, 2023 and 2025; the
  800 m to the 10,000 m in 2015, 2017 and 2019 (every 400 m or 1000 m until 2017, every 100 m
  from 2019); the 400 m to the 3000 m at the World Indoors from 2024 to 2026; and the 200 m to
  the 5000 m at the 2026 Ultimate Championship. World Athletics publishes none for the 100 m,
  60 m and sprint hurdles;
- every race analysed at the 2024 European Championships in Rome (the 400 m, 400 m hurdles,
  800 m to 10,000 m and steeplechase) and at the 2026 Commonwealth Games in Glasgow (every
  individual track event, the 100 m timed every 10 m);
- every round of the 100 m, 200 m, 400 m and hurdles at the 2009 World Championships in
  Berlin, timed from video for most runners (every 20 m in the 100 m, 50 m in the 200 m,
  100 m in the 400 m, and at the touchdown after each hurdle); the 100 m finals of the 2017
  World Championships and the men's 60 m hurdles final of the 2018 World Indoors, timed from
  video (every 10 m, and at each hurdle);
- the world-record race of each sprint and hurdles event whose splits were published: all but
  the women's 100 m and the men's 110 m hurdles.

With the records set at the meetings above (Kipyegon's and Kerr's miles among them), 17 of the
32 events have their current world record in the data, Rudisha's 800 m at London 2012 among
them, and the Olympic finals bring many since broken, from Hampson's 800 m in 1932 to Ayana's
10,000 m at Rio 2016.

A current race is read from two official documents: its results (places, lanes, reaction
times) and its race analysis (the splits); where they overlap they must agree. For the 2016
Olympics, the 2024 European Championships and the 2026 Commonwealth Games both come from the
official results book, one PDF holding every report. Where no race analysis was published, the
splits come from the biomechanics reports of the 2009 and 2017 World Championships and the
2018 World Indoors, with the official results. Older races are read from what World Athletics
has published about them since: its statistics handbooks, which give the result and lanes of
every past Olympic final and, for many, the runners' halfway times or a table of their splits.

```
catalog/ ─▶ fetch & pin ─▶ read ─▶ assemble & check ─▶ publish ─▶ site/
 (YAML)     (SHA-256)     (one reader    (identity,      (DuckDB, CSV,
                           per format)    checks)         Parquet, JSON)
```

## The rules

1. **Every stored value is read from a document or declared in the catalog**, and carries
   where it came from: the document, page, box and exact text, and the extraction rule that
   read it; or the catalog file and line. The data model makes a value without a source
   impossible to construct.
2. **Derived values are never stored.** Segment times, speeds and typical splits are computed
   from the stored cumulative times whenever they are needed, so they cannot disagree.
3. **The catalog declares and documents attest.** Before any value is taken from a document,
   the document's own heading must confirm the race the catalog says it reports.
4. **Documents are pinned.** Every document is identified by the SHA-256 of its bytes in a
   committed lock file; a publisher silently replacing a PDF stops the build.
5. **Mistakes are flagged, never fixed.** Official documents contain errors. They are kept as
   published, flagged by named checks with an explanation, and left out of analyses.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Node 22.18 or later.

```bash
make setup   # install Python and site dependencies
make fetch   # download the documents in the catalog (checked against the lock files)
make build   # read, assemble, check and publish: build/splits.duckdb and the site data
make site    # run the website at http://localhost:5173
```

`make check` runs the linters, strict type checks and the test suite. The tests use text
layers of real documents saved in `tests/fixtures/`, so they need no network access.

## Exploring the data

The build writes `build/splits.duckdb`; the same tables are exported to `build/tables/` as CSV
and Parquet. [docs/schema.md](docs/schema.md) describes every table and column.

```sql
-- Where did this split come from?
SELECT s.time_s, p.document, p.page, p.text, p.method
FROM splits s JOIN provenance p ON p.id = s.time_source
WHERE s.performance = 'wch-2023-budapest/400m-men/final/antonio-watson';

-- Segment times and speeds, derived on the fly, with suspect values marked
SELECT * FROM split_analysis WHERE performance LIKE 'og-2024-paris/400m-men/final/%';
```

The command line inspects the dataset too:

```bash
uv run splits trace wch-2023-budapest/400m-men/final/antonio-watson   # provenance of every value
uv run splits read og-2024-paris/400mh-women/final/oris-c77a          # what a reader transcribes
uv run splits inspect og-2024-paris/400mh-women/final/oris-c77a       # a document as a reader sees it
```

## Repository layout

```
catalog/                     what the dataset is built from (curated, committed)
  disciplines.yaml           what is raced; barrier layouts for hurdles
  series.yaml                families of competitions
  athletes.yaml              identity rules for the cases name matching gets wrong
  annotations.yaml           what the marks printed beside results mean (TR16.8, YC)
  competitions/<id>/
    competition.yaml         a competition and every document published for it
    lock.json                the SHA-256 each document is pinned to (written by fetch)
src/splits/
  model/                     the data model: types and invariants, no I/O
  catalog/                   loading and validating the catalog
  acquire/                   downloading, content-addressed storage, pinning
  pdf/                       text layers and the layout toolkit readers use
  formats/                   one reader per kind of document
  discover/                  what publishers list for a competition, to audit the catalog
  assemble/                  readings to records: race confirmation, athlete identity
  checks/                    data-quality checks
  publish/                   the database, table exports and the site's data
  pipeline.py, cli.py
site/                        the website (React, TypeScript, Vite)
tests/                       unit tests and golden tests on real documents
docs/                        the data model, adding a format, the schema
```

## Adding data

**A competition whose documents an existing reader understands:** create
`catalog/competitions/<id>/competition.yaml` (copy a similar one) and list its documents with
the race each reports, then run `make fetch build`. The build stops, naming the file and line,
if a document does not confirm its declared race, if a reader cannot read it, or if an
athlete's identity is ambiguous.

Where the publisher lists a competition's documents (World Athletics' results pages, an
Olympic-style results book or document index), give the list's address as `results_url` or
`listing_url` and let `splits discover` write the documents:

```bash
uv run splits discover wch-2023-budapest           # compare the listing with the catalog
uv run splits discover wch-2023-budapest --write   # write every listed race into the catalog
```

It reports every race with splits the catalog neither declares nor excludes, so none is
missed silently; a race left out on purpose is listed under `excluded:` with the reason. See
[docs/data-model.md](docs/data-model.md#coverage-listed-declared-excluded).

**A new kind of document:** write a reader. It is one module that transcribes a page layout
using the toolkit in `splits.pdf.layout`; provenance comes for free. See
[docs/adding-a-format.md](docs/adding-a-format.md).

**An athlete the name matching gets wrong** (a changed name, two athletes with one name): add a
rule to `catalog/athletes.yaml`.

## Further reading

- [docs/data-model.md](docs/data-model.md): the entities, identifiers, provenance and checks,
  and why they are the way they are.
- [docs/adding-a-format.md](docs/adding-a-format.md): writing a reader for a new document type.
- [docs/schema.md](docs/schema.md): the database schema (generated).

## The website

`site/` is a static single-page app that reads the JSON written by `splits build`
(`site/public/data/`). Every race is replayed on a track drawn to the World Athletics
dimensions, round the oval or, for the sprints, down the straight, each athlete a line pulse in
their own lane passing every timing point at their published split, with the standings in the
infield (past the finish, on the straight) and the results table below; pointing at a
split, or a stretch of the track, marks that stretch in every lane and shows everyone's time
for it. Readers can race the field themselves: given a time, a ghost runs in an empty lane on
the typical splits for that time; runners whose splits were not published run theirs too. Both
are drawn dashed and never enter the tables: elite pacing is close to scale-invariant, so each
timing point's share of the finishing time is fitted as a line in the finishing time across
every run (within about 0.25 s at 200 m and 300 m of a 400 m, tested on runs left out). Event pages give
typical segment times and a split planner, and athlete pages compare each run with elites who
finished in the same time. Runs over the same course on the same kind of track (outdoors or
indoors) can be raced against each other from any races, men's and women's alike where they
run the same course (the 400 m hurdles differ only in height): each in a lane of its own, the
fastest in the middle as in a final, with their splits side by side.

Races follow the World Athletics rules for the track: to the 400 m in lanes all the way, the
800 m in lanes to the break line after the first bend, and from 1000 m from a waterfall start
without lanes, every race ending on the finish line. Indoors the track is a typical 200 m oval,
since venues' exact geometry is not published, and the steeplechase is drawn on the standard
lap, without its barriers. Between splits the motion is interpolated (an acceleration from the
blocks, then a smooth curve through every published time); the splits themselves are exact.
Out of lanes the data says how far along each runner is, not where across the track: runners
are drawn in lane 1, single file, moving out only to pass or when someone is alongside. The
view can follow the runners, closing in on the leaders (or any one runner) as they go round.

The site's TypeScript types are generated from the Python models (`npm run types`), so the
site cannot drift from the data. `make site-build` produces a deployable `site/dist/`; set
`BASE_PATH` when serving from a sub-path (e.g. GitHub Pages).

Documents remain the property of their publishers (World Athletics, OMEGA, the Olympic and
Commonwealth Games, European Athletics). The site links every race to its original documents.

## Deploying

Every push to `main` that passes the checks is built and published by the `deploy` job in
[.github/workflows/check.yml](.github/workflows/check.yml): the site to Cloudflare Pages, and
the table exports and database, larger than Pages allows a file, to a public Cloudflare R2
bucket. A private R2 bucket mirrors `data/store`, so a build only asks publishers for the
documents the mirror lacks, and it fetches with `splits fetch --locked`: every document must be
pinned in a committed lock file. `make deploy` publishes the same way from a machine that has
run `make build`.

To set it up once:

1. Create the Pages project and the buckets:

   ```bash
   npx wrangler pages project create track-splits --production-branch main
   npx wrangler r2 bucket create splits-documents
   npx wrangler r2 bucket create splits-downloads
   ```

   Connect custom domains to the Pages project (the site) and to `splits-downloads` (its URL
   is `DOWNLOADS_URL`). Keep `splits-documents` private: the site links to the publishers'
   copies.
2. Create an R2 API token with read and write access to both buckets, and an API token with
   the Cloudflare Pages Edit permission.
3. In the GitHub repository, add the secrets `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`,
   `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`, and the variable `DOWNLOADS_URL`.
4. Seed the mirror from a machine that has fetched every document, so the first deploy does
   not download them all again:

   ```bash
   CLOUDFLARE_ACCOUNT_ID=… AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… make mirror-push
   ```

The project and bucket names are set in the Makefile. Built without `VITE_DOWNLOADS_URL`, the
site links to downloads next to its data, as `make site-build` publishes them.

### The report form

`/report` lets visitors report wrong data, a missing race (with links to its documents), a
problem with the site, or an idea; each page's "Report" link fills in what the page shows. A
Pages Function (`site/functions/api/report.ts`) checks the report and files it as a GitHub
issue labelled `from-site` and one of `data-error`, `race-request`, `site-bug` or `idea`, with
the exact IDs and the build it was made on. Visitors need no GitHub account; Cloudflare
Turnstile keeps bots out. To set it up once:

1. Create the labels:

   ```bash
   gh label create from-site --color ededed
   gh label create data-error --color d73a4a
   gh label create race-request --color 0e8a16
   gh label create site-bug --color fbca04
   gh label create idea --color 1d76db
   ```

2. Add a Turnstile widget in the Cloudflare dashboard for the site's hostname. Its site key is
   the GitHub variable `TURNSTILE_SITE_KEY`.
3. Create a fine-grained GitHub token with access to this repository only and the Issues
   permission set to read and write. Give it and Turnstile's secret key to the Pages project:

   ```bash
   npx wrangler pages secret put GITHUB_TOKEN --project-name track-splits
   npx wrangler pages secret put TURNSTILE_SECRET_KEY --project-name track-splits
   npx wrangler pages secret put GITHUB_REPO --project-name track-splits
   ```

Without them the form answers that reports can't be sent. Reports are public issues, and their
text is written by visitors: whoever acts on them should treat it as untrusted.
