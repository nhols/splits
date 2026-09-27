# The data model

The model lives in `src/splits/model/` as immutable, strictly validated Pydantic records. Read
the modules in this order: `values` (vocabularies), `ids` (identifiers), `provenance`,
`reference` (disciplines, timing points, series), `catalog` (what people declare), `records`
(what the dataset says happened), `dataset` (all of it, consistent).

## Entities

```
Series ─< Competition ─< Race ─< Performance >─ Athlete
                          │          │
                          │          ├─< Split      time from the gun at a timing point
                          │          └─< Segment    time between two points, as printed
                          └─< Document  what the race was read from
Discipline ─< Race   (what is raced: 400m, 400mh, ...)
```

- **Competition**: a meeting or championship (`wch-2023-budapest`), declared in the catalog
  with its dates, venue, time zone and setting (outdoor, indoor, road).
- **Race**: one start and one finish, identified by competition, discipline, sex, round and
  heat. A race is *declared* by the catalog and *attested* by one or more documents.
- **Document**: a published file, identified by its race and format, with the exact bytes read
  (SHA-256, size, when and from which URL) and what the document says about itself: its
  version, issue time and timing provider. A compilation (a statistics handbook of past
  results) reports many races; the catalog names the pages of the one it is declared for, and
  only those are read. Its format is of one of two kinds: *results*
  (places, lanes, reaction times, the official result) or *analysis* (splits).
- **Performance**: one athlete's run in one race: place, result (a time, or DNF/DNS/DQ), the
  time to the thousandth where printed (`20.90 (.893)`), lane, reaction time (negative for a
  false start), bib, country, birth date as printed, record tags (PB, NR...) and remarks (a
  rule broken, a card).
- **Split**: when an athlete reached a timing point, measured from the gun, and their position
  there, *according to one document*.
- **Segment**: the time between two timing points as a document prints it. Segments can be
  derived from splits, so printed ones serve to verify them (check `segment-matches-splits`).
- **Athlete**: a person, identified across documents and publishers.
- **Flag**: a finding of a data-quality check about one value.

## Identifiers

Every ID is readable and built from the entity's natural key, so it is stable across rebuilds
and meaningful in URLs, SQL and diffs:

| Entity | Example |
| --- | --- |
| Competition | `wch-2023-budapest` |
| Race | `wch-2023-budapest/400m-men/semi-final-2` |
| Document | `wch-2023-budapest/400m-men/semi-final-2/wa-rs5` |
| Athlete | `karsten-warholm` |
| Performance | `wch-2023-budapest/400m-men/final/antonio-watson` |
| Split | `wch-2023-budapest/400m-men/final/antonio-watson/200m@wa-rs5` |

Each kind of ID is a distinct type, so mypy rejects a document ID where a race ID is expected.
A race key reads `<discipline>-<sex>/<round>[-<heat>]`; a single-race round (a final, a
one-day meeting race) has no heat number.

## Provenance

Every value read from a document is a `Sourced[T]`: the value, its `source`, and the `method`
(the extraction rule that interpreted it, e.g. `cumulative.time`). A source is either

