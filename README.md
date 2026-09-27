# Splits

A database of split times from elite track races, where **every value can be traced to the
exact words of the official document it was read from**, and a website for athletes and
coaches to explore how the world's best run their races.

It currently holds 1,145 races from 89 competitions (11,473 performances by 2,286 athletes,
131,003 split times):

- every elite race from the 100 m to the 5000 m, hurdles, steeplechase and mile included (and
  the occasional 300 m, 1000 m, 2000 m and two miles), whose race analysis OMEGA published at
  a Diamond League meeting from 2021 to 2026 or at the FBK Games in Hengelo from 2022 to 2024,
  with Hengelo's 10,000 m. National undercard races, B races and invitationals are left out.
  Sprints are timed every 10 m or at every hurdle (every 20 m, to the tenth, in 2021–22),
  longer races every 100 m, 200 m or lap;
- every archived round of the 2024 Olympic Games from the 100 m to the 10,000 m, hurdles and
  steeplechase included;
- the 400 m at the 2022, 2023 and 2025 World Championships (with the 200 m and 400 m hurdles
  in 2023) and at the 2024 and 2026 World Indoors;
- the world-record race of each sprint and hurdles event whose splits were published: all but
  the women's 100 m and the men's 110 m hurdles.

With the records set at the meetings above (Kipyegon's and Kerr's miles among them), 16 of the
31 events have their world record in the data.

A current race is read from two official documents: its results (places, lanes, reaction
times) and its race analysis (the splits); where they overlap they must agree. Older record
races are read from what World Athletics has published about them since: its statistics
handbooks, which give the result, lanes and halfway times of every past final, and the
biomechanics report of the 2009 World Championships.

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
  competitions/<id>/
    competition.yaml         a competition and every document published for it
    lock.json                the SHA-256 each document is pinned to (written by fetch)
src/splits/
  model/                     the data model: types and invariants, no I/O
  catalog/                   loading and validating the catalog
  acquire/                   downloading, content-addressed storage, pinning
  pdf/                       text layers and the layout toolkit readers use
  formats/                   one reader per kind of document
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
`catalog/competitions/<id>/competition.yaml` (copy a similar one), list its documents with the
race each reports, then run `make fetch build`. The build stops, naming the file and line, if
a document does not confirm its declared race, if a reader cannot read it, or if an athlete's
identity is ambiguous.

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

Documents remain the property of their publishers (World Athletics, OMEGA, the Olympic
Games). The site links every race to its original documents.

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
   npx wrangler pages project create splits --production-branch main
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