- a `Span`: document, page, box (PDF points from the page's top-left corner) and the exact
  text read; or
- a `CatalogRef`: catalog file, line and JSON pointer, for values a person declared.

Readers never build sources by hand: the layout toolkit (`splits.pdf.layout`) produces them
when a reader reads a regular-expression group or a set of words, so a source always covers
exactly the words a value came from. A `Sourced` value cannot be constructed without a
source, and the `Dataset` checks that every value was read from a document of its own race.

In the database, each sourced column has a sibling `<column>_source` holding an ID in the
`provenance` table.

**Derived values are not stored.** Segment times, speeds, shares of the race and typical
splits are computed from stored cumulative times: the `split_analysis` view in DuckDB, and
`site/src/data/analysis.ts` on the website.

## Declared versus attested

The catalog says which race a document reports; the document must agree. Each reader
transcribes the document's heading into its parts (discipline, sex, round, heat), and assembly
refuses a document whose heading contradicts the catalog. A part a document does not state
(Diamond League analyses give no round) cannot be confirmed, and is taken from the catalog.

## One race, several documents

Most races are read from a results document and a race analysis, and their facts overlap:
both print the athlete, the place and the result. Assembly combines them per fact. Where the
documents agree, the value is kept once, with the source of the more authoritative document:
a results document for results, places, lanes and reaction times. Where they disagree, that
document's value stands and the disagreement is reported as a flag (check `documents-agree`)
naming both values and both sources; nothing is averaged or silently overwritten. Birth dates
merge by precision: a year alone agrees with a full date in that year. Record tags and
remarks are collected from every document, each distinct one once.

## Timing points

A `TimingPoint` is a place along the race: the start, a distance line (`100m`), a barrier
(`H3`, resolved to its distance from the discipline's barrier layout: 115 m in the 400 m
hurdles), or the finish. Distances are decimals, so 110 m hurdle positions (13.72 m...) and road
distances (21,097.5 m) are exact.

Different documents time races differently: World Athletics every 100 m, OMEGA every 10 m in
the 200 m, every 50 m in the 400 m, and at each hurdle. **Splits are never merged across
documents**: each split names the document that measured it, so two timings of the same race
(official and video analysis, say) coexist and can be compared.

Some documents also time the finish line itself (Olympic reports print a `Finish` split with a
rank). Those are kept as printed, as splits at a `finish` point, and must equal the result
(check `finish-matches-result`); analyses take the finish from the result.

## Athletes and identity

By default two appearances are the same athlete when their given name, family name and
country match, ignoring case, accents and punctuation, whatever order the document prints
them in: `WARHOLM Karsten`, `Karsten WARHOLM` and `MAGI Rasmus`/`Rasmus MÄGI` all resolve. The
ID is the slug of the name. Anything the default cannot decide stops the build instead of
guessing: an ID claimed by two different names or countries needs a rule in
`catalog/athletes.yaml` (to merge name variants, or to separate two people who share a name).

Athlete fields summarise the printed values stored, with sources, on their performances. Birth
dates are `BirthDate` values that may give only a year, as some documents do; the athlete's
birth date is the most precise one all their documents agree with.

## Checks

Checks (`src/splits/checks/rules.py`) are named rules that report findings as `Flag`s attached
to one value. They never change or delete data. Each check has a severity (`error`: values
contradict each other; `warning`: a value is implausible) and says whether flagged values are
*suspect*, meaning analyses leave them out. Current checks: splits increase along the race,
splits come before the finish, the time at the line matches the result, printed segments agree
with the splits, speeds are humanly possible, splits look like other athletes' (a robust
statistical test, with a diagnosis of timing error versus a race that went wrong), time lost
late in the race (every split fast for the finish, as after a fall: the result is flagged and
analyses of typical pacing leave the whole run out, while its splits stay clean), ranks agree
with times, places agree with results, birth dates agree, and a race's documents agree with
each other.

## Integrity

Constructing a `Dataset` proves that IDs are unique, every reference resolves, performances
and races agree on sex, splits and segments are measured by documents of their own race, and
every flag is about an existing record. A dataset that exists is consistent.

## Design decisions

- **Decimal times.** `Decimal("44.20")` keeps the printed precision; floats would not.
- **Readings versus records.** Readers produce a `DocumentReading`, a faithful transcription.
  Identity, merging and plausibility are decided once, in assembly and checks, identically
  for every format. This keeps each reader small and each decision in one place.
- **Rounds.** First-round races are `heat` whatever a programme calls them ("Round 1",
  "Heats"). `heat` is the heat number within a round, absent for single races.
- **Setting** (outdoor, indoor, road) is a property of the competition, overridable per
  document, rather than a separate discipline: an indoor 400 m is still a 400 m, and filters
  can separate them.
- **Relays** are not read yet. The model is ready for them: a relay performance would be by
  a team rather than an athlete, with a table of legs mapping athletes to their stretch of
  the race; splits would attach to the performance as they do now.
